# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""vCard tools that work without a CardDAV server: download, address book
export, QR code and .vcf import (formerly in pibicard)."""

import base64
import io
import json
import re

import frappe
import qrcode
import vobject
from frappe import _
from PIL import Image

from pibidav.pibidav_card import vcard
from pibidav.pibidav_core.permissions import acting_as

MAX_VCF_BYTES = 5 * 1024 * 1024
MAX_VCARDS = 5000


def legacy_uid(contact_name):
	"""UID that pibicard stored in Contact.cr_vcard_text, so exported and synced copies
	keep the same identity. Transitional: remove with pibicard and its cr_* fields."""
	if not frappe.db.has_column("Contact", "cr_vcard_text"):
		return None
	text = frappe.db.get_value("Contact", contact_name, "cr_vcard_text") or ""
	match = re.search(r"^UID:(.+)$", text, re.MULTILINE)
	return match.group(1).strip() if match else None


def card_uid(contact_name):
	return (
		frappe.db.get_value("DAV Card Link", {"contact": contact_name}, "uid")
		or legacy_uid(contact_name)
		or vcard.new_uid()
	)


def card_text(contact):
	return vcard.build(contact, card_uid(contact.name))


def readable_contact(name):
	doc = frappe.get_doc("Contact", name)
	doc.check_permission("read")
	return doc


def safe_filename(value):
	return re.sub(r"[^\w.-]+", "_", value or "contact").strip("_") or "contact"


@frappe.whitelist()
def download_vcard(contact):
	doc = readable_contact(contact)
	frappe.response["filename"] = safe_filename(doc.full_name or doc.name) + ".vcf"
	frappe.response["filecontent"] = card_text(doc)
	frappe.response["type"] = "download"


@frappe.whitelist(methods=["POST"])
def download_book(contacts):
	names = json.loads(contacts) if isinstance(contacts, str) else list(contacts)
	text = "".join(card_text(readable_contact(name)) for name in names)
	frappe.response["filename"] = "vcard_book.vcf"
	frappe.response["filecontent"] = text
	frappe.response["type"] = "download"


@frappe.whitelist()
def qr_code(contact):
	"""PNG data URI with the contact's vCard; the DAV Settings logo, if any, goes in the centre."""
	doc = readable_contact(contact)
	logo_url = frappe.db.get_single_value("DAV Settings", "qr_logo")
	qr = qrcode.QRCode(
		error_correction=qrcode.constants.ERROR_CORRECT_H if logo_url else qrcode.constants.ERROR_CORRECT_M,
		box_size=8,
		border=2,
	)
	qr.add_data(card_text(doc))
	try:
		qr.make(fit=True)
	except qrcode.exceptions.DataOverflowError:
		frappe.throw(_("This contact has too much data for a QR code"))
	image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
	if logo_url:
		logo_file = frappe.get_doc("File", {"file_url": logo_url})
		logo = Image.open(io.BytesIO(logo_file.get_content())).convert("RGBA")
		side = image.size[0] // 4  # error correction H tolerates about a quarter hidden
		logo.thumbnail((side, side))
		position = ((image.size[0] - logo.size[0]) // 2, (image.size[1] - logo.size[1]) // 2)
		image.paste(logo, position, logo)
	buffer = io.BytesIO()
	image.save(buffer, format="PNG")
	return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


@frappe.whitelist(methods=["POST"])
def import_vcf(file_url, link_doctype=None, link_name=None):
	"""Queue the import of an uploaded .vcf file."""
	frappe.has_permission("Contact", "create", throw=True)
	if link_doctype:
		if link_doctype not in ("Customer", "Supplier"):
			frappe.throw(_("Imported contacts can only be linked to a Customer or a Supplier"))
		frappe.has_permission(link_doctype, "read", link_name, throw=True)
	file_doc = frappe.get_doc("File", {"file_url": file_url})
	file_doc.check_permission("read")
	if (file_doc.file_size or 0) > MAX_VCF_BYTES:
		frappe.throw(_("The file is larger than {0} MB").format(MAX_VCF_BYTES // (1024 * 1024)))
	frappe.enqueue(
		"pibidav.pibidav_card.tools.run_import",
		file_name=file_doc.name,
		user=frappe.session.user,
		link_doctype=link_doctype,
		link_name=link_name,
		queue="long",
		timeout=1800,
	)
	return {"queued": 1}


def known_contact(uid, emails):
	"""Existing Contact for a vCard: by sync link, by pibicard UID, or by e-mail."""
	name = frappe.db.get_value("DAV Card Link", {"uid": uid}, "contact") if uid else None
	if not name and uid and frappe.db.has_column("Contact", "cr_vcard_text"):
		pattern = "%UID:" + uid.replace("%", r"\%").replace("_", r"\_") + "%"
		name = frappe.db.get_value("Contact", {"cr_vcard_text": ("like", pattern)})
	if not name and emails:
		name = frappe.db.get_value("Contact Email", {"email_id": ("in", emails), "parenttype": "Contact"}, "parent")
	return name


def run_import(file_name, user, link_doctype=None, link_name=None):
	counts = {"created": 0, "existing": 0, "invalid": 0}
	with acting_as(user):
		file_doc = frappe.get_doc("File", file_name)
		text = file_doc.get_content()
		if isinstance(text, bytes):
			text = text.decode("utf-8", errors="replace")
		try:
			cards = list(vobject.readComponents(text))[:MAX_VCARDS]
		except Exception:
			cards = []
			counts["invalid"] += 1
		for i, card in enumerate(cards, 1):
			frappe.db.savepoint("pibidav_vcf_item")
			try:
				data = vcard.summary(card)
				if known_contact(vcard.uid_of(card), data["emails"]):
					counts["existing"] += 1
					continue
				contact = vcard.apply(frappe.new_doc("Contact"), card)
				if link_doctype and link_name:
					contact.append("links", {"link_doctype": link_doctype, "link_name": link_name})
				contact.insert()
				counts["created"] += 1
			except Exception:
				frappe.db.rollback(save_point="pibidav_vcf_item")
				counts["invalid"] += 1
			if i % 50 == 0:
				frappe.db.commit()
				frappe.publish_realtime("pibidav_vcf_import", {"done": i, "total": len(cards)}, user=user)
		frappe.db.commit()
		file_doc.delete()  # the upload was only a carrier for this import
		frappe.db.commit()
	frappe.publish_realtime("pibidav_vcf_import", {"done": len(cards), "total": len(cards), "result": counts}, user=user)
	frappe.logger("pibidav.card").info(f"vCard import by {user}: {counts}")
	return counts
