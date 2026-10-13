# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Keep what pibicard left on Contact before its cr_* fields go away: the vCard UID
(so exported and synced copies keep their identity) goes to Contact.dav_uid, and the
notes become a Comment on the Contact. Does nothing where pibicard never ran."""

import re

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import escape_html

UID = re.compile(r"^UID:(.+)$", re.MULTILINE)


def execute():
	# The fixture with this field is synced after the patches
	create_custom_fields(
		{
			"Contact": [
				{
					"fieldname": "dav_uid",
					"fieldtype": "Data",
					"label": "vCard UID",
					"insert_after": "pulled_from_google_contacts",
					"hidden": 1,
					"read_only": 1,
					"no_copy": 1,
					"search_index": 1,
					"module": "Pibidav",
				}
			]
		},
		update=False,
	)

	if frappe.db.has_column("Contact", "cr_vcard_text"):
		for name, text in frappe.db.sql(
			"SELECT name, cr_vcard_text FROM `tabContact` WHERE cr_vcard_text LIKE %s AND IFNULL(dav_uid, '') = ''",
			"%UID:%",
		):
			match = UID.search(text or "")
			if match and 0 < len(match.group(1).strip()) <= 140:
				frappe.db.set_value("Contact", name, "dav_uid", match.group(1).strip(), update_modified=False)

	if frappe.db.has_column("Contact", "cr_notes"):
		for name, notes in frappe.db.sql("SELECT name, cr_notes FROM `tabContact` WHERE IFNULL(cr_notes, '') != ''"):
			content = escape_html(notes).replace("\n", "<br>")
			if not frappe.db.exists("Comment", {"reference_doctype": "Contact", "reference_name": name, "content": content}):
				frappe.get_doc(
					{
						"doctype": "Comment",
						"comment_type": "Comment",
						"reference_doctype": "Contact",
						"reference_name": name,
						"content": content,
					}
				).insert(ignore_permissions=True)  # migration of existing data
