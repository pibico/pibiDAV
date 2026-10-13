# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""One sync link per account and UID: a second job can never create a duplicate."""

import frappe


def execute():
	for doctype in ("DAV Card Link", "DAV Cal Link"):
		frappe.db.add_unique(doctype, ["dav_account", "uid"], constraint_name="unique_account_uid")
