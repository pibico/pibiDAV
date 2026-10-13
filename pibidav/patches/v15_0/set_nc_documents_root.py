# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Documents Root of NextCloud Settings: the common top folder of the destination
folders already configured, so existing addons keep working."""

import frappe


def execute():
	if frappe.db.get_single_value("NextCloud Settings", "nc_documents_root"):
		return
	folders = [f for f in frappe.get_all("Reference Item", filters={"parent": "NextCloud Settings"}, pluck="nc_folder") if f]
	tops = {"/" + f.strip("/").split("/")[0] + "/" for f in folders if f.strip("/")}
	if len(tops) == 1:
		frappe.db.set_single_value("NextCloud Settings", "nc_documents_root", tops.pop())
