# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint

from pibidav.pibidav_core.audit import log_operation


@frappe.whitelist()
def get_targets():
	"""Writable calendars the current user syncs."""
	return frappe.get_all(
		"DAV Collection",
		filters={"user": frappe.session.user, "service": "CalDAV", "sync_enabled": 1, "read_only": 0},
		fields=["name", "display_name"],
		order_by="display_name",
	)


@frappe.whitelist()
def get_links(event):
	frappe.has_permission("Event", "read", event, throw=True)
	return frappe.get_all(
		"DAV Cal Link",
		filters={"event": event, "user": frappe.session.user},
		fields=["name", "dav_collection", "last_sync", "rrule_kept"],
	)


@frappe.whitelist(methods=["POST"])
def link_event(event, collection):
	"""Send an Event to one of the user's calendars."""
	if not cint(frappe.db.get_single_value("DAV Settings", "cal_push_enabled")):
		frappe.throw(_("Writing events to CalDAV is switched off in DAV Settings"))
	frappe.has_permission("Event", "write", event, throw=True)
	target = frappe.get_doc("DAV Collection", collection)
	if target.user != frappe.session.user or target.service != "CalDAV" or target.read_only or not target.sync_enabled:
		frappe.throw(_("Choose one of your writable calendars"))
	if frappe.db.exists("DAV Cal Link", {"event": event, "dav_account": target.dav_account}):
		frappe.throw(_("This event is already in one of your calendars"))
	frappe.enqueue(
		"pibidav.pibidav_cal.sync.push_event", event_name=event, collection_name=target.name, queue="short"
	)
	return {"queued": 1}


@frappe.whitelist(methods=["POST"])
def unlink_event(link):
	"""Stop syncing an Event; it stays in Frappe and on the server."""
	doc = frappe.get_doc("DAV Cal Link", link)
	if doc.user != frappe.session.user:
		frappe.throw(_("This belongs to another user"), frappe.PermissionError)
	account = frappe.get_doc("DAV Account", doc.dav_account)
	doc.delete(ignore_permissions=True)
	log_operation(account, "unlink", doc.uid, detail=f"Event {doc.event}")
