// Copyright (c) 2026, pibiCo and contributors
// For license information, please see license.txt

// Customer and Supplier: the Nextcloud folder of the party (PibiDAV Addon). Legacy, moves to pibidrive.

frappe.provide("pibidav.nc");

pibidav.nc.update_folder_link = function (frm) {
	if (frm.doc.nc_folder_link) return;
	frappe.db
		.get_list("PibiDAV Addon", {
			filters: { ref_doctype: frm.doctype, ref_docname: frm.doc.name },
			fields: ["name", "nc_folder_internal_link"],
		})
		.then((records) => {
			if (!records || !records.length) {
				frappe.msgprint(__("No PibiDAV Addon record found for this {0}", [__(frm.doctype)]));
				return;
			}
			frm.set_value("nextcloud", records[0].name);
			if (records[0].nc_folder_internal_link) {
				frm.set_value("nc_folder_link", records[0].nc_folder_internal_link);
			}
		});
};

["Customer", "Supplier"].forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		setup(frm) {
			frm.set_query("nextcloud", () => ({ filters: { ref_doctype: frm.doctype, ref_docname: frm.doc.name } }));
		},
		nextcloud(frm) {
			pibidav.nc.update_folder_link(frm);
		},
	});
});
