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
##Features

Once is installed, be aware that you will need to set **developer_mode = 1 **on your site_config.json file. Also it is a must to have SSL active in both servers Frappe and NextCloud with specific certificates (wildcard *.domain.com certificates are not valid for this integration). Letsencrypt Certificates are valid for both servers.

This integration app is prepared for including specific and custom doctypes to upload its attachments to NextCloud at the same time than to Frappe. But for that purpose, custom fields (for Frappe Core Doctypes) or new fields in custom doctypes, are needed. These custom fields are always to be named as nc_enable, nc_folder and attachment_item, as it will be explained in next paragraphs. Also a custom script (client script) will be needed for making active the new frappe.ui.component dialog based on vue.js and called frappe.ui.pibiDocs where to draw the NextCloud Tree and select the destination NextCloud node to upload the files.

### 1. Credentials for NextCloud SuperUser

PibiCo works on NextCloud making the Main Company Folders Superestructure as a shared folder from this NextCloud SuperUser that should be a System Manager on Frappe also. Let's explain with some pictures.
