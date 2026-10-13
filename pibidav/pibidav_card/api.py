# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.utils import cint

from pibidav.pibidav_card import vcard
from pibidav.pibidav_card.sync import resolve_other_pending, save_link
from pibidav.pibidav_core.audit import log_operation


def own_doc(doctype, name):
	doc = frappe.get_doc(doctype, name)
	if doc.user != frappe.session.user:
		frappe.throw(_("This belongs to another user"), frappe.PermissionError)
	return doc


@frappe.whitelist()
def get_push_targets():
	"""Writable address books the current user syncs, for the push dialog."""
	return frappe.get_all(
		"DAV Collection",
		filters={"user": frappe.session.user, "service": "CardDAV", "sync_enabled": 1, "read_only": 0},
		fields=["name", "display_name"],
		order_by="display_name",
	)


@frappe.whitelist(methods=["POST"])
def push(contacts, collection):
	"""Queue the upload of the given contacts to one of the user's address books."""
	if not cint(frappe.db.get_single_value("DAV Settings", "card_push_enabled")):
		frappe.throw(_("Uploading contacts to CardDAV is switched off in DAV Settings"))
	names = json.loads(contacts) if isinstance(contacts, str) else list(contacts)
	target = own_doc("DAV Collection", collection)
	if target.service != "CardDAV" or target.read_only or not target.sync_enabled:
		frappe.throw(_("Choose one of your writable address books"))
	for name in names:
		frappe.has_permission("Contact", "read", name, throw=True)
	frappe.enqueue(
		"pibidav.pibidav_card.sync.push_contacts",
		contact_names=names,
		collection_name=target.name,
		queue="short",
		timeout=1800,
		job_name=f"pibidav: push {len(names)} contacts",
	)
	return {"queued": len(names)}


@frappe.whitelist(methods=["POST"])
def create_from_pending(name, link_doctype=None, link_name=None):
	"""Create a Contact from a vCard waiting in DAV Pending Contact."""
	pending = own_doc("DAV Pending Contact", name)
	if pending.status != "Pending":
		frappe.throw(_("This vCard was already handled"))
	card = vcard.parse(pending.vcard)
	if card is None:
		frappe.throw(_("The stored vCard cannot be read"))
	contact = vcard.apply(frappe.new_doc("Contact"), card)
	if link_doctype and link_name:
		if link_doctype not in ("Customer", "Supplier"):
			frappe.throw(_("A contact can only be linked to a Customer or a Supplier here"))
		frappe.has_permission(link_doctype, "read", link_name, throw=True)
		contact.append("links", {"link_doctype": link_doctype, "link_name": link_name})
	contact.insert()
	account = frappe.get_doc("DAV Account", pending.dav_account)
	collection = frappe.get_doc("DAV Collection", pending.dav_collection) if pending.dav_collection else None
	save_link(account, collection, contact.name, pending.uid, pending.href, pending.etag)
	pending.db_set({"status": "Created", "contact": contact.name})
	log_operation(account, "pending_create", pending.uid, detail=f"Contact {contact.name}")
	resolve_other_pending(pending.uid, contact.name)
	return contact.name


@frappe.whitelist(methods=["POST"])
def link_pending(name, contact):
	"""Link a waiting vCard to an existing Contact (no data is copied)."""
	pending = own_doc("DAV Pending Contact", name)
	if pending.status != "Pending":
		frappe.throw(_("This vCard was already handled"))
	frappe.has_permission("Contact", "write", contact, throw=True)
	account = frappe.get_doc("DAV Account", pending.dav_account)
	collection = frappe.get_doc("DAV Collection", pending.dav_collection) if pending.dav_collection else None
	save_link(account, collection, contact, pending.uid, pending.href, pending.etag)
	pending.db_set({"status": "Linked", "contact": contact})
	log_operation(account, "pending_link", pending.uid, detail=f"Contact {contact}")
	resolve_other_pending(pending.uid, contact)


@frappe.whitelist(methods=["POST"])
def discard_pending(name):
	pending = own_doc("DAV Pending Contact", name)
	pending.db_set("status", "Discarded")
	log_operation(frappe.get_doc("DAV Account", pending.dav_account), "pending_discard", pending.uid)
