# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""pibidav keeps only CalDAV and CardDAV (Paco, 14/10/2026). The Nextcloud part
(folders per record, uploads, public links, backups) moved to pibidrive: its folders
were migrated to pibidrive by a reviewed one-off script, and its data was archived to
CSV before this patch. This patch removes from the database:

* the custom fields of the old «Pibidav» module (the Nextcloud ones: Customer, Supplier,
  Project, Purchase Invoice, File, Tag and the Nextcloud credentials in User), with
  their columns and the stored User tokens. Contact.dav_uid (CardDAV) stays and moves to
  the «Pibidav Card» module;
* the doctypes of that module (PibiDAV Addon, NextCloud Settings, Folder Set, Reference
  Item, Attachment Item, File Category) and their tables;
* the «Pibidav» Module Def.
"""

import frappe
from frappe.model import no_value_fields

DOCTYPES = ("PibiDAV Addon", "Attachment Item", "Reference Item", "NextCloud Settings", "Folder Set", "File Category")


def execute():
	if frappe.db.exists("Custom Field", "Contact-dav_uid"):
		frappe.db.set_value("Custom Field", "Contact-dav_uid", "module", "Pibidav Card", update_modified=False)

	fields = frappe.get_all("Custom Field", filters={"module": "Pibidav"}, fields=["name", "dt", "fieldname", "fieldtype"])
	for cf in fields:
		frappe.delete_doc("Custom Field", cf.name, force=True, ignore_permissions=True)
		if cf.fieldtype in no_value_fields or not frappe.db.table_exists(cf.dt):
			continue
		if frappe.db.has_column(cf.dt, cf.fieldname):
			frappe.db.sql_ddl(f"alter table `tab{cf.dt}` drop column `{cf.fieldname}`")
	frappe.db.delete("__Auth", {"doctype": "User", "fieldname": "nextcloud_token"})

	for dt in DOCTYPES:
		if frappe.db.exists("DocType", dt):
			frappe.delete_doc("DocType", dt, force=True, ignore_permissions=True)
		frappe.db.sql_ddl(f"drop table if exists `tab{dt}`")
	frappe.db.delete("Singles", {"doctype": "NextCloud Settings"})

	if frappe.db.exists("Module Def", "Pibidav"):
		frappe.delete_doc("Module Def", "Pibidav", force=True, ignore_permissions=True)
	frappe.clear_cache()
