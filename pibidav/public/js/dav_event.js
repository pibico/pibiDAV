// Copyright (c) 2026, pibiCo and contributors
// For license information, please see license.txt

const DAV_CAL_API = "pibidav.pibidav_cal.api";

frappe.ui.form.on("Event", {
	refresh(frm) {
		if (frm.is_new()) return;
		if ((frm.doc.event_participants || []).some((p) => p.reference_doctype === "Contact")) {
			frm.add_custom_button(__("Send Invitations"), () => send_invitations(frm));
		}
		if (frm.doc.owner !== frappe.session.user) return;
		frappe.call({ method: `${DAV_CAL_API}.get_links`, args: { event: frm.doc.name } }).then((r) => {
			const links = r.message || [];
			if (links.length) {
				frm.dashboard.set_headline(__("Synced with your CalDAV calendar"));
				frm.add_custom_button(__("Stop syncing"), () => {
					frappe.confirm(__("The event stays in Frappe and in the calendar, but changes will no longer be synced. Continue?"), () =>
						frappe.call({ method: `${DAV_CAL_API}.unlink_event`, args: { link: links[0].name } }).then(() => frm.reload_doc())
					);
				}, __("CalDAV"));
				return;
			}
			frm.add_custom_button(__("Send to CalDAV"), () => {
				frappe.call(`${DAV_CAL_API}.get_targets`).then((t) => {
					const targets = t.message || [];
					if (!targets.length) {
						frappe.msgprint(__("You have no writable calendar with sync enabled. Open your CalDAV account in DAV Account."));
						return;
					}
					frappe.prompt(
						{
							fieldname: "collection",
							fieldtype: "Select",
							label: __("Calendar"),
							reqd: 1,
							options: targets.map((c) => ({ value: c.name, label: c.display_name })),
							default: targets[0].name,
						},
						(values) =>
							frappe.call({ method: `${DAV_CAL_API}.link_event`, args: { event: frm.doc.name, collection: values.collection } })
								.then(() => frappe.show_alert({ message: __("Queued"), indicator: "blue" })),
						__("Send to CalDAV")
					);
				});
			}, __("CalDAV"));
		});
	},
});

function send_invitations(frm) {
	frappe.call({ method: `${DAV_CAL_API}.get_invitation_recipients`, args: { event: frm.doc.name } }).then((r) => {
		const people = r.message || [];
		if (!people.length) {
			frappe.msgprint(__("No participant Contact has an e-mail address."));
			return;
		}
		const d = new frappe.ui.Dialog({
			title: __("Send Invitations"),
			fields: people.map((p, i) => ({
				fieldname: `c${i}`,
				fieldtype: "Check",
				label: frappe.utils.escape_html(`${p.name} (${p.email})`),
				default: 1,
			})),
			primary_action_label: __("Send"),
			primary_action(values) {
				const contacts = people.filter((p, i) => values[`c${i}`]).map((p) => p.contact);
				d.hide();
				frappe.call({
					method: `${DAV_CAL_API}.send_invitations`,
					args: { event: frm.doc.name, contacts: JSON.stringify(contacts) },
					freeze: true,
				}).then((res) => frappe.show_alert({ message: __("{0} invitations sent", [res.message.sent]), indicator: "green" }));
			},
		});
		d.show();
	});
}
