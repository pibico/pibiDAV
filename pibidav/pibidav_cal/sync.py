# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Event sync between Frappe and the CalDAV calendars of each account.

Frappe v15 only lets the owner see a Private event, so every person has their
own copy of an event, owned by them and linked by the iCalendar UID. Each copy
is synced with that person's own account.
"""

from xml.sax.saxutils import escape

import frappe
from frappe.utils import cint, get_datetime, now_datetime

from pibidav.pibidav_cal import ical
from pibidav.pibidav_core.audit import log_operation
from pibidav.pibidav_core.client import DAVClient, DAVError
from pibidav.pibidav_core.discovery import (
	XML_HEADERS,
	mark_synced,
	parse_multistatus,
	sync_changes,
	tag,
)
from pibidav.pibidav_core.permissions import acting_as

BATCH = 50


def settings():
	return frappe.get_cached_doc("DAV Settings")


def usable(account):
	return account.enabled and account.status == "Connected" and account.service == "CalDAV"


def multiget(client, collection, hrefs):
	body = (
		'<cal:calendar-multiget xmlns:d="DAV:" xmlns:cal="urn:ietf:params:xml:ns:caldav">'
		"<d:prop><d:getetag/><cal:calendar-data/></d:prop>"
		+ "".join(f"<d:href>{escape(h)}</d:href>" for h in hrefs)
		+ "</cal:calendar-multiget>"
	)
	response = client.request("REPORT", collection.href, data=body, headers={**XML_HEADERS, "Depth": "1"})
	out = {}
	for href, props, _status in parse_multistatus(response.text)[0]:
		data = props.get(tag("cal", "calendar-data"))
		etag = props.get(tag("d", "getetag"))
		if data is not None and data.text:
			out[href] = (etag.text if etag is not None else None, data.text)
	return out


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


# ---------- CalDAV → Frappe ----------


def pull_collection(collection_name):
	collection = frappe.get_doc("DAV Collection", collection_name)
	account = frappe.get_doc("DAV Account", collection.dav_account)
	if not (cint(settings().cal_pull_enabled) and usable(account) and collection.sync_enabled):
		return
	client = DAVClient(account)
	with acting_as(account.user):
		try:
			changed, deleted, token = sync_changes(client, collection)
		except DAVError as e:
			if e.status not in (403, 409):
				log_operation(account, "pull", collection.href, "Error", str(e))
				raise
			# The server forgot our sync token: start again with a full sync
			collection.sync_token = None
			changed, deleted, token = sync_changes(client, collection)
		hrefs = list(changed)
		counts = {"created": 0, "updated": 0, "skipped": 0, "cancelled": 0}
		for i in range(0, len(hrefs), BATCH):
			for href, (etag, text) in multiget(client, collection, hrefs[i : i + BATCH]).items():
				frappe.db.savepoint("pibidav_cal_item")
				try:
					counts[handle_resource(account, collection, href, etag or changed.get(href), text)] += 1
				except Exception as e:
					# One bad event must not stop the rest of the calendar
					frappe.db.rollback(save_point="pibidav_cal_item")
					log_operation(account, "pull_item", href, "Error", str(e))
					counts["skipped"] += 1
		for href in deleted:
			counts["cancelled"] += remove_resource(account, href)
		mark_synced(collection, token)
		log_operation(account, "pull", collection.href, detail=str(counts))
		frappe.db.commit()
	return counts


def handle_resource(account, collection, href, etag, text):
	cal = ical.parse(text)
	uid = ical.uid_of(cal)
	if not uid:
		log_operation(account, "pull_item", href, "Skipped", "no VEVENT with UID")
		return "skipped"
	link = frappe.db.get_value("DAV Cal Link", {"dav_account": account.name, "uid": uid}, ["name", "event", "etag"], as_dict=True)
	if link and link.etag == etag:
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


def remove_resource(account, href):
	"""The event left the calendar: the link goes and the Event is cancelled, not deleted."""
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
	"""Write one Event to the server with the account of the user who owns it."""
	if not cint(settings().cal_push_enabled):
		return
	event = frappe.get_doc("Event", event_name)
	if link_name:
		link = frappe.get_doc("DAV Cal Link", link_name)
		account = frappe.get_doc("DAV Account", link.dav_account)
		collection = frappe.get_doc("DAV Collection", link.dav_collection) if link.dav_collection else None
	else:
		collection = frappe.get_doc("DAV Collection", collection_name)
		account = frappe.get_doc("DAV Account", collection.dav_account)
		link = None
	if not usable(account) or (collection and collection.read_only):
		return
	client = DAVClient(account)
	with acting_as(account.user):
		try:
			if link and link.href:
				current = client.request("GET", link.href)
				text = ical.build(event, link.uid, base_text=current.text, keep_server_rrule=link.rrule_kept)
				response = client.request(
					"PUT", link.href, data=text.encode(),
					headers={"Content-Type": "text/calendar; charset=utf-8", "If-Match": current.headers.get("ETag") or "*"},
				)
				uid, href = link.uid, link.href
			else:
				uid = ical.new_uid()
				href = collection.href.rstrip("/") + "/" + uid + ".ics"
				text = ical.build(event, uid)
				response = client.request(
					"PUT", href, data=text.encode(), headers={"Content-Type": "text/calendar; charset=utf-8", "If-None-Match": "*"}
				)
		except DAVError as e:
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
	"""Changes made in Frappe go to the server with the owner's account."""
	if doc.flags.from_dav or not cint(settings().cal_push_enabled):
		return
	for link in frappe.get_all("DAV Cal Link", filters={"event": doc.name, "user": frappe.session.user}, pluck="name"):
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
	"""Deleting an Event deletes it from the owner's calendar; links of others only go away."""
	for link in frappe.get_all("DAV Cal Link", filters={"event": doc.name}, fields=["name", "dav_account", "user", "href", "etag", "uid"]):
		if link.user == frappe.session.user and cint(settings().cal_push_enabled):
			frappe.enqueue(
				"pibidav.pibidav_cal.sync.delete_remote",
				account_name=link.dav_account, href=link.href, etag=link.etag, uid=link.uid,
				queue="short", enqueue_after_commit=True,
			)
		frappe.delete_doc("DAV Cal Link", link.name, ignore_permissions=True)


# ---------- scheduler ----------


def run_due_syncs():
	if not cint(settings().cal_pull_enabled):
		return
	interval = cint(settings().sync_interval) or 15
	for c in frappe.get_all("DAV Collection", filters={"service": "CalDAV", "sync_enabled": 1}, fields=["name", "last_sync"]):
		if c.last_sync and (now_datetime() - get_datetime(c.last_sync)).total_seconds() < interval * 60:
			continue
		frappe.enqueue(
			"pibidav.pibidav_cal.sync.pull_collection",
			collection_name=c.name,
			queue="short",
			job_id=f"pibidav-cal-{c.name}",
			deduplicate=True,
			timeout=900,
		)
