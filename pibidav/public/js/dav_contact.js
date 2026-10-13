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

frappe.ui.form.on("Contact", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Upload to CardDAV"), () => pibidav.card.push([frm.doc.name]), __("CardDAV"));
	},
});
