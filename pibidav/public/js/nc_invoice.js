// Copyright (c) 2026, pibiCo and contributors
// For license information, please see license.txt

// Sales and Purchase Invoice: the Nextcloud public link of the invoice PDF goes to the
// pdf_file field (when the site has one: pibitools adds it) and is read by the reports
// sent to the accounting advisor. Legacy, moves to pibidrive.

frappe.provide("pibidav.nc");

pibidav.nc.is_public_link = (url) =>
	typeof url === "string" && url.startsWith("http") && !url.includes("/files/") && !url.includes("/private/") &&
	!url.includes(window.location.hostname);

pibidav.nc.fill_pdf_file = function (frm, notify) {
	if (!frm.fields_dict.pdf_file || frm.doc.pdf_file || frm.is_new()) return;
	frappe.db
		.get_list("File", {
			filters: {
				attached_to_doctype: frm.doctype,
				attached_to_name: frm.docname,
				file_name: ["like", "%.pdf"],
				uploaded_to_nextcloud: 1,
			},
			fields: ["share_link", "file_url"],
			order_by: "creation desc",
			limit: 10,
		})
		.then((files) => {
			for (const file of files || []) {
				const url = pibidav.nc.is_public_link(file.share_link)
					? file.share_link
					: pibidav.nc.is_public_link(file.file_url) ? file.file_url : null;
				if (url && !frm.doc.pdf_file) {
					frm.set_value("pdf_file", url);
					notify && frappe.show_alert({ message: __("PDF field updated with NextCloud link"), indicator: "green" }, 5);
					return;
				}
			}
			notify && frappe.show_alert({ message: __("No NextCloud link found for this invoice"), indicator: "orange" }, 5);
		});
};

["Sales Invoice", "Purchase Invoice"].forEach((doctype) => {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			if (!frm.fields_dict.pdf_file || frm.is_new()) return;
			pibidav.nc.fill_pdf_file(frm);
			frm.add_custom_button(
				__("Fill PDF from NextCloud"),
				() => {
					if (frm.doc.pdf_file && !pibidav.nc.is_public_link(frm.doc.pdf_file)) frm.set_value("pdf_file", "");
					pibidav.nc.fill_pdf_file(frm, true);
				},
				__("Actions")
			);
		},
	});
});

// A new Sales Invoice gets its own addon, in the Nextcloud folder of its customer
frappe.ui.form.on("Sales Invoice", {
	after_save(frm) {
		if (!frm.doc.customer) return;
		frappe.db.get_value("PibiDAV Addon", { ref_doctype: "Customer", ref_docname: frm.doc.customer }, "nc_folder").then((r) => {
			const folder = r.message && r.message.nc_folder;
			if (!folder) return;
			frappe.db.exists("PibiDAV Addon", `pbc_${frm.doc.name}`).then((exists) => {
				if (exists) return;
				frappe.db
					.insert({ doctype: "PibiDAV Addon", ref_doctype: frm.doctype, ref_docname: frm.doc.name, nc_folder: folder })
					.then(() => frappe.show_alert(__("PibiDAV Addon created")));
			});
		});
	},
});
