// Copyright (c) 2026, pibiCo and contributors
// For license information, please see license.txt

const DAV_CARD_API = "pibidav.pibidav_card.api";

frappe.ui.form.on("DAV Pending Contact", {
	refresh(frm) {
		frm.disable_save();
		if (frm.doc.status !== "Pending" || frm.doc.user !== frappe.session.user) return;
		frm.add_custom_button(__("Create Contact"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Create Contact"),
				fields: [
					{ fieldname: "link_doctype", fieldtype: "Select", label: __("Link to"), options: ["", "Customer", "Supplier"] },
					{ fieldname: "link_name", fieldtype: "Dynamic Link", label: __("Party"), options: "link_doctype", depends_on: "link_doctype" },
				],
				primary_action_label: __("Create"),
				primary_action(values) {
					d.hide();
					frappe.call({ method: `${DAV_CARD_API}.create_from_pending`, args: { name: frm.doc.name, ...values } })
						.then((r) => frappe.set_route("Form", "Contact", r.message));
				},
			});
			d.show();
		});
		frm.add_custom_button(__("Link to Contact"), () => {
			frappe.prompt(
				{ fieldname: "contact", fieldtype: "Link", options: "Contact", label: __("Contact"), reqd: 1 },
				(values) => frappe.call({ method: `${DAV_CARD_API}.link_pending`, args: { name: frm.doc.name, contact: values.contact } })
					.then(() => frm.reload_doc()),
				__("Link to Contact")
			);
		});
		frm.add_custom_button(__("Discard"), () => {
			frappe.call({ method: `${DAV_CARD_API}.discard_pending`, args: { name: frm.doc.name } }).then(() => frm.reload_doc());
		});
	},
});
