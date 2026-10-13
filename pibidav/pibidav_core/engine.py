# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Pull engine shared by contacts (CardDAV) and calendars (CalDAV).

One background job per account pulls all its synced collections in turn, so two
jobs never handle the same account at once, and an item that moves from one
collection to another is seen as a move, not as a deletion plus a creation.
Each service module provides handle_item(account, collection, href, etag, text)
and remove_item(account, href), and declares its multiget REPORT.
"""

from xml.sax.saxutils import escape

import frappe
from frappe.utils import cint, get_datetime, now_datetime

from pibidav.pibidav_core.audit import log_operation
from pibidav.pibidav_core.client import DAVClient, DAVError
from pibidav.pibidav_core.discovery import NS, XML_HEADERS, mark_synced, parse_multistatus, sync_changes, tag

BATCH = 50

SERVICES = {
	"CardDAV": {
		"module": "pibidav.pibidav_card.sync",
		"pull_flag": "card_pull_enabled",
		"report": ("card", "addressbook-multiget", "address-data"),
	},
	"CalDAV": {
		"module": "pibidav.pibidav_cal.sync",
		"pull_flag": "cal_pull_enabled",
		"report": ("cal", "calendar-multiget", "calendar-data"),
	},
}


def settings():
	return frappe.get_cached_doc("DAV Settings")


def usable(account, service):
	return account.enabled and account.status == "Connected" and account.service == service


def multiget(client, collection, hrefs, service):
	prefix, report, data_prop = SERVICES[service]["report"]
	body = (
		f'<{prefix}:{report} xmlns:d="DAV:" xmlns:{prefix}="{NS[prefix]}">'
		f"<d:prop><d:getetag/><{prefix}:{data_prop}/></d:prop>"
		+ "".join(f"<d:href>{escape(h)}</d:href>" for h in hrefs)
		+ f"</{prefix}:{report}>"
	)
	response = client.request("REPORT", collection.href, data=body, headers={**XML_HEADERS, "Depth": "1"})
	out = {}
	for href, props, _status in parse_multistatus(response.text)[0]:
		data = props.get(tag(prefix, data_prop))
		etag = props.get(tag("d", "getetag"))
		if data is not None and data.text:
			out[href] = (etag.text if etag is not None else None, data.text)
	return out


def pull_account(account_name):
	"""Pull every synced collection of one account. Item deletions are applied at the end,
	once every collection has been read."""
	account = frappe.get_doc("DAV Account", account_name)
	service = SERVICES[account.service]
	if not (cint(settings().get(service["pull_flag"])) and usable(account, account.service)):
		return
	handler = frappe.get_module(service["module"])
	from pibidav.pibidav_core.permissions import acting_as

	deleted = []
	with acting_as(account.user):
		try:
			client = DAVClient(account)
		except (DAVError, frappe.ValidationError) as e:
			account_failed(account, e)
			return
		for name in frappe.get_all(
			"DAV Collection", filters={"dav_account": account.name, "sync_enabled": 1}, pluck="name", order_by="creation"
		):
			collection = frappe.get_doc("DAV Collection", name)
			try:
				deleted += pull_collection(client, account, collection, handler)
			except DAVError as e:
				frappe.db.rollback()
				log_operation(account, "pull", collection.href, "Error", str(e))
				if e.status == 401:
					account_failed(account, e)
					return
				if e.status == 404:
					collection.db_set("sync_enabled", 0)
					log_operation(account, "pull", collection.href, "Error", "collection no longer on the server; sync switched off")
				frappe.db.commit()
		removed = sum(handler.remove_item(account, href) for href in deleted)
		if removed:
			log_operation(account, "pull", None, detail=f"{removed} removed on the server")
		frappe.db.commit()


def account_failed(account, error):
	"""The credential no longer works: stop syncing until the owner reconnects."""
	from pibidav.pibidav_core.doctype.dav_account.dav_account import mark

	frappe.db.rollback()
	mark(account, "Error", str(error))
	log_operation(account, "pull", None, "Error", str(error))
	frappe.db.commit()


def pull_collection(client, account, collection, handler):
	"""Apply the changes of one collection; returns the hrefs deleted on the server."""
	full = not collection.sync_token
	try:
		changed, deleted, token = sync_changes(client, collection)
	except DAVError as e:
		if e.status not in (403, 409):
			raise
		# The server forgot our sync token: start again with a full sync
		collection.sync_token = None
		full = True
		changed, deleted, token = sync_changes(client, collection)
	if full:
		# A full listing reports no deletions: whatever we link and is not listed is gone
		link_doctype = "DAV Card Link" if account.service == "CardDAV" else "DAV Cal Link"
		deleted += [
			href
			for href in frappe.get_all(
				link_doctype, filters={"dav_account": account.name, "dav_collection": collection.name}, pluck="href"
			)
			if href not in changed
		]
	counts = {}
	hrefs = list(changed)
	for i in range(0, len(hrefs), BATCH):
		for href, (etag, text) in multiget(client, collection, hrefs[i : i + BATCH], account.service).items():
			frappe.db.savepoint("pibidav_item")
			try:
				result = handler.handle_item(account, collection, href, etag or changed.get(href), text)
			except Exception as e:
				# One bad item must not stop the rest of the collection
				frappe.db.rollback(save_point="pibidav_item")
				log_operation(account, "pull_item", href, "Error", str(e))
				result = "error"
			counts[result] = counts.get(result, 0) + 1
		frappe.db.commit()  # items are idempotent by ETag: a later failure does not redo them
	mark_synced(collection, token)
	changes = {k: v for k, v in counts.items() if k != "skipped"}
	if changes or deleted:
		log_operation(account, "pull", collection.href, detail=str({**changes, "deleted": len(deleted)}))
	frappe.db.commit()
	return deleted


def run_due_syncs():
	"""Cron entry: one pull job per account whose collections are due."""
	s = settings()
	interval = (cint(s.sync_interval) or 15) * 60
	services = [name for name, svc in SERVICES.items() if cint(s.get(svc["pull_flag"]))]
	if not services:
		return
	accounts = set(
		frappe.get_all(
			"DAV Account", filters={"enabled": 1, "status": "Connected", "service": ("in", services)}, pluck="name"
		)
	)
	due = set()
	for c in frappe.get_all(
		"DAV Collection", filters={"sync_enabled": 1}, fields=["dav_account", "last_sync"]
	):
		if c.dav_account in accounts and (
			not c.last_sync or (now_datetime() - get_datetime(c.last_sync)).total_seconds() >= interval
		):
			due.add(c.dav_account)
	for account in due:
		frappe.enqueue(
			"pibidav.pibidav_core.engine.pull_account",
			account_name=account,
			queue="short",
			job_id=f"pibidav-pull-{account}",
			deduplicate=True,
			timeout=1500,
		)
