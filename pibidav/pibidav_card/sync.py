# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Contact sync between Frappe and the CardDAV address books of each account.

Every server request uses the account of the person who owns it, and Frappe
permissions are checked as that person: nobody sees or changes through pibiDAV
what they could not see or change themselves.
"""

from xml.sax.saxutils import escape

import frappe
from frappe.utils import cint, get_datetime, now_datetime

from pibidav.pibidav_card import vcard
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
	return account.enabled and account.status == "Connected" and account.service == "CardDAV"


def multiget(client, collection, hrefs):
	body = (
		'<card:addressbook-multiget xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">'
		"<d:prop><d:getetag/><card:address-data/></d:prop>"
		+ "".join(f"<d:href>{escape(h)}</d:href>" for h in hrefs)
		+ "</card:addressbook-multiget>"
	)
	response = client.request("REPORT", collection.href, data=body, headers={**XML_HEADERS, "Depth": "1"})
	out = {}
	for href, props, _status in parse_multistatus(response.text)[0]:
		data = props.get(tag("card", "address-data"))
		etag = props.get(tag("d", "getetag"))
		if data is not None and data.text:
			out[href] = (etag.text if etag is not None else None, data.text)
	return out


# ---------- CardDAV → Frappe ----------


def pull_collection(collection_name):
	collection = frappe.get_doc("DAV Collection", collection_name)
	account = frappe.get_doc("DAV Account", collection.dav_account)
	if not (cint(settings().card_pull_enabled) and usable(account) and collection.sync_enabled):
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
		counts = {"updated": 0, "linked": 0, "pending": 0, "skipped": 0, "removed": 0}
		for i in range(0, len(hrefs), BATCH):
			for href, (etag, text) in multiget(client, collection, hrefs[i : i + BATCH]).items():
				frappe.db.savepoint("pibidav_card_item")
				try:
					counts[handle_card(account, collection, href, etag or changed.get(href), text)] += 1
				except Exception as e:
					# One bad vCard must not stop the rest of the address book
					frappe.db.rollback(save_point="pibidav_card_item")
					log_operation(account, "pull_item", href, "Error", str(e))
					counts["skipped"] += 1
		for href in deleted:
			# The vCard left this address book; the Contact stays in Frappe
			for doctype in ("DAV Card Link", "DAV Pending Contact"):
				for name in frappe.get_all(doctype, filters={"dav_account": account.name, "href": href}, pluck="name"):
					frappe.delete_doc(doctype, name, ignore_permissions=True)
					counts["removed"] += 1
		mark_synced(collection, token)
		log_operation(account, "pull", collection.href, detail=str(counts))
		frappe.db.commit()
	return counts


def handle_card(account, collection, href, etag, text):
	card = vcard.parse(text)
	uid = vcard.uid_of(card)
	if not uid:
		log_operation(account, "pull_item", href, "Skipped", "vCard without UID")
		return "skipped"
	link = frappe.db.get_value("DAV Card Link", {"dav_account": account.name, "uid": uid}, ["name", "contact", "etag"], as_dict=True)
	if link:
		if link.etag == etag:
			return "skipped"
		contact = frappe.get_doc("Contact", link.contact)
		if not frappe.has_permission("Contact", "write", contact):
			log_operation(account, "pull_item", uid, "Skipped", "no write permission on the Contact")
			return "skipped"
		vcard.apply(contact, card).save()
		frappe.db.set_value("DAV Card Link", link.name, {"etag": etag, "href": href, "last_sync": now_datetime()})
		log_operation(account, "pull_item", uid, detail=f"Contact {contact.name} updated")
		return "updated"

	# Same vCard already known through another account (shared address book) or by its
	# UID (Contact.dav_uid, kept from pibicard): link it
	known = frappe.db.get_value("DAV Card Link", {"uid": uid}, "contact") or frappe.db.get_value(
		"Contact", {"dav_uid": uid}
	)
	if known and frappe.has_permission("Contact", "read", known):
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
			"vcard": text,
			"status": "Pending" if doc.status != "Discarded" else "Discarded",
		}
	)
	doc.save(ignore_permissions=True)  # owned by the account user; filled by the sync job
	return "pending"


def resolve_other_pending(uid, contact):
	"""The same vCard waiting in other accounts (shared address book) now has a Contact."""
	for p in frappe.get_all(
		"DAV Pending Contact", filters={"uid": uid, "status": "Pending"}, fields=["name", "dav_account", "dav_collection", "href", "etag"]
	):
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
	done = 0
	with acting_as(account.user):
		for name in contact_names:
			try:
				push_contact(client, account, collection, name)
				done += 1
			except DAVError as e:
				log_operation(account, "push_item", name, "Error", str(e))
			frappe.publish_realtime(
				"pibidav_card_push", {"done": done, "total": len(contact_names), "contact": name}, user=account.user
			)
		frappe.db.commit()
	return done


def push_contact(client, account, collection, contact_name):
	contact = frappe.get_doc("Contact", contact_name)
	contact.check_permission("read")
	link = frappe.db.get_value(
		"DAV Card Link", {"dav_account": account.name, "contact": contact.name}, ["uid", "href", "etag"], as_dict=True
	)
	if link and link.href:
		current = client.request("GET", link.href)
		text = vcard.build(contact, link.uid, base_text=current.text)
		response = client.request(
			"PUT", link.href, data=text.encode(), headers={"Content-Type": "text/vcard; charset=utf-8", "If-Match": current.headers.get("ETag") or "*"}
		)
		uid, href = link.uid, link.href
	else:
		# Reuse the UID the contact already has in another address book, so all copies stay the same contact
		uid = frappe.db.get_value("DAV Card Link", {"contact": contact.name}, "uid") or vcard.new_uid()
		href = collection.href.rstrip("/") + "/" + uid + ".vcf"
		text = vcard.build(contact, uid)
		response = client.request(
			"PUT", href, data=text.encode(), headers={"Content-Type": "text/vcard; charset=utf-8", "If-None-Match": "*"}
		)
	save_link(account, collection, contact.name, uid, href, response.headers.get("ETag"))
	log_operation(account, "push_item", uid, detail=f"Contact {contact.name}")


# ---------- scheduler ----------


def run_due_card_syncs():
	"""Cron entry: enqueue the pull of every collection whose interval has passed."""
	if not cint(settings().card_pull_enabled):
		return
	interval = cint(settings().sync_interval) or 15
	collections = frappe.get_all(
		"DAV Collection",
		filters={"service": "CardDAV", "sync_enabled": 1},
		fields=["name", "dav_account", "last_sync"],
	)
	for c in collections:
		if c.last_sync and (now_datetime() - get_datetime(c.last_sync)).total_seconds() < interval * 60:
			continue
		frappe.enqueue(
			"pibidav.pibidav_card.sync.pull_collection",
			collection_name=c.name,
			queue="short",
			job_id=f"pibidav-card-{c.name}",
			deduplicate=True,
			timeout=900,
		)


def on_contact_trash(doc, method=None):
	"""Deleting a Contact in Frappe only drops its sync rows; the server is not touched."""
	for name in frappe.get_all("DAV Card Link", filters={"contact": doc.name}, pluck="name"):
		frappe.delete_doc("DAV Card Link", name, ignore_permissions=True)
	frappe.db.set_value("DAV Pending Contact", {"contact": doc.name}, "contact", None)
