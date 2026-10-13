// Copyright (c) 2022, pibiCo and contributors
// For license information, please see license.txt

frappe.ui.form.on('Folder Set', {
  select_nc_folder: function(frm) {
    frappe.require("nc_browser.bundle.js", () => new frappe.ui.pibiDocs());
  }  
});