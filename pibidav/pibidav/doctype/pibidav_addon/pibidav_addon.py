# Copyright (c) 2022, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PibiDAVAddon(Document):
	pass


def has_permission(doc, ptype=None, user=None, debug=False):
	"""An addon (NextCloud folder and links of a document) is seen and changed only by
	those who may see or change that document."""
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return True
	if not (doc.ref_doctype and doc.ref_docname) or not frappe.db.exists(doc.ref_doctype, doc.ref_docname):
		return False
	needed = "read" if ptype in ("read", "select", "print", "email") else "write"
	return frappe.has_permission(doc.ref_doctype, needed, doc=doc.ref_docname, user=user)
