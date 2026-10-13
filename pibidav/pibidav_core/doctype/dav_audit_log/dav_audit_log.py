# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DAVAuditLog(Document):
	"""Append-only: rows are written by pibidav.pibidav_core.audit and never edited."""

	def before_insert(self):
		if not self.flags.from_audit:
			frappe.throw(_("DAV Audit Log entries are created by the system only"), frappe.PermissionError)

	def validate(self):
		if not self.is_new():
			frappe.throw(_("DAV Audit Log entries cannot be modified"), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("DAV Audit Log entries cannot be deleted"), frappe.PermissionError)
