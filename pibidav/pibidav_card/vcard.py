# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""vCard ↔ Contact mapping.

Frappe manages only the name, company, job title, e-mails and phones. When a
contact already exists on the server, those properties are replaced inside the
server's vCard and everything else (photo, addresses, birthday, notes set on
a phone) is kept.
"""

import uuid

import vobject
from frappe.utils import cstr, now_datetime

MANAGED = ("fn", "n", "org", "title", "email", "tel")


def new_uid():
	return str(uuid.uuid4())


BINARY = ("photo", "logo", "sound", "key")


def without_binaries(card):
	"""vCard text without photos and other binary properties, to keep in the database."""
	for key in BINARY:
		card.contents.pop(key, None)
	return card.serialize()


def parse(text):
	try:
		return vobject.readOne(text)
	except Exception:
		return None


def uid_of(card):
	return cstr(card.uid.value).strip() if card is not None and hasattr(card, "uid") else None


def summary(card):
	"""Plain fields used to show and match a vCard; no photo or notes."""
	n = card.n.value if hasattr(card, "n") else None
	org = card.org.value if hasattr(card, "org") else None
	return {
		"full_name": cstr(card.fn.value).strip() if hasattr(card, "fn") else "",
		"first_name": cstr(n.given).strip() if n else "",
		"middle_name": cstr(n.additional).strip() if n else "",
		"last_name": cstr(n.family).strip() if n else "",
		"company_name": cstr(org[0] if isinstance(org, list) and org else org).strip() if org else "",
		"designation": cstr(card.title.value).strip() if hasattr(card, "title") else "",
		"emails": [cstr(e.value).strip().lower() for e in card.contents.get("email", []) if cstr(e.value).strip()],
		"phones": [
			(cstr(t.value).strip(), "CELL" in [p.upper() for p in t.params.get("TYPE", [])])
			for t in card.contents.get("tel", [])
			if cstr(t.value).strip()
		],
	}


def build(contact, uid, base_text=None):
	"""vCard text for a Contact; base_text is the server's current vCard, if any."""
	card = parse(base_text) if base_text else None
	if card is None:
		card = vobject.vCard()
	for key in MANAGED + ("uid", "rev", "prodid"):
		card.contents.pop(key, None)

	card.add("uid").value = uid
	full_name = contact.full_name or " ".join(filter(None, [contact.first_name, contact.last_name])) or contact.name
	card.add("fn").value = full_name
	card.add("n").value = vobject.vcard.Name(
		family=cstr(contact.last_name), given=cstr(contact.first_name), additional=cstr(contact.middle_name)
	)
	if contact.company_name:
		card.add("org").value = [contact.company_name]
	if contact.designation:
		card.add("title").value = contact.designation
	for row in contact.email_ids:
		email = card.add("email")
		email.value = row.email_id
		email.type_param = ["INTERNET", "PREF"] if row.is_primary else ["INTERNET"]
	for row in contact.phone_nos:
		tel = card.add("tel")
		tel.value = row.phone
		tel.type_param = ["CELL"] if row.is_primary_mobile_no else ["VOICE"]
	card.add("prodid").value = "-//pibiCo//pibiDAV 15//EN"
	card.add("rev").value = now_datetime().strftime("%Y%m%dT%H%M%S")
	return card.serialize()


def apply(contact, card):
	"""Copy the managed vCard values into a Contact. E-mails and phones are only
	added, never removed, so data entered in Frappe is not lost."""
	data = summary(card)
	if data["first_name"] or data["last_name"]:
		contact.first_name = data["first_name"] or contact.first_name
		contact.middle_name = data["middle_name"]
		contact.last_name = data["last_name"]
	elif data["full_name"] and not contact.first_name:
		contact.first_name = data["full_name"]
	if data["company_name"]:
		contact.company_name = data["company_name"]
	if data["designation"]:
		contact.designation = data["designation"]

	known_emails = {cstr(r.email_id).strip().lower() for r in contact.email_ids}
	for email in data["emails"]:
		if email not in known_emails:
			contact.append("email_ids", {"email_id": email, "is_primary": 0 if contact.email_ids else 1})
			known_emails.add(email)

	def digits(value):
		return "".join(ch for ch in cstr(value) if ch.isdigit())

	known_phones = {digits(r.phone) for r in contact.phone_nos}
	for phone, is_mobile in data["phones"]:
		if digits(phone) and digits(phone) not in known_phones:
			has_mobile = any(r.is_primary_mobile_no for r in contact.phone_nos)
			has_phone = any(r.is_primary_phone for r in contact.phone_nos)
			contact.append(
				"phone_nos",
				{
					"phone": phone,
					"is_primary_mobile_no": 1 if is_mobile and not has_mobile else 0,
					"is_primary_phone": 1 if not is_mobile and not has_phone else 0,
				},
			)
			known_phones.add(digits(phone))
	return contact
