# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Event sync between Frappe and the CalDAV calendars of each account.

Frappe v15 only lets the owner see a Private event, so every person has their
own copy of an event, owned by them and linked by the iCalendar UID. Each copy
is synced with that person's own account.
"""

import frappe
from frappe.utils import cint, now_datetime

from pibidav.pibidav_cal import ical
from pibidav.pibidav_core.audit import log_operation
from pibidav.pibidav_core.client import DAVClient, DAVError
from pibidav.pibidav_core.engine import settings
from pibidav.pibidav_core.engine import usable as account_usable
from pibidav.pibidav_core.permissions import acting_as


def usable(account):
	return account_usable(account, "CalDAV")


def save_link(account, collection, event, uid, href, etag, rrule_kept=None):
	name = frappe.db.get_value("DAV Cal Link", {"dav_account": account.name, "uid": uid})
	doc = frappe.get_doc("DAV Cal Link", name) if name else frappe.new_doc("DAV Cal Link")
	doc.update(
		{
			"event": event,
			"dav_account": account.name,
			"dav_collection": collection.name if collection else doc.dav_collection,
			"uid": uid,
			"href": href,
			"etag": etag,
			"last_sync": now_datetime(),
		}
	)
	if rrule_kept is not None:
		doc.rrule_kept = 0 if rrule_kept else 1
	doc.save(ignore_permissions=True)  # bookkeeping row of the account owner
	return doc


# ---------- CalDAV → Frappe (called by pibidav_core.engine) ----------


def handle_item(account, collection, href, etag, text):
	cal = ical.parse(text)
	uid = ical.uid_of(cal)
	if not uid:
		log_operation(account, "pull_item", href, "Skipped", "no VEVENT with UID")
		return "skipped"
	link = frappe.db.get_value(
		"DAV Cal Link", {"dav_account": account.name, "uid": uid}, ["name", "event", "etag", "href"], as_dict=True
	)
	if link and link.etag == etag:
		if link.href != href:  # moved to another calendar of the account
			frappe.db.set_value("DAV Cal Link", link.name, {"href": href, "dav_collection": collection.name})
		return "skipped"
	if link:
		event = frappe.get_doc("Event", link.event)
	else:
		event = frappe.new_doc("Event")
		event.event_type = "Private"
		event.owner = account.user
	supported = ical.apply(event, cal)
	event.flags.from_dav = True
	event.save()
	save_link(account, collection, event.name, uid, href, etag, rrule_kept=supported)
	if not supported:
		log_operation(account, "pull_item", uid, "Partial", "recurrence not representable in Frappe; kept on the server")
	return "updated" if link else "created"


def remove_item(account, href):
	"""The event left the account's calendars: the link goes and the Event is cancelled, not deleted."""
	cancelled = 0
	for link in frappe.get_all("DAV Cal Link", filters={"dav_account": account.name, "href": href}, fields=["name", "event", "uid"]):
		frappe.delete_doc("DAV Cal Link", link.name, ignore_permissions=True)
		if frappe.db.exists("Event", link.event) and not frappe.db.exists("DAV Cal Link", {"event": link.event}):
			event = frappe.get_doc("Event", link.event)
			if event.status != "Cancelled":
				event.status = "Cancelled"
				event.flags.from_dav = True
				event.save()
				cancelled += 1
		log_operation(account, "pull_item", link.uid, detail=f"removed on the server; Event {link.event} cancelled")
	return cancelled


# ---------- Frappe → CalDAV ----------


def push_event(event_name, link_name=None, collection_name=None):
	"""Write one Event to the server with the account of the link (or target calendar)."""
	if not cint(settings().cal_push_enabled) or not frappe.db.exists("Event", event_name):
		return
	if link_name:
		if not frappe.db.exists("DAV Cal Link", link_name):
			return
		link = frappe.get_doc("DAV Cal Link", link_name)
		account = frappe.get_doc("DAV Account", link.dav_account)
		collection = frappe.get_doc("DAV Collection", link.dav_collection) if link.dav_collection else None
	else:
		collection = frappe.get_doc("DAV Collection", collection_name)
		account = frappe.get_doc("DAV Account", collection.dav_account)
		if frappe.db.exists("DAV Cal Link", {"event": event_name, "dav_account": account.name}):
			return  # already sent by an earlier job
		link = None
	if not usable(account) or (collection and collection.read_only):
		return
	client = DAVClient(account)
	with acting_as(account.user):
		event = frappe.get_doc("Event", event_name)
		if not frappe.has_permission("Event", "read", event):
			return
		try:
			current = None
			if link and link.href:
				uid, href = link.uid, link.href
				try:
					current = client.request("GET", href)
				except DAVError as e:
					if e.status != 404:
						raise
					# Deleted on the server: write it again at the same place
			else:
				uid = ical.new_uid()
				href = collection.href.rstrip("/") + "/" + uid + ".ics"
			headers = {"Content-Type": "text/calendar; charset=utf-8"}
			if current is not None:
				server_etag = current.headers.get("ETag")
				if link.etag and server_etag and server_etag != link.etag:
					raise DAVError("changed on the server", 412)
				text = ical.build(event, uid, base_text=current.text, keep_server_rrule=link.rrule_kept)
				if server_etag:
					headers["If-Match"] = server_etag
			else:
				text = ical.build(event, uid)
				headers["If-None-Match"] = "*"
			response = client.request("PUT", href, data=text.encode(), headers=headers)
		except DAVError as e:
			if e.status == 412:
				log_operation(account, "push_item", uid, "Conflict", f"Event {event.name}: the server copy changed; not overwritten")
			else:
				log_operation(account, "push_item", event.name, "Error", str(e))
			frappe.db.commit()
			return
		save_link(account, collection, event.name, uid, href, response.headers.get("ETag"))
		log_operation(account, "push_item", uid, detail=f"Event {event.name}")
		frappe.db.commit()


def delete_remote(account_name, href, etag, uid):
	if not cint(settings().cal_push_enabled):
		return
	account = frappe.get_doc("DAV Account", account_name)
	if not usable(account):
		return
	try:
		DAVClient(account).request("DELETE", href, headers={"If-Match": etag} if etag else {})
		log_operation(account, "delete_item", uid)
	except DAVError as e:
		log_operation(account, "delete_item", uid, "Error", str(e))


# ---------- Event doc_events ----------


def on_event_update(doc, method=None):
	"""Changes made in Frappe, by anyone, go to every calendar the Event is linked to,
	each with the account of that calendar."""
	if doc.flags.from_dav or not cint(settings().cal_push_enabled):
		return
	for link in frappe.get_all("DAV Cal Link", filters={"event": doc.name}, pluck="name"):
		frappe.enqueue(
			"pibidav.pibidav_cal.sync.push_event",
			event_name=doc.name,
			link_name=link,
			queue="short",
			enqueue_after_commit=True,
			job_id=f"pibidav-cal-push-{link}",
			deduplicate=True,
		)


def on_event_trash(doc, method=None):
	"""Deleting an Event deletes it from every calendar it is linked to."""
	for link in frappe.get_all("DAV Cal Link", filters={"event": doc.name}, fields=["name", "dav_account", "href", "etag", "uid"]):
		if cint(settings().cal_push_enabled):
			frappe.enqueue(
				"pibidav.pibidav_cal.sync.delete_remote",
				account_name=link.dav_account, href=link.href, etag=link.etag, uid=link.uid,
				queue="short", enqueue_after_commit=True,
			)
		frappe.delete_doc("DAV Cal Link", link.name, ignore_permissions=True)
