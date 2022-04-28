## pibiDAV
pibiDAV is a Frappe App to integrate webDAV, calDAV for event calendars and cardDAV (Future Development for CardDAV) for contacts with a NextCloud Server used as a secondary repository (DMS) for a copy of Frappe Files uploaded and tagged to NextCloud on the same action of uploading a file to Frappe. The standard app only needs frappe as main framework, but it can be used with other frappe apps, such as ERPNext, etc.

## License
MIT# pibiDAV

## Requirements
Requires a Frappe server instance (refer to https://github.com/frappe/frappe), and has dependencies on CalDAV (refer to https://github.com/python-caldav/caldav) and iCalendar (refer to https://github.com/collective/icalendar). It also uses a tweaked code of pyocclient but this is embedded already in pibiDAV.

## Compatibility
PibiDAV has been tested on Frappe/ERPNext version-13 only.

## Installation
From the frappe-bench folder, execute
```
$ bench get-app pibidav https://github.com/pibico/pibidav.git
$ bench install-app pibidav
```
If you are using a multi-tenant environment, use the following command
```
$ bench --site site_name install-app pibidav
```
## Update
Run updates with
```
$ bench update
```
In case you update from the sources and observe errors, make sure to update dependencies with
```
$ bench update --requirements
```
## Features

Once is installed, be aware that you will need to set **developer_mode = 1 **on your site_config.json file. Also it is a must to have SSL active in both servers Frappe and NextCloud with specific certificates (wildcard *.domain.com certificates are not valid for this integration). Letsencrypt Certificates are valid for both servers.

This integration app is prepared for including specific and custom doctypes to upload its attachments to NextCloud at the same time than to Frappe. But for that purpose, custom fields (for Frappe Core Doctypes) or new fields in custom doctypes, are needed. These custom fields are always to be named as nc_enable, nc_folder and attachment_item, as it will be explained in next paragraphs. Also a custom script (client script) will be needed for making active the new frappe.ui.component dialog based on vue.js and called frappe.ui.pibiDocs where to draw the NextCloud Tree and select the destination NextCloud node to upload the files.

### 1. Credentials for NextCloud SuperUser, Backup and DocTypes to Integrate with NextCloud

PibiCo works on NextCloud making the Main Company Folders Superestructure as a shared folder from this NextCloud SuperUser that should be a System Manager on Frappe also. Let's explain with some pictures.

![NC_FolderStructure_Shared_from_SuperUser](https://user-images.githubusercontent.com/69711454/165801352-b4a14016-b360-41ea-9a2c-050ea589580f.JPG)

This Folder Superstructure has children at different levels and are shared with different groups or users also at different level, thus giving access to these folders and below (both user internal to Company or External such as Customers or Suppliers).

![imagen](https://user-images.githubusercontent.com/69711454/165802115-275c6234-77f5-43fa-b2aa-a1f3942e4693.png)

At this point, let's go to Frappe Server and once logged-in as System Manager or Administrator we'll go to module pibiDAV on side menu, and on Settings Card we'll choose NextCloud Settings.

![pibiDav_NC_SuperUser_Credentials_and_Settings](https://user-images.githubusercontent.com/69711454/165805974-23fcec72-04c6-4f4e-9ff0-eba250862fb5.JPG)

Once there, we'll activate the NextCloud Backup Enable checkbox and fill the credentials of the NextCloud SuperUser in the input fields.

![imagen](https://user-images.githubusercontent.com/69711454/165806449-60d1967f-9aa9-41ee-a9b9-7590ccb4896c.png)

We can check that our credentials are correct clicking on NC commands button on upper right side of the screen.

![imagen](https://user-images.githubusercontent.com/69711454/165807198-41a41df3-9a6e-447f-96fa-5ee2040190c2.png)

Now, automatic uploading of frappe backup is enabled and will be uploaded to the destination folder as given in the backups details section. Frappe Backups files are renamed on NextCloud to files beginning by a number that is the weekday of the backup files, as shown in the picture. So, we will have always the last backup and also all the ancient backups for this weekday as versions in NextCloud, as shown in the picture

![imagen](https://user-images.githubusercontent.com/69711454/165808672-33278ca8-1776-4cb4-bd0e-50ad273aa9e0.png)

It's time now of telling to Frappe which doctypes will be integrated to upload its attachments to NextCloud once they are uploaded in Frappe. This is done on the same NextCloud Settings, but on Settings Section, choosing the Frappe Doctype in the table and also giving the DocFields in that DocType that will be used to Tag Automatically the Files on Frappe and On NextCloud also. We will choose the Sales Invoice Doctype as an example for this configuration. In this case, we will tag the files with the name, the customer and the tax_id from the customer, but whichever field in the doctype, even custom fields are valid.

![imagen](https://user-images.githubusercontent.com/69711454/165810977-61e39c51-c1cf-4f75-a423-69bc174354ef.png)



