# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import cint, escape_html, format_datetime

from pibidav.pibidav_cal import ical
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


def invitation_candidates(event):
	"""Contacts among the event participants, with the e-mail to use."""
	out = []
	for row in event.event_participants:
		if row.reference_doctype != "Contact" or not row.reference_docname:
			continue
		if not frappe.has_permission("Contact", "read", row.reference_docname):
			continue
		contact = frappe.db.get_value("Contact", row.reference_docname, ["full_name", "email_id"], as_dict=True) or {}
		email = row.email or contact.get("email_id")
		if email:
			out.append({"contact": row.reference_docname, "name": contact.get("full_name") or row.reference_docname, "email": email})
	return out


@frappe.whitelist()
def get_invitation_recipients(event):
	doc = frappe.get_doc("Event", event)
	doc.check_permission("write")
	return invitation_candidates(doc)


@frappe.whitelist(methods=["POST"])
def send_invitations(event, contacts):
	"""E-mail an iCalendar invitation to the selected Contact participants of an Event."""
	doc = frappe.get_doc("Event", event)
	doc.check_permission("write")
	wanted = set(json.loads(contacts) if isinstance(contacts, str) else contacts)
	recipients = [c for c in invitation_candidates(doc) if c["contact"] in wanted]
	if not recipients:
		frappe.throw(_("Choose at least one participant Contact with an e-mail address"))

	# Same UID as in the user's synced calendar, so the invitee's calendar sees one event
	uid = frappe.db.get_value("DAV Cal Link", {"event": doc.name, "user": frappe.session.user}, "uid") or (
		f"{doc.name}@{frappe.utils.get_host_name()}"
	)
	user = frappe.get_doc("User", frappe.session.user)
	ics = ical.invitation(doc, uid, user.email, user.full_name, [(r["email"], r["name"]) for r in recipients])

	when = format_datetime(doc.starts_on, "dd-MM-yyyy" if doc.all_day else "dd-MM-yyyy HH:mm")
	if doc.ends_on and doc.ends_on != doc.starts_on:
		when += " - " + format_datetime(doc.ends_on, "dd-MM-yyyy" if doc.all_day else "dd-MM-yyyy HH:mm")
	description = ical.html_to_text(doc.description)
	message = (
		f"<h3>{_('Event Invitation')}</h3>"
		f"<p><strong>{_('Event')}:</strong> {escape_html(doc.subject or '')}</p>"
		f"<p><strong>{_('Date/Time')}:</strong> {escape_html(when)}</p>"
	)
	if description:
		message += f"<p><strong>{_('Description')}:</strong><br>{escape_html(description).replace(chr(10), '<br>')}</p>"
	message += f"<hr><p><small>{_('Open the attached invitation to add it to your calendar.')}</small></p>"

	for r in recipients:
		frappe.sendmail(
			recipients=[r["email"]],
			subject=_("Event Invitation: {0}").format(doc.subject),
			message=message,
			attachments=[{"fname": "invitation.ics", "fcontent": ics}],
			reference_doctype="Event",
			reference_name=doc.name,
		)
	return {"sent": len(recipients)}
