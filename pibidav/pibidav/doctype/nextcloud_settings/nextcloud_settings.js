// Copyright (c) 2022, pibiCo and contributors
// For license information, please see license.txt

frappe.ui.form.on('NextCloud Settings', {
  refresh: function(frm) {
    if (frm.doc.nc_backup_enable && frm.doc.nc_backup_url && frm.doc.nc_backup_username && frm.doc.nc_backup_token) {
      // add check credentials button
      frm.add_custom_button(__("Check Credentials"), function() {
        frappe.call({
          method: "pibidav.pibidav.custom.check_nextcloud",
          args: {
            doc: frm.doc
          }
        });
      },__("NC Commands"));
      // add backup button 
    	frm.add_custom_button(__("Backup Now"), function() {
				frappe.call({
					method: "pibidav.pibidav.doctype.nextcloud_settings.nextcloud_settings.take_backup",
					freeze: true
				});
			}).addClass("btn-primary");
		}
    // Fill DocType Included with Data From Reference Item Table
    var includeArr = frm.doc.reference_item;
    var inclusion = '';
    for (var i=0; i<includeArr.length; i++) {
      inclusion += includeArr[i].reference_doctype+',';
    }
    frm.doc.nc_doctype_included = inclusion.slice(0,-1);
    frm.refresh_field('nc_doctype_included');
  }
});