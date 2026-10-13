# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Contact sync between Frappe and the CardDAV address books of each account.

Every server request uses the account of the person who owns it, and Frappe
permissions are checked as that person: nobody sees or changes through pibiDAV
what they could not see or change themselves.
"""

import frappe
from frappe.utils import cint, get_datetime, now_datetime

from pibidav.pibidav_card import vcard
from pibidav.pibidav_core.audit import log_operation
from pibidav.pibidav_core.client import DAVClient, DAVError
from pibidav.pibidav_core.engine import settings
from pibidav.pibidav_core.engine import usable as account_usable
from pibidav.pibidav_core.permissions import acting_as


def usable(account):
	return account_usable(account, "CardDAV")


# ---------- CardDAV → Frappe (called by pibidav_core.engine) ----------


def handle_item(account, collection, href, etag, text):
	card = vcard.parse(text)
	uid = vcard.uid_of(card)
	if not uid:
		log_operation(account, "pull_item", href, "Skipped", "vCard without UID")
		return "skipped"
	link = frappe.db.get_value(
		"DAV Card Link", {"dav_account": account.name, "uid": uid}, ["name", "contact", "etag", "href", "last_sync"], as_dict=True
	)
	if link:
		if link.etag == etag:
			if link.href != href:  # moved to another address book of the account
				frappe.db.set_value("DAV Card Link", link.name, {"href": href, "dav_collection": collection.name})
			return "skipped"
		contact = frappe.get_doc("Contact", link.contact)
		if not frappe.has_permission("Contact", "write", contact):
			log_operation(account, "pull_item", uid, "Skipped", "no write permission on the Contact")
			return "skipped"
		if link.last_sync and get_datetime(contact.modified) > get_datetime(link.last_sync):
			# Edited in Frappe and on the server since the last sync: Frappe's version stays,
			# the server copy is not applied (Upload to CardDAV replaces it)
			frappe.db.set_value("DAV Card Link", link.name, {"etag": etag, "href": href, "last_sync": now_datetime()})
			log_operation(account, "pull_item", uid, "Conflict", f"Contact {contact.name} changed in Frappe and on the server; Frappe kept")
			return "conflict"
		vcard.apply(contact, card).save()
		frappe.db.set_value(
			"DAV Card Link", link.name, {"etag": etag, "href": href, "dav_collection": collection.name, "last_sync": now_datetime()}
		)
		log_operation(account, "pull_item", uid, detail=f"Contact {contact.name} updated")
		return "updated"

	# Same vCard already known through another account (shared address book) or by its
	# UID (Contact.dav_uid, kept from pibicard): link it
	known = frappe.db.get_value("DAV Card Link", {"uid": uid}, "contact") or frappe.db.get_value(
		"Contact", {"dav_uid": uid}
	)
	if known and frappe.has_permission("Contact", "write", known):
		save_link(account, collection, known, uid, href, etag)
		log_operation(account, "pull_item", uid, detail=f"linked to Contact {known}")
		return "linked"

	data = vcard.summary(card)
	pending = frappe.db.get_value("DAV Pending Contact", {"dav_account": account.name, "uid": uid}, ["name", "status"], as_dict=True)
	doc = frappe.get_doc("DAV Pending Contact", pending.name) if pending else frappe.new_doc("DAV Pending Contact")
	if pending and doc.status == "Discarded" and doc.etag == etag:
		return "skipped"
	doc.update(
		{
			"dav_account": account.name,
			"dav_collection": collection.name,
			"uid": uid,
			"href": href,
			"etag": etag,
			"full_name": data["full_name"] or " ".join(filter(None, [data["first_name"], data["last_name"]])),
			"company_name": data["company_name"],
			"emails": "\n".join(data["emails"]),
			"phones": "\n".join(p for p, _m in data["phones"]),
			"vcard": vcard.without_binaries(card),
			"status": "Pending" if doc.status != "Discarded" else "Discarded",
		}
	)
	doc.save(ignore_permissions=True)  # owned by the account user; filled by the sync job
	return "pending"


def remove_item(account, href):
	"""The vCard left the account's address books: its sync rows go, the Contact stays."""
	removed = 0
	for doctype in ("DAV Card Link", "DAV Pending Contact"):
		for name in frappe.get_all(doctype, filters={"dav_account": account.name, "href": href}, pluck="name"):
			frappe.delete_doc(doctype, name, ignore_permissions=True)
			removed += 1
	return removed


def resolve_other_pending(uid, contact):
	"""The same vCard waiting in other accounts (shared address book) now has a Contact.
	Each of those rows is linked only if its owner may edit that Contact."""
	for p in frappe.get_all(
		"DAV Pending Contact",
		filters={"uid": uid, "status": "Pending"},
		fields=["name", "user", "dav_account", "dav_collection", "href", "etag"],
	):
		if not frappe.has_permission("Contact", "write", contact, user=p.user):
			continue
		account = frappe.get_doc("DAV Account", p.dav_account)
		collection = frappe.get_doc("DAV Collection", p.dav_collection) if p.dav_collection else None
		save_link(account, collection, contact, uid, p.href, p.etag)
		frappe.db.set_value("DAV Pending Contact", p.name, {"status": "Linked", "contact": contact})
		log_operation(account, "pending_link", uid, detail=f"Contact {contact} (same vCard handled by another account)")


def save_link(account, collection, contact, uid, href, etag):
	name = frappe.db.get_value("DAV Card Link", {"dav_account": account.name, "uid": uid})
	doc = frappe.get_doc("DAV Card Link", name) if name else frappe.new_doc("DAV Card Link")
	doc.update(
		{
			"contact": contact,
			"dav_account": account.name,
			"dav_collection": collection.name if collection else doc.dav_collection,
			"uid": uid,
			"href": href,
			"etag": etag,
			"last_sync": now_datetime(),
		}
	)
	doc.save(ignore_permissions=True)  # bookkeeping row of the account owner
	return doc


# ---------- Frappe → CardDAV ----------


def push_contacts(contact_names, collection_name):
	collection = frappe.get_doc("DAV Collection", collection_name)
	account = frappe.get_doc("DAV Account", collection.dav_account)
	if not (cint(settings().card_push_enabled) and usable(account)) or collection.read_only:
		return
	client = DAVClient(account)
	counts = {"done": 0, "conflict": 0, "error": 0}
	with acting_as(account.user):
		for name in contact_names:
			frappe.db.savepoint("pibidav_push_item")
			try:
				counts[push_contact(client, account, collection, name)] += 1
			except Exception as e:
				frappe.db.rollback(save_point="pibidav_push_item")
				log_operation(account, "push_item", name, "Error", str(e) if isinstance(e, DAVError) else repr(e))
				counts["error"] += 1
			frappe.db.commit()  # every vCard already on the server keeps its link
	frappe.publish_realtime(
		"pibidav_card_push",
		{**counts, "total": len(contact_names), "address_book": collection.display_name},
		user=account.user,
	)
	return counts


def contact_uid(contact_name):
	"""The UID this Contact already has (in any address book, or kept from pibicard)."""
	return frappe.db.get_value("DAV Card Link", {"contact": contact_name}, "uid") or frappe.db.get_value(
		"Contact", contact_name, "dav_uid"
	)


def put_card(client, href, text, condition):
	return client.request(
		"PUT", href, data=text.encode(), headers={"Content-Type": "text/vcard; charset=utf-8", **condition}
	)


def push_contact(client, account, collection, contact_name):
	"""Upload one Contact. Returns 'done', or 'conflict' when the server copy changed
	since the last sync (it is not overwritten: the next pull brings it)."""
	contact = frappe.get_doc("Contact", contact_name)
	contact.check_permission("read")
	link = frappe.db.get_value(
		"DAV Card Link", {"dav_account": account.name, "contact": contact.name}, ["uid", "href", "etag"], as_dict=True
	)
	current = None
	if link and link.href:
		uid, href = link.uid, link.href
		try:
			current = client.request("GET", href)
		except DAVError as e:
			if e.status != 404:
				raise
			# Deleted on the server: upload it again at the same place
	else:
		uid = contact_uid(contact.name) or vcard.new_uid()
		href = collection.href.rstrip("/") + "/" + uid + ".vcf"

	try:
		if current is not None:
			server_etag = current.headers.get("ETag")
			if link.etag and server_etag and server_etag != link.etag:
				raise DAVError("changed on the server", 412)
			text = vcard.build(contact, uid, base_text=current.text)
			response = put_card(client, href, text, {"If-Match": server_etag} if server_etag else {})
		else:
			response = put_card(client, href, vcard.build(contact, uid), {"If-None-Match": "*"})
	except DAVError as e:
		if e.status != 412:
			raise
		log_operation(account, "push_item", uid, "Conflict", f"Contact {contact.name}: the server copy changed; not overwritten")
		return "conflict"
	save_link(account, collection, contact.name, uid, href, response.headers.get("ETag"))
	log_operation(account, "push_item", uid, detail=f"Contact {contact.name}")
	return "done"


# ---------- Contact doc_events ----------


def on_contact_trash(doc, method=None):
	"""Deleting a Contact in Frappe only drops its sync rows; the server is not touched."""
	for name in frappe.get_all("DAV Card Link", filters={"contact": doc.name}, pluck="name"):
		frappe.delete_doc("DAV Card Link", name, ignore_permissions=True)
	frappe.db.set_value("DAV Pending Contact", {"contact": doc.name}, "contact", None)
