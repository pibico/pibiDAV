// Copyright (c) 2024, pibiCo and Contributors
// MIT License. See license.txt

frappe.ui.form.on(cur_frm.doctype, {
  refresh: function(frm) {
    // if doctype is saved
    if (!frm.doc.__islocal) {
      frappe.db.get_value("PibiDAV Addon",
        {"ref_doctype": frm.doc.doctype, "ref_docname": frm.doc.name},
        ["nc_enable"]
      ).then(r => {
        let nc_enable = r.message.nc_enable;
        //console.log(r);
        if (nc_enable !== 1) { 
          frm.add_custom_button(__("Enable NC"), function() {
            frappe.db.get_value("PibiDAV Addon",
              {"ref_doctype": frm.doc.doctype, "ref_docname": frm.doc.name},
              ["name"]
            )
            .then(r => {
              var addon = r.message;
              let docname = frm.doc.name
              if (addon.name == 'pbc_' + docname) {
                frappe.db.set_value("PibiDAV Addon", `pbc_${docname}`, {"nc_enable": 1});    
              } else {
                frappe.db.insert({
                  "doctype": "PibiDAV Addon",
                  "ref_doctype": frm.doc.doctype,
                  "ref_docname": frm.doc.name,
                  "nc_enable": 1
                }).then(function(doc) {
                  console.log(`${doc.name} created on ${doc.creation}`)
                });
              }
            });
            window.setTimeout(function(){location.reload()},300)
          }).addClass("btn btn-primary");
        } else {
          // Button to upload to NC
          frm.add_custom_button(__("Upload to NC"), function() {
            frappe.db.get_value("PibiDAV Addon",
              {"ref_doctype": frm.doc.doctype, "ref_docname": frm.doc.name},
              ["name","nc_folder"]
            )
            .then(r => {
              var addon = r.message;
              //console.log(addon);
              if (addon.name == "pbc_" + frm.doc.name) {
                new frappe.ui.pibiDocs;      
              } else {
                frappe.db.insert({
                  "doctype": "PibiDAV Addon",
                  "ref_doctype": frm.doc.doctype,
                  "ref_docname": frm.doc.name,
                  "nc_enable": 1
                }).then(function(doc) {
                  console.log(`${doc.name} created on ${doc.creation}`)
                  new frappe.ui.pibiDocs;
                });
              }
            });
          },__("NC Commands"));
          // Button to check addon
          frm.add_custom_button(__("Check Addon"), function() {
            frappe.db.get_value("PibiDAV Addon",
              {"ref_doctype": frm.doc.doctype, "ref_docname": frm.doc.name},
              ["name"]
            )
            .then(r => {
              var addon = r.message;
              if (addon.name == "pbc_" + frm.doc.name) {
                frappe.set_route("Form", "PibiDAV Addon", addon.name);
              } else {
                frappe.db.insert({
                  "doctype": "PibiDAV Addon",
                  "ref_doctype": frm.doc.doctype,
                  "ref_docname": frm.doc.name,
                  "nc_enable": 1
                }).then(function(pibidav) {
                  frappe.set_route("Form", "PibiDAV Addon", pibidav.name);
                });
              }
            });
          },__("NC Commands"));
          // Button to disable NC
          frm.add_custom_button(__("Disable NC"), function() {
            frappe.db.get_value("PibiDAV Addon",
              {"ref_doctype": frm.doc.doctype, "ref_docname": frm.doc.name},
              ["name"]
            )
            .then(r => {
              var addon = r.message;
              let docname = frm.doc.name
              if (addon.name == 'pbc_' + docname) {
                frappe.db.set_value("PibiDAV Addon", `pbc_${docname}`, {"nc_enable": 0});    
              } else {
                frappe.db.insert({
                  "doctype": "PibiDAV Addon",
                  "ref_doctype": frm.doc.doctype,
                  "ref_docname": frm.doc.name,
                  "nc_enable": 0
                }).then(function(doc) {
                  console.log(`${doc.name} created on ${doc.creation}`)
                });
              }
            });
            window.setTimeout(function(){location.reload()},300)
          }).addClass("btn btn-danger");
        }  
      });
    }
  },
  after_save: function(frm) {
    frappe.db.get_list('PibiDAV Addon',
      { filters: { 'ref_doctype': frm.doc.doctype, 'ref_docname': frm.doc.name },
      fields: ['nc_enable', 'nc_folder_internal_link'] }
    ).then(res => {
      if (res.length > 0) {
        if (res[0].nc_folder_internal_link != '' ) {
          console.log(res[0].nc_folder_internal_link);
        } else {
          if (res[0].nc_enable) {
            CreateFolder(frm);
          }
        }  
      } else {
        CreateFolder(frm);
      }
    });
  }
});
function CreateFolder(frm) {
  frappe.call({
    method: "pibidav.pibidav.custom.doCreateFolder",
    args: {
      doctype: frm.doc.doctype
    }
  }).then(function(r) {
    let doCreate = r.message;
    //console.log(doCreate);
    if (doCreate) {
      let d = new frappe.ui.Dialog({
        title: 'Create NC Folder',
        fields: [
          {
            label: (__('Enter Abbreviation')),
            fieldname: 'abbreviation',
            fieldtype: 'Data'
          },
          {
            label: (__('Enter Folder Name')),
            fieldname: 'strmain',
            fieldtype: 'Data'
          },
          {
            label: (__('Select Folder Set')),
            fieldname: 'folder_set',
            fieldtype: 'Link',
            options: 'Folder Set',
            filters: {'parent_folder_set': ''}
          },
          {
            label: (__('Sharing Option')),
            fieldname: 'sharing_option',
            fieldtype: 'Select',
            options: ['','4-Upload Only','17-Read Only','31-Upload and Edit']
          },
          {
            label: (__('Sharing Password')),
            fieldname: 'secret',
            fieldtype: 'Data'
          }
        ],
        primary_action_label: 'Create',
        primary_action(values) {
          //console.log(values);
          if (values.abbreviation === undefined || values.strmain === undefined || values.folder_set === undefined){
            frappe.throw(__('Complete all data Abbreviation, Folder Name and Folder Set'));
            return false;
          }
          let secret = ''
          if (values.secret !== undefined) {
            secret = values.secret;
          }
          if (secret.length > 0 && secret.length < 10){
            frappe.throw(__('Sharing password must be greater than 10 chars long and not usual'));
            return false;
          }
          frappe.call({
            method: "pibidav.pibidav.custom.create_nc_folder",
            args: {
              dt: frm.doc.doctype,
              dn: frm.doc.name,
              abbr: values.abbreviation,
              strmain: values.strmain,
              folder_set: values.folder_set,
              sharing_option: values.sharing_option,
              secret: secret
            }
          }).then(function(r) {
            frappe.msgprint(r.message);
          });
          d.hide();
        }
      });
      d.show();
    }
  });
};