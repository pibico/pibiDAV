## pibiDAV
pibiDAV is a Frappe App to integrate webDAV, calDAV and cardDAV (Future) with a NextCloud Server used as (DMS) for a copy of Frappe Files uploaded and tagged to NextCloud while uploading files to Frappe.
## License
MIT# pibiDAV
## Requirements
Requires a Frappe server instance (refer to https://github.com/frappe/frappe), and has dependencies on CalDAV (refer to https://github.com/python-caldav/caldav) and iCalendar (refer to https://github.com/collective/icalendar). It also uses a tweaked code of pyocclient but this is embedded already in pibiDAV.
## Compatibility
PibiDAV has been tested on Frappe/ERPNext version-13 only.
## Installation
From the frappe-bench folder, execute
```
$ bench get-app pibidav --branch develop https://github.com/pibico/pibidav.git
$ bench install-app pibidav
```
If you are using a multi-tenant environment, use the following command
```
$ bench --site site_name install-app pibidav
```
## Features
Once is installed, be aware that you will need to set **developer_mode = 1** on your site_config.json file. Also it is a must to have SSL active in both servers Frappe and NextCloud with specific certificates (wildcard *.domain.com* certificates are not valid for this integration). Letsencrypt Certificates are valid for both servers. 
This integration app is prepared for including specific and custom doctypes to upload its attachments to NextCloud at the same time than to Frappe. There is a new frappe.ui.component dialog based on vue.js and called frappe.ui.pibiDocs where to draw the NextCloud Tree and select the destination NextCloud node to upload the files.
### 1. Credentials for NextCloud SuperUser, Backup and DocTypes to Integrate with NextCloud
PibiCo works on NextCloud making the Main Company Folders Superestructure as a shared folder from this NextCloud SuperUser that should be a System Manager on Frappe also. Let's explain with some pictures.
![NC_FolderStructure_Shared_from_SuperUser](https://user-images.githubusercontent.com/69711454/165801352-b4a14016-b360-41ea-9a2c-050ea589580f.JPG)
This Folder Superstructure has children at different levels and are shared with different groups or users also at different level, thus giving access to these folders and below (both user internal to Company or External such as Customers or Suppliers).
![imagen](https://user-images.githubusercontent.com/69711454/165802115-275c6234-77f5-43fa-b2aa-a1f3942e4693.png)
At this point, let's go to Frappe Server and once logged-in as System Manager or Administrator we'll go to module pibiDAV on side menu, and on Settings Card we'll choose NextCloud Settings.
![pibiDav_NC_SuperUser_Credentials_and_Settings](https://user-images.githubusercontent.com/69711454/165805974-23fcec72-04c6-4f4e-9ff0-eba250862fb5.JPG)
Once there, we'll activate the NextCloud Enable checkbox (valid also for backup) and fill the credentials of the NextCloud SuperUser in the input fields.
![imagen](https://user-images.githubusercontent.com/69711454/168047648-0c131b17-ba4e-4f77-af4e-8207d0050159.png)
We can check that our credentials are correct clicking on NC commands button on upper right side of the screen.
![imagen](https://user-images.githubusercontent.com/69711454/165807198-41a41df3-9a6e-447f-96fa-5ee2040190c2.png)
Now, automatic uploading of frappe backup is enabled and will be uploaded to the destination folder as given in the backups details section. Frappe Backups files are renamed on NextCloud to files beginning by a number that is the weekday of the backup files, as shown in the picture. So, we will have always the last backup and also all the ancient backups for this weekday as versions in NextCloud, as shown in the picture
![imagen](https://user-images.githubusercontent.com/69711454/165808672-33278ca8-1776-4cb4-bd0e-50ad273aa9e0.png)
It's time now of telling to Frappe which doctypes will be integrated to upload its attachments to NextCloud once they are uploaded in Frappe. This is done on the same NextCloud Settings, but on Settings Section, choosing the Frappe Doctype in the table and also giving the DocFields in that DocType that will be used to Tag Automatically the Files on Frappe and On NextCloud as well. We will choose the Sales Invoice Doctype as an example for this configuration. In this case, we will tag the files with the name, the customer and the tax_id from the customer, but whichever field in the doctype, even custom fields are valid.
![imagen](https://user-images.githubusercontent.com/69711454/168048312-ecb71229-8937-4fe3-bfe2-fdcac6dd5fc1.png)
### 2. Credentials for each Frappe User to Use his NextCloud Account Credentials
To get the permissions from NextCloud into Frappe we will fill the User NextCloud Credentials on Frappe User Settings. We'll go through the user settings and will select the Role NextCloud User first.
![imagen](https://user-images.githubusercontent.com/69711454/165817057-d765dd68-ae4f-4ab9-9edf-2fa438a0d012.png)
After that we will go at the bottom of de User Settings Form to provide the NextCloud User Credentials. In this example is the System Manager or Administrator having the SuperUser NextCloud Credentials for having access to the full NextCloud Folder SuperStructure.
![imagen](https://user-images.githubusercontent.com/69711454/165817406-eeb6fc05-3fa7-4e14-8798-3712c4a2b26c.png)
For CalDAV integration we will provide also the url for the User Calendars, in the way https://domain.com/remote.php/dav/principals/ (do not forget the / at the end).
### 3. Hooks for NextCloud Integration
Provide we have access to the frappe-bench folder, we must hook with the Doctypes included in the integration, on adding the following to hooks.py of pibidav app:
```
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

nc_list = ["Customer","Project","Sales Invoice","Purchase Invoice","Supplier","Event"]
doctype_js = {}
for item in nc_list:
  doctype_js[item] = "public/js/dist/nc_pibidav.js"

# Home Pages
# ----------
```
In nc_list variable, we will include whichever doctype to integrate with NextCloud.
#### 2.1 PibiDAV Addon DocType
This new DocType is an extension of existing DocTypes to fill with data related to Attchments, Folders, etc. related to NextCloud based on its referenced doctype. It is somehow a parallel sheet with data only related to NextCloud Functionalities. It is filled automatically from the different actions derived from NC buttons.
![imagen](https://user-images.githubusercontent.com/69711454/168050089-1f6a7f44-52a8-4d27-ae64-2c94775a17f3.png)
### 4. The magic of the NextCloud Integration inside Frappe
It's time now to try the integration of the NextCloud Folder Structure from Frappe to choose the NC Destination Folder of our uploaded files (except website urls).
Let's go to a doctype of the NC Integration List, i.e. a Sales Invoice. On this core doctype, we'll have two new buttons, for enabling NC and for getting the browser dialog to choose the NC destination folder.
![imagen](https://user-images.githubusercontent.com/69711454/168051235-2f762d9e-30a4-476e-83c8-e8345ca2dd4f.png)
First of all, we must enable the NC Integration, clicking on Enable NC button. With this action we will generate the pbc_sales_invoice doctype parallel to our sales invoice (same name with 'pbc_' before it).
![imagen](https://user-images.githubusercontent.com/69711454/168051867-32eeaeda-0d05-4525-935f-b464a6cb7a06.png)
We can check the created Addon clicking on the Check Addon Button. And return to the sales invoice clicking on the ref_docname on the addon.
![imagen](https://user-images.githubusercontent.com/69711454/168052040-b623d8ef-7d4c-4135-8497-ba412e730023.png)
After having saved the original Sales Invoice as draft we can select the NextCloud Destination Folder for our attachments by clicking on the NC Commands Button and selecting Select NC Folder to bring the pop-up dialog for browsing and selecting our NC Folder.
![imagen](https://user-images.githubusercontent.com/69711454/168052743-ac2bec03-915e-47de-82a7-2e62996b1d64.png)


When we select the NextCloud Destination Folder in the dialog, this folder path will be filled in our text nc_folder custom field.
![imagen](https://user-images.githubusercontent.com/69711454/165823241-63c5cace-f68e-4a11-9a40-7ab27b0a6d96.png)
While we keep this destination folder, all the attachments uploaded to the Sales Invoice will be also uploaded to NextCloud to this folder. Let's create the pdf from the Sales Invoice, signed electronically outside Frappe and uploaded again as attachment in Frappe/ERPNext
![imagen](https://user-images.githubusercontent.com/69711454/165823914-8dd352e1-69ce-4698-851e-33f53dadb3e2.png)
We have uploaded the attachment to Frappe/ERPNext as shown in the picture
![imagen](https://user-images.githubusercontent.com/69711454/165824171-d145445b-9c87-4740-b48d-494ef116c26b.png)
Let's Check if it has been also uploaded to NextCloud on the PBC > Customer > Client > Invoices > 2022 as selected.
![imagen](https://user-images.githubusercontent.com/69711454/165824625-0d650e18-0c94-4c9e-be7e-7577b1d10968.png)
Looking for details we see the pdf file Sales Invoice uploaded in NextCloud Destination, but also has been created a shared public Link, tagged with customer, tax_id, doctype and name as we defined in the Settings. Voilà, first integration achieved. Let's check the File uploaded to Frappe, it has all metadata from NextCloud as well, and also has some frappe tags also automatically filled on the upload.
![imagen](https://user-images.githubusercontent.com/69711454/165825969-f883e0d4-b415-4eba-9885-16ed92073276.png)
### 5. Create folder structures in NextCloud from template Folder Sets in Frappe.
Another possible integration is through a Folder Set Doctype Tree integrated in pibiDav. Folder Set is a Doctype for making Folder Structures taken as templates for recreating them in the NextCloud Instance from a destination folder as root. Let's see in action, once we have the template folder set created in Frappe. We can select the root folder and enable the nc_enable check and select the destination folder in NextCloud where to recreate this structure, renaming the folders in NextCloud upon its creation.
![imagen](https://user-images.githubusercontent.com/69711454/165839794-602f4e5c-3e7d-4350-9a12-fa16c31bb75b.png)
We select the destination folder in NextCloud browsing in the dialog.
![imagen](https://user-images.githubusercontent.com/69711454/165840960-bb937ec7-9b2b-491d-94b4-4d9df0374c8e.png)
And once selected the destination folder, on the tree we click on button Recreate to perform the copy of folders from Frappe to NextCloud.
![imagen](https://user-images.githubusercontent.com/69711454/165841213-d50cd3e1-089e-4106-a997-c9188a2eeef0.png)
The result is seen on the image for a new Client Structure called CUSTOMER as abbreviation and Customer Name Details as Description for the Folder.
![imagen](https://user-images.githubusercontent.com/69711454/165841463-62829c06-e4f6-4e13-ae3e-49d5bbe67fee.png)
![imagen](https://user-images.githubusercontent.com/69711454/165841656-f5b458d8-b15d-47ff-8738-bafe8c5bd08a.png)
### 6. CalDAV integration with Calendar App in NextCloud.
This portion is explained in pibiCal (refer to https://github.com/pibico/pibical/tree/version-13) The code from pibiCal has been integrated into pibiDav to achieve the syncronization between Frappe and NextCloud CalDAV Server.





