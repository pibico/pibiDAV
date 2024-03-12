import { createApp, watch } from "vue";
import NcBrowserComponent from './NcBrowser.vue';

class Browser {
  constructor(options = {}) {
    const { wrapper, ...componentProps } = options;
    this.initializeWrapper(wrapper);
    this.initializeVueComponent(componentProps);
  }
  //
  initializeWrapper(wrapper) {
    if (!wrapper) {
      this.make_dialog();
    } else {
      this.wrapper = wrapper.get ? wrapper.get(0) : wrapper;
    }
  }
  //
  initializeVueComponent(props) {
    const app = createApp(NcBrowserComponent, {
      show_upload_button: !this.dialog,
      ...props
    });
    this.browser = app.mount(this.wrapper);

    this.setupWatchers();
  }
  //
  setupWatchers() {
    watch(
      () => this.browser.close_dialog,
      (close_dialog) => {
        if (close_dialog) this.dialog?.hide();
      }
    );
  }
  //
  select_folder() {
    this.dialog?.get_primary_btn().prop('disabled', true);
    return this.browser.select_folder();
  }
  //
  make_dialog() {
    this.dialog = new frappe.ui.Dialog({
      title: __('Select NextCloud Folder'),
      size: 'large',
      primary_action_label: __('Select'),
      primary_action: () => this.handlePrimaryAction()
    });

    this.wrapper = this.dialog.body;
    this.dialog.show();
    this.setupDialogCleanup();
  }
  //
  handlePrimaryAction() {
    const nc_folder = this.select_folder();
    const [doctype, docname] = this.getDocumentInfo();
    if (nc_folder.is_folder) {
      frappe.db.set_value("PibiDAV Addon", `pbc_${docname}`, {
        "nc_folder": nc_folder.path,
        "nc_enable": 1
      });
    } else {
      frappe.msgprint(__('You have selected a file and not a folder'), nc_folder.file_name);
    }
    this.dialog.hide();
    this.postSelectionAction(doctype);
  }
  //
  getDocumentInfo() {
    const dtdn = this.wrapper.ownerDocument.body.getAttribute('data-route').replace('Form/', '');
    const pos = dtdn.lastIndexOf('/');
    const docname = dtdn.substr(pos + 1);
    const doctype = dtdn.replace('/' + docname, '');
    return [doctype, docname];
  }
  //
  postSelectionAction(doctype) {
    if (doctype === 'Folder Set') {
      window.location.reload();
    } else {
      document.querySelector('.add-attachment-btn').click();
    }
  }
  //
  setupDialogCleanup() {
    this.dialog.$wrapper.on('hidden.bs.modal', function() {
      $(this).data('bs.modal', null);
      $(this).remove();
    });
  }
}
//
frappe.provide("frappe.ui");
frappe.ui.pibiDocs = Browser;
export default Browser;