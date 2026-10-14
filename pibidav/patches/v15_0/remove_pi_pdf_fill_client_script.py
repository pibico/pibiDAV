# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""The Client Script 'Purchase Invoice PDF Fill' (module Pibidav) only lived in the
database of one site; its logic is now public/js/nc_invoice.js."""

import frappe


def execute():
	if frappe.db.exists("Client Script", "Purchase Invoice PDF Fill"):
		frappe.delete_doc("Client Script", "Purchase Invoice PDF Fill", ignore_permissions=True)
