# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import add_days, cint, now_datetime


def log_operation(account, operation, resource=None, result="OK", detail=None, user=None):
	"""Append a row to DAV Audit Log. Never stores vCard or event content."""
	doc = frappe.get_doc(
		{
			"doctype": "DAV Audit Log",
			"user": user or frappe.session.user,
			"dav_account": account.name if account else None,
			"service": account.service if account else None,
			"operation": operation,
			"resource": (resource or "")[:500],
			"result": result,
			"detail": (detail or "")[:1000],
			"ip_address": getattr(frappe.local, "request_ip", None),
		}
	)
	doc.flags.from_audit = True
	# Audit rows are written by the system on behalf of the acting user; no role may
	# create them through the UI or API, so permissions are bypassed on purpose here.
	doc.insert(ignore_permissions=True)


def purge_old_entries():
	days = cint(frappe.db.get_single_value("DAV Settings", "audit_retention_days")) or 730
	cutoff = add_days(now_datetime(), -days)
	frappe.db.delete("DAV Audit Log", {"creation": ("<", cutoff)})
