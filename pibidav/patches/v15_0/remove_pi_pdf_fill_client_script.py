# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""The Client Script 'Purchase Invoice PDF Fill' (module Pibidav) only lived in the
database of one site; its logic moved to public/js/nc_invoice.js and, on 14/10/2026,
to the cloud button of pibidrive (public link of the invoice PDF in pdf_file)."""

import frappe


def execute():
	if frappe.db.exists("Client Script", "Purchase Invoice PDF Fill"):
		frappe.delete_doc("Client Script", "Purchase Invoice PDF Fill", ignore_permissions=True)
