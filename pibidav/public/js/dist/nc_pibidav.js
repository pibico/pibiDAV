// Copyright (c) 2022, pibiCo and Contributors
// MIT License. See license.txt

frappe.ui.form.on(doctype.name, {
  refresh: function(frm) {
    let nc_enable = frappe.db.get_value("PibiDAV Addon",
      {"ref_doctype": frm.doc.doctype, "ref_docname": frm.doc.name},
      ["nc_enable"]
    );
    console.log(nc_enable);
    frm.add_custom_button(__("Select NC Folder"), function() {
      frappe.db.get_value("PibiDAV Addon",
        {"ref_doctype": frm.doc.doctype, "ref_docname": frm.doc.name},
        ["name"]
      )
      .then(r => {
        var addon = r.message;
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
    frm.add_custom_button(__("Enable NC Upload"), function() {
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
    },__("NC Commands"));
    frm.add_custom_button(__("Disable NC Upload"), function() {
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
    },__("NC Commands"));
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
    if (doCreate === 'true') {
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
          console.log(values);
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