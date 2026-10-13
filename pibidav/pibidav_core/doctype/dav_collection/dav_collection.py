# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from pibidav.pibidav_core.doctype.dav_account.dav_account import is_admin

# The owner may only choose which collections to sync
OWNER_EDITABLE = {"sync_enabled"}


class DAVCollection(Document):
	def validate(self):
		if is_admin() or self.flags.from_discovery:
			return
		if self.is_new():
			frappe.throw(_("Collections are discovered from the server"), frappe.PermissionError)
		before = self.get_doc_before_save()
		for df in self.meta.fields:
			if df.fieldname in OWNER_EDITABLE or df.fieldtype in ("Section Break", "Column Break"):
				continue
			if before and before.get(df.fieldname) != self.get(df.fieldname):
				frappe.throw(_("Only the sync switch can be changed"), frappe.PermissionError)


def has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if is_admin(user):
		return True
	if ptype in ("create", "delete"):
		return False
	return doc.user == user


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if is_admin(user):
		return ""
	return f"`tabDAV Collection`.`user` = {frappe.db.escape(user)}"
