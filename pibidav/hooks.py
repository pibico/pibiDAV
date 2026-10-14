app_name = "pibidav"
app_title = "Pibidav"
app_publisher = "pibiCo"
app_description = "CalDAV and CardDAV sync, vCard tools and Nextcloud files for Frappe"
app_email = "pibico.sl@gmail.com"
app_license = "MIT"
required_apps = ["erpnext"]  # Custom Fields and the Nextcloud folder buttons on Customer, Supplier, Project...

app_include_icons = ["pibidav/icons/timeless/icons.svg"]

# Nextcloud folder buttons (legacy, moves to pibidrive; invoices already moved: cloud button)
_NC_DOCTYPES = (
	"Contact",
	"Event",
	"Customer",
	"Supplier",
	"Project",
	"Sales Order",
	"Quotation",
	"Purchase Order",
	"Task",
	"Timesheet",
	"Item",
	"Employee",
)
doctype_js = {dt: ["public/js/dist/nc_pibidav.js"] for dt in _NC_DOCTYPES}
doctype_js["Contact"].append("public/js/dav_contact.js")
doctype_js["Event"].append("public/js/dav_event.js")
for _dt in ("Customer", "Supplier"):
	doctype_js[_dt].append("public/js/nc_party.js")
doctype_list_js = {"Contact": "public/js/dav_contact_list.js"}

permission_query_conditions = {
	"DAV Account": "pibidav.pibidav_core.permissions.account_query",
	"DAV Collection": "pibidav.pibidav_core.permissions.collection_query",
	"DAV Card Link": "pibidav.pibidav_core.permissions.card_link_query",
	"DAV Pending Contact": "pibidav.pibidav_core.permissions.pending_contact_query",
	"DAV Cal Link": "pibidav.pibidav_core.permissions.cal_link_query",
}

has_permission = {
	"DAV Account": "pibidav.pibidav_core.permissions.has_owner_edit_permission",
	"DAV Collection": "pibidav.pibidav_core.permissions.has_owner_edit_permission",
	"DAV Card Link": "pibidav.pibidav_core.permissions.has_owner_permission",
	"DAV Pending Contact": "pibidav.pibidav_core.permissions.has_owner_permission",
	"DAV Cal Link": "pibidav.pibidav_core.permissions.has_owner_permission",
	"PibiDAV Addon": "pibidav.pibidav.doctype.pibidav_addon.pibidav_addon.has_permission",
}

ignore_links_on_delete = ["DAV Card Link", "DAV Cal Link", "DAV Pending Contact"]

doc_events = {
	"File": {"after_insert": ["pibidav.pibidav.custom.upload_file_to_nc"]},
	"User": {"on_update": ["pibidav.pibidav_core.doctype.dav_account.dav_account.disable_accounts_of_user"]},
	"Contact": {"on_trash": ["pibidav.pibidav_card.sync.on_contact_trash"]},
	"Event": {
		"on_update": ["pibidav.pibidav_cal.sync.on_event_update"],
		"on_trash": ["pibidav.pibidav_cal.sync.on_event_trash"],
	},
}

scheduler_events = {
	"cron": {
		"*/5 * * * *": ["pibidav.pibidav_core.engine.run_due_syncs"]
	},
	"daily": [
		"pibidav.pibidav.doctype.nextcloud_settings.nextcloud_settings.daily_backup",
		"pibidav.pibidav_core.audit.purge_old_entries",
		"pibidav.pibidav_cal.housekeeping.complete_past_events",
	],
	"weekly": ["pibidav.pibidav.doctype.nextcloud_settings.nextcloud_settings.weekly_backup"],
}

# Personal data (GDPR download and deletion requests)
user_data_fields = [
	{"doctype": "DAV Account", "filter_by": "user"},
	{"doctype": "DAV Pending Contact", "filter_by": "user"},
	{"doctype": "DAV Audit Log", "filter_by": "user"},
]

fixtures = [{"dt": "Custom Field", "filters": {"module": ["like", "Pibidav"]}}]

treeviews = ["Folder Set"]
