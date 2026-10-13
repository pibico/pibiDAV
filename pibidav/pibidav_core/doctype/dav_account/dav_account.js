// Copyright (c) 2026, pibiCo and contributors
// For license information, please see license.txt

const DAV_ACCOUNT = "pibidav.pibidav_core.doctype.dav_account.dav_account";

frappe.ui.form.on("DAV Account", {
	refresh(frm) {
		if (frm.is_new()) return;
		const is_owner = frm.doc.user === frappe.session.user;
		if (is_owner && frm.doc.server_type === "Nextcloud" && frm.doc.enabled) {
			frm.add_custom_button(__("Connect"), () => start_login_flow(frm));
		}
		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: `${DAV_ACCOUNT}.test_connection`,
				args: { name: frm.doc.name },
				freeze: true,
			}).then((r) => {
				const res = r.message || {};
				frappe.show_alert({
					message: res.ok ? __("Connected") : __("Error: {0}", [res.error]),
					indicator: res.ok ? "green" : "red",
				});
				frm.reload_doc();
			});
		});
	},
});

function start_login_flow(frm) {
	frappe.call({
		method: `${DAV_ACCOUNT}.start_login_flow`,
		args: { name: frm.doc.name },
	}).then((r) => {
		const url = r.message && r.message.login_url;
		if (!url) return;
		window.open(url, "_blank", "noopener");
		frappe.show_alert({ message: __("Log in to Nextcloud in the new tab and grant access"), indicator: "blue" }, 10);
		poll_login_flow(frm, 0);
	});
}

function poll_login_flow(frm, attempt) {
	// Nextcloud keeps the login token for 20 minutes; poll every 3 seconds
	if (attempt > 400) return;
	frappe.call({
		method: `${DAV_ACCOUNT}.poll_login_flow`,
		args: { name: frm.doc.name },
	}).then((r) => {
		const res = r.message || {};
		if (res.status === "waiting") {
			setTimeout(() => poll_login_flow(frm, attempt + 1), 3000);
		} else if (res.status === "done") {
			frappe.show_alert({
				message: res.ok ? __("Account connected") : __("Error: {0}", [res.error]),
				indicator: res.ok ? "green" : "red",
			});
			frm.reload_doc();
		} else {
			frappe.msgprint(res.error || __("The login expired. Press Connect again."));
		}
	});
}
