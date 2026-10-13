// Copyright (c) 2026, pibiCo and contributors
// For license information, please see license.txt

frappe.require("/assets/pibidav/js/dav_contact.js", () => {
	const settings = (frappe.listview_settings["Contact"] = frappe.listview_settings["Contact"] || {});
	const previous = settings.onload;
	settings.onload = function (listview) {
		previous && previous(listview);
		listview.page.add_actions_menu_item(__("Upload to CardDAV"), () => {
			const names = listview.get_checked_items(true);
			if (!names.length) return frappe.msgprint(__("Select the contacts to upload"));
			pibidav.card.push(names, () => listview.clear_checked_items());
		});
	};
});
