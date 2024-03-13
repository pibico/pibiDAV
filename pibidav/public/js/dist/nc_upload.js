// Copyright (c) 2024, pibiCo and Contributors
// MIT License. See license.txt

if (frappe.require) {
	frappe.require("nc_browser.bundle.js");
} else {
	frappe.ready(function () {
		frappe.require("nc_browser.bundle.js");
	});
}