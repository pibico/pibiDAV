// Copyright (c) 2024, pibiCo and Contributors
// MIT License. See license.txt

/*
import NcBrowser from './nc_browser';

frappe.provide('frappe.ui');
frappe.ui.pibiDocs = NcBrowser;
*/

if (frappe.require) {
	frappe.require("nc_browser.bundle.js");
} else {
	frappe.ready(function () {
		frappe.require("nc_browser.bundle.js");
	});
}