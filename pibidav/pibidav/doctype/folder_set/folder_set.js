// Copyright (c) 2022, pibiCo and contributors
// For license information, please see license.txt

frappe.ui.form.on('Folder Set', {
  refresh: function(frm) {
    if (!frm.doc.nc_enable) {
      frm.set_value("nc_folder", "");
      frm.refresh_field("nc_folder");
    }
  },
  nc_enable(frm) {
    if (frm.doc.nc_enable) {
      frm.set_value("nc_enable", 1);
      frm.refresh_field("nc_enable");
      frm.save();
      new frappe.ui.pibiDocs();
    }
  }
});
