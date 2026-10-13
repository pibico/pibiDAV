// Copyright (c) 2026, pibiCo and contributors
// For license information, please see license.txt

const DAV_CAL_API = "pibidav.pibidav_cal.api";

frappe.ui.form.on("Event", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.owner !== frappe.session.user) return;
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
