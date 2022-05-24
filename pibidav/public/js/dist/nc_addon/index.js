import NcBrowserComponent from './NcBrowser.vue';

export default class Browser {
	constructor({
		wrapper,
    folder
	} = {}) {

    if (!wrapper) {
			this.make_dialog();
		} else {
			this.wrapper = wrapper.get ? wrapper.get(0) : wrapper;
		}

    let node = {}
    if (!folder) {
      node = {
        label: __("/"),
        value: "/",
        children: [],
        children_start: 0,
        children_loading: false,
        is_leaf: false,
        fetching: false,
        fetched: false,
        open: false
      } 
    } else {  
      node = {
        label: folder.slice(0, -1),
        value: folder,
        children: [],
        children_start: 0,
        children_loading: false,
        is_leaf: false,
        fetching: false,
        fetched: false,
        open: false
      }
    }
    
    this.$ncbrowser = new Vue({
			el: this.wrapper,
			render: h => h(NcBrowserComponent, {
				props: {
          node
				}
			})
		});

		this.browser = this.$ncbrowser.$children[0];

		this.browser.$watch('close_dialog', (close_dialog) => {
			if (close_dialog) {
				this.dialog && this.dialog.hide();
			}
		});

  }
  
	select_folder() {
		this.dialog && this.dialog.get_primary_btn().prop('disabled', true);
		return this.browser.select_folder();
	}

	make_dialog() {
	  this.dialog = new frappe.ui.Dialog({
		  title: __('Select NextCloud Folder'),
      size: 'large',
      primary_action_label: __('Select'),
		  primary_action: () => {
        let nc_folder = this.select_folder();
        let nc_create_folder = this.browser.ncCreateFolder;
        let secret = null;
        let share_type = null;
        if (nc_create_folder) {
          secret = this.browser.secret;
          share_type = this.browser.shareType;
        }
        let dtdn = this.wrapper.ownerDocument.body.getAttribute('data-route').replace('Form/', '');
        let pos = dtdn.lastIndexOf('/');
        let docname = dtdn.substr(pos+1);
        let doctype = dtdn.replace('/'+docname,'')
        if (nc_folder.is_folder) {
          //frappe.db.set_value(doctype, docname, 'nc_folder', nc_folder.path);
          console.log(`Create Folder: ${nc_create_folder} sharing ${share_type} with password ${secret}`);
          frappe.db.set_value(`${doctype}`, `${docname}`, {
            "nc_folder": nc_folder.path,
            //"secret": secret,
            //"sharing_option": share_type,
            //"nc_enable": 1
          });
        } else {
          frappe.msgprint(__('You have selected a file and not a folder'), nc_folder.file_name);
          return false;
        }
        
        this.dialog.hide();
        //console.log(doctype);
        if (doctype == 'Folder Set') {
          window.location.reload();
        } else {
          document.querySelector('.add-attachment-btn').click(); return false;  
        }
      }  
  	});

	  this.wrapper = this.dialog.body;
	  this.dialog.show();
	  this.dialog.$wrapper.on('hidden.bs.modal', function() {
		  $(this).data('bs.modal', null);
		  $(this).remove();
	  });
	}
}
