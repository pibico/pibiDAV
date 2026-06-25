frappe.ui.form.on(cur_frm.doctype, {
    refresh: function (frm) {
        if (!frm.doc.__islocal) {
            managePibiDAVAddon(frm);
        }
    },
    after_save: function (frm) {
        handleAfterSave(frm);
    }
});
// Function to manage PibiDAV Addon buttons and actions
function managePibiDAVAddon(frm) {
    frappe.db.get_value(
        "PibiDAV Addon",
        { ref_doctype: frm.doc.doctype, ref_docname: frm.doc.name },
        ["nc_enable"]
    ).then(r => {
        const nc_enable = r.message?.nc_enable || 0;
        if (nc_enable !== 1) {
            addNextCloudEnableButton(frm);
        } else {
            addNextCloudButtons(frm);
        }
    });
}
// Add Enable NextCloud Button
function addNextCloudEnableButton(frm) {
    frm.add_custom_button(frappe.utils.icon('nextcloud', 'md'), function () {
        handleEnableNextCloud(frm);
    })
        .addClass("btn btn-primary")
        .attr('title', __('Enable NextCloud'));
}
// Add Buttons for Upload, Check, and Disable NextCloud
function addNextCloudButtons(frm) {
    frm.add_custom_button(__("Upload to NC"), function () {
        handleUploadToNextCloud(frm);
    }, __("NC"));

    frm.add_custom_button(__("Check Addon"), function () {
        handleCheckAddon(frm);
    }, __("NC"));

    frm.add_custom_button(frappe.utils.icon('nextcloud', 'md'), function () {
        handleDisableNextCloud(frm);
    })
        .addClass("btn btn-danger")
        .attr('title', __('Disable NextCloud'));
}
// Handle enabling NextCloud
function handleEnableNextCloud(frm) {
    processNextCloudEnable(frm);
}
// Process enabling NextCloud
function processNextCloudEnable(frm, addon) {
    const nc_parent_folder = frm.doc.nc_parent_folder || '';

    frappe.call({
        method: 'pibidav.pibidav.custom.enable_nc_addon',
        args: {
            dt: frm.doc.doctype,
            dn: frm.doc.name,
            nc_parent_folder: nc_parent_folder
        },
        callback: function (r) {
            if (r.message) {
                console.log("DEBUG enable_nc_addon result:", r.message);
            }
            location.reload();
        }
    });
}
// Handle uploading to NextCloud
function handleUploadToNextCloud(frm) {
    frappe.db.get_value(
        "PibiDAV Addon",
        { ref_doctype: frm.doc.doctype, ref_docname: frm.doc.name },
        ["name", "nc_folder", "nc_folder_internal_link"]
    ).then(r => {
        const addon = r.message || {};
        if (addon.name) {
            openNextCloudBrowser(addon);
        } else {
            createAddon(frm, () => openNextCloudBrowser({}));
        }
    });
}
// Handle checking the Addon
function handleCheckAddon(frm) {
    frappe.db.get_value(
        "PibiDAV Addon",
        { ref_doctype: frm.doc.doctype, ref_docname: frm.doc.name },
        ["name"]
    ).then(r => {
        const addon = r.message || {};
        if (addon.name) {
            frappe.set_route("Form", "PibiDAV Addon", addon.name);
        } else {
            createAddon(frm, pibidav => {
                frappe.set_route("Form", "PibiDAV Addon", pibidav.name);
            });
        }
    });
}
// Handle disabling NextCloud
function handleDisableNextCloud(frm) {
    frappe.db.set_value("PibiDAV Addon", `pbc_${frm.doc.name}`, { nc_enable: 0 })
        .then(() => location.reload());
}
// Create or Update Addon with Folder
function createOrUpdateAddonWithFolder(frm, addon) {
    const docname = frm.doc.name;
    const nc_parent_folder = frm.doc.nc_parent_folder;
    const addonName = addon.name || `pbc_${docname}`;
    
    frappe.db.set_value("PibiDAV Addon", addonName, {
        nc_enable: 1,
        nc_folder_internal_link: nc_parent_folder
    }).then(() => {
        fetchAndSetFolderPath(nc_parent_folder, addonName);
    });
}
// Create or Update Addon without Folder
function createOrUpdateAddonWithoutFolder(frm, addon) {
    const docname = frm.doc.name;
    const addonName = addon.name || `pbc_${docname}`;

    frappe.db.set_value("PibiDAV Addon", addonName, { nc_enable: 1 })
        .then(() => location.reload());
}
// Fetch and Set Folder Path
function fetchAndSetFolderPath(folderLink, addonName) {
    const fileId = extractFileId(folderLink);
    console.log("DEBUG fetchAndSetFolderPath: folderLink =", folderLink);
    console.log("DEBUG fetchAndSetFolderPath: extracted fileId =", fileId);
    console.log("DEBUG fetchAndSetFolderPath: addonName =", addonName);

    frappe.db.get_value("PibiDAV Addon", addonName, "nc_folder").then(result => {
        const currentFolder = result.message.nc_folder;
        console.log("DEBUG fetchAndSetFolderPath: currentFolder =", currentFolder);

        // Check if nc_folder is already filled with a valid path (starts with /)
        if (currentFolder && currentFolder.trim() !== "" && currentFolder.startsWith("/")) {
            console.log("DEBUG: Folder path already set, reloading");
            location.reload();
        } else {
          console.log("DEBUG: Calling get_folder_path_from_link with fileId =", fileId);
          // If not filled or contains error, proceed to fetch and set the folder path
          frappe.call({
            method: 'pibidav.pibidav.custom.get_folder_path_from_link',
            args: { fileid: fileId },
            callback: function (r) {
                console.log("DEBUG fetchAndSetFolderPath: response =", r.message);
                console.log("DEBUG fetchAndSetFolderPath: exc =", r.exc);
                if (!r.exc && r.message && r.message.startsWith("/")) {
                    console.log("DEBUG: Setting nc_folder to", r.message);
                    frappe.db.set_value("PibiDAV Addon", addonName, {
                        nc_folder: r.message
                    }).then(() => location.reload());
                } else {
                    console.log("DEBUG: Failed - message:", r.message, "exc:", r.exc);
                    frappe.msgprint(__('Failed to fetch folder path.'));
                    location.reload();
                }
            }
          });
        }
    });
}
// Open NextCloud Browser
function openNextCloudBrowser(addon) {
    // Use nc_folder if it's a valid path, otherwise start at root
    const ncFolder = addon.nc_folder;
    const targetFolder = (ncFolder && ncFolder.startsWith("/")) ? ncFolder : '/';

    new frappe.ui.pibiDocs({
        targetFolder: targetFolder,
        root_folder: "/"
    });
}
// Create Addon
function createAddon(frm, callback) {
    frappe.db.insert({
        doctype: "PibiDAV Addon",
        ref_doctype: frm.doc.doctype,
        ref_docname: frm.doc.name,
        nc_enable: 1
    }).then(callback);
}
// Handle After Save
function handleAfterSave(frm) {
    frappe.db.get_list("PibiDAV Addon", {
        filters: { ref_doctype: frm.doc.doctype, ref_docname: frm.doc.name },
        fields: ["nc_enable", "nc_folder_internal_link"]
    }).then(res => {
        const addon = res[0] || {};
        if (!addon.nc_folder_internal_link && addon.nc_enable) {
            createFolderDialog(frm);
        }
    });
}
// Create Folder Dialog
function createFolderDialog(frm) {
    frappe.call({
        method: "pibidav.pibidav.custom.doCreateFolder",
        args: { doctype: frm.doc.doctype }
    }).then(r => {
        if (r.message) {
            openFolderCreationDialog(frm, r.message);
        }
    });
}
// Open Folder Creation Dialog
function openFolderCreationDialog(frm, doCreate) {
    const defaultData = getDefaultFolderData(frm);
    if (doCreate) {
        const d = new frappe.ui.Dialog({
            title: __('Create NC Folder'),
            fields: getFolderDialogFields(defaultData),
            primary_action_label: 'Create',
            primary_action(values) {
                if (!values.abbreviation || !values.strmain || !values.folder_set) {
                    frappe.throw(__('Complete all data: Abbreviation, Folder Name, and Folder Set'));
                }
                createNextCloudFolder(frm, values);
                d.hide();
            }
        });
        d.show();
    }
}
// Utility Functions
function extractFileId(htmlString) {
    const regex = /\/f\/(\d+)/;
    const match = htmlString.match(regex);
    return match ? match[1] : null;
}
//
function getDefaultFolderData(frm) {
    if (frm.doc.doctype === 'Customer') {
        return {
            folder_name: frm.doc.customer_name,
            abbreviation: frm.doc.pb_abbreviation,
            folder_set: '(CLI) Plantilla Clientes'
        };
    } else if (frm.doc.doctype === 'Supplier') {
        return {
            folder_name: frm.doc.supplier_name,
            abbreviation: frm.doc.pb_abbreviation,
            folder_set: '(PRO) Plantilla Proveedores'
        };
    }
    return {};
}
//
function getFolderDialogFields(defaultData) {
    return [
        { label: __('Enter Abbreviation'), fieldname: 'abbreviation', fieldtype: 'Data', default: defaultData.abbreviation },
        { label: __('Enter Folder Name'), fieldname: 'strmain', fieldtype: 'Data', default: defaultData.folder_name },
        { label: __('Select Folder Set'), fieldname: 'folder_set', fieldtype: 'Link', options: 'Folder Set', filters: { parent_folder_set: '' }, default: defaultData.folder_set },
        { label: __('Sharing Option'), fieldname: 'sharing_option', fieldtype: 'Select', options: ['', '4-Upload Only', '17-Read Only', '31-Upload and Edit'] },
        { label: __('Sharing Password'), fieldname: 'secret', fieldtype: 'Data' }
    ];
}
//
function createNextCloudFolder(frm, values) {
    frappe.call({
        method: "pibidav.pibidav.custom.create_nc_folder",
        args: {
            dt: frm.doc.doctype,
            dn: frm.doc.name,
            abbr: values.abbreviation,
            strmain: values.strmain,
            folder_set: values.folder_set,
            sharing_option: values.sharing_option,
            secret: values.secret || ""
        }
    }).then(r => {
        frappe.msgprint(r.message);
    });
}