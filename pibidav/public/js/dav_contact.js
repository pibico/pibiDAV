// Copyright (c) 2026, pibiCo and contributors
// For license information, please see license.txt

frappe.provide("pibidav.card");

pibidav.card.push = function (contacts, after) {
	frappe.call("pibidav.pibidav_card.api.get_push_targets").then((r) => {
		const targets = r.message || [];
		if (!targets.length) {
			frappe.msgprint(__("You have no writable address book with sync enabled. Open your CardDAV account in DAV Account."));
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("Upload to CardDAV"),
			fields: [
				{
					fieldname: "collection",
					fieldtype: "Select",
					label: __("Address Book"),
					reqd: 1,
					options: targets.map((t) => ({ value: t.name, label: t.display_name })),
					default: targets[0].name,
				},
			],
			primary_action_label: __("Upload"),
			primary_action(values) {
				d.hide();
				frappe.call({
					method: "pibidav.pibidav_card.api.push",
					args: { contacts: JSON.stringify(contacts), collection: values.collection },
				}).then((res) => {
					frappe.show_alert({ message: __("{0} contacts queued", [res.message.queued]), indicator: "blue" });
					after && after();
				});
			},
		});
		d.show();
	});
};

pibidav.card.show_qr = function (contact) {
	frappe.call({ method: "pibidav.pibidav_card.tools.qr_code", args: { contact: contact.name } }).then((r) => {
		if (!r.message) return;
		const d = new frappe.ui.Dialog({
			title: __("QR Code"),
			fields: [{ fieldname: "qr", fieldtype: "HTML" }],
			primary_action_label: __("Download"),
			primary_action() {
				const a = document.createElement("a");
				a.href = r.message;
				a.download = `${(contact.full_name || contact.name).replace(/[^\w.-]+/g, "_")}_qr.png`;
				a.click();
			},
		});
		const img = document.createElement("img");
		img.src = r.message;
		img.style.cssText = "display:block;margin:0 auto;max-width:100%";
		d.fields_dict.qr.$wrapper.empty().append(img);
		d.show();
	});
};

pibidav.card.import_vcf = function (listview) {
	new frappe.ui.FileUploader({
		folder: "Home/Attachments",
		restrictions: { allowed_file_types: [".vcf"] },
		allow_multiple: false,
		make_attachments_public: false,
		on_success(file) {
			const d = new frappe.ui.Dialog({
				title: __("Import vCard"),
				fields: [
					{ fieldname: "link_doctype", fieldtype: "Select", label: __("Link all to"), options: ["", "Customer", "Supplier"] },
					{ fieldname: "link_name", fieldtype: "Dynamic Link", label: __("Party"), options: "link_doctype", depends_on: "link_doctype" },
				],
				primary_action_label: __("Import"),
				primary_action(values) {
					d.hide();
					frappe.realtime.off("pibidav_vcf_import");
					frappe.realtime.on("pibidav_vcf_import", (data) => {
						frappe.show_progress(__("Importing vCards"), data.done, data.total || 1);
						if (data.result) {
							frappe.realtime.off("pibidav_vcf_import");
							frappe.hide_progress();
							frappe.msgprint(__("Created: {0}. Already existing: {1}. Not readable: {2}.", [data.result.created, data.result.existing, data.result.invalid]));
							listview && listview.refresh();
						}
					});
					frappe.call({ method: "pibidav.pibidav_card.tools.import_vcf", args: { file_url: file.file_url, ...values } });
				},
			});
			d.show();
		},
	});
};

frappe.ui.form.on("Contact", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Upload to CardDAV"), () => pibidav.card.push([frm.doc.name]), __("vCard"));
		frm.add_custom_button(__("Download vCard"), () => {
			window.open(`/api/method/pibidav.pibidav_card.tools.download_vcard?contact=${encodeURIComponent(frm.doc.name)}`);
		}, __("vCard"));
		frm.add_custom_button(__("QR Code"), () => pibidav.card.show_qr(frm.doc), __("vCard"));
	},
});
