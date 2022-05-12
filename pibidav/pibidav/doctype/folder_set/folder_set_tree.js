// Copyright (c) 2022, pibiCo and contributors
// For license information, please see license.txt

frappe.provide("frappe.treeview_settings");
frappe.provide('frappe.views');

frappe.treeview_settings['Folder Set'] = {
  breadcrumbs: "Templates",
  title: __('Folder Set'),
  get_tree_root: false,
  root_label: "",
  get_tree_nodes: 'pibidav.pibidav.doctype.folder_set.folder_set.get_children',
  filters: [
		{
			fieldname: "root_parent",
			fieldtype: "Link",
			options: "Folder Set",
			label: __("Tree"),
			default: "BPJ Big Project",
			get_query: function() {
        var args = [
          ["Folder Set", 'is_group', '=', 1],
					["Folder Set", 'parent_folder_set', '=', '']
        ];
				return {filters: args};
			}
		}
  ], 
  post_render: function(treeview) {
	  treeview.args['is_group'] = 1; 
  },
  extend_toolbar: false,
  toolbar: [
    {
		  label:__("Edit"),
			condition: function(node) {
        var me = frappe.views.trees['Folder Set'];
			  return !node.is_root && me.can_read;
		  },
			click: function(node) {
        var me = frappe.views.trees['Folder Set'];
			  frappe.set_route("Form", me.doctype, node.label);
			}
		},
	  {
		  label:__("Add Child"),
		  condition: function(node) {
			  var me = frappe.views.trees['Folder Set'];
			  if (me.can_create && node.expandable && !node.hide_add) {
				  try {
            if (node.parent_node.hide_add) { node.hide_add = true; }
          }
          catch (e) {  }
				}
			  return me.can_create && node.expandable && !node.hide_add;
		  },
		  click: function(node) {
			  var me = frappe.views.trees['Folder Set'];
			  me.new_node();
		  }//,
		  //btnClass: "hidden-xs"
	  },
	  {
		  label:__("Delete"),
		  async: false,
		  condition: function(node) {
			  var allow_delete = true;
			  var me = frappe.views.trees['Folder Set'];
			  try { if (node.parent_node.hide_add) { allow_delete = false; }
			  } catch (e) {  }
			    if (allow_delete && me.can_delete && !node.is_root && !node.hide_add && node.expandable) {
				    frappe.call({ 
    			    method: 'frappe.client.get_value',
    				  args: {
        		    'doctype': 'Folder Set',
        			  'filters': {'parent_folder_set' : node.label},
        			  'fieldname': [ 'name' ]
    				  },
					    async: false,
    				  callback: function(r) {
					      if (!r.exc) {
						      if (r.message.name && r.message.name !="" && r.message.name != null) allow_delete = false;
						      return allow_delete;
					      }
    				  }
				    });
			    }
			    return allow_delete && me.can_delete && !node.is_root && !node.hide_add;
		    },
		    click: function(node) {
			    var me = frappe.views.trees['Folder Set'];
			    frappe.model.delete_doc(me.doctype, node.label, function() {
				    node.parent.remove();
			    });
		    }//,
	    //btnClass: "hidden-xs"
	   },
     {
		   label:__("Recreate"),
       condition: function(node) {
			  var allow_create = true;
			  var me = frappe.views.trees['Folder Set'];
			  if (node.is_root) { allow_create = false; }
		    return allow_create && !node.is_root && !node.hide_add;
		   },   
       click: function(node) {
         var upload2nc = true;
         frappe.db.get_value('Folder Set', {'name': node.title}, 'nc_folder', (r) => {
           let nc_folder = r.nc_folder;
           if (nc_folder) {
              frappe.call({
                method: "pibidav.pibidav.custom.checkNCuser",
                args: {
                }
              }).then(function(r) {
                let isUser = r.message;
                if (isUser) {
                  let d = new frappe.ui.Dialog({
                    title: __("Recreate Folders in NC"),
                    fields: [
			                { label: __("Parent Path"), fieldname: "parent_path", fieldtype: "Data", default: nc_folder},
			                { label: __("Abbreviation"), fieldname: "abbreviation", fieldtype: "Data", default: "PRJYYABV"},
				              { label: __("Root Dir Name"), fieldname: "folder_name", fieldtype: "Data"},
                      { label: __("Digits to substitute with abbreviation"), fieldname: "digits", fieldtype: "Int", default: 3}
               ],
                    primary_action_label: __("Create"),
                    primary_action(values) {
				              //console.log(values);
				              frappe.call({
				                method: "pibidav.pibidav.custom.create_nc_dirs",
				                args: {
					                node_name: node.title,
                          path: values.parent_path,
                          abbrv: values.abbreviation,
                          strmain: values.folder_name,
                          digits: values.digits
				                },
                        callback: function(r) {
                          console.log(r.message);
                        }					   
				              });
				              d.hide();
                    }
                  });
		              d.show();
                } else {
                  frappe.msgprint(__("Only NextCloud SuperUser can use this method"));
                }
              });  
           } else {
             frappe.msgprint(__("First Select your NC Destination Folder"));
           }
         });
		   }//,
		  //btnClass: "hidden-xs"
	   }  
   ]
}

