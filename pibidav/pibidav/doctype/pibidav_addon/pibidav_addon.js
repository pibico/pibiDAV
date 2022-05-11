// Copyright (c) 2022, pibiCo and contributors
// For license information, please see license.txt

frappe.ui.form.on('PibiDAV Addon', {
  refresh(frm) {
    frm.add_custom_button(__("Refresh Files List"), function() {
      frappe.call({
        method: "pibidav.pibidav.custom.update_attachment_item",
        args: {
          dt: frm.doc.ref_doctype,
          dn: frm.doc.ref_docname,
        }
      }).then(function(r) {
        frappe.msgprint(r.message);
        window.location.reload();
      });
    }).addClass('btn-primary');
  }
});
