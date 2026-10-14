app_name = "pibidav"
app_title = "Pibidav"
app_publisher = "pibiCo"
app_description = "CalDAV and CardDAV sync and vCard tools for Frappe"
app_email = "pibico.sl@gmail.com"
app_license = "MIT"
required_apps = ["erpnext"]  # CardDAV links imported contacts to a Customer or a Supplier

app_include_icons = ["pibidav/icons/timeless/icons.svg"]

doctype_js = {
	"Contact": ["public/js/dav_contact.js"],
	"Event": ["public/js/dav_event.js"],
}
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
}

ignore_links_on_delete = ["DAV Card Link", "DAV Cal Link", "DAV Pending Contact"]

doc_events = {
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
		"pibidav.pibidav_core.audit.purge_old_entries",
		"pibidav.pibidav_cal.housekeeping.complete_past_events",
	],
}

# Personal data (GDPR download and deletion requests)
user_data_fields = [
	{"doctype": "DAV Account", "filter_by": "user"},
	{"doctype": "DAV Pending Contact", "filter_by": "user"},
	{"doctype": "DAV Audit Log", "filter_by": "user"},
]

fixtures = [{"dt": "Custom Field", "filters": {"module": ["in", ["Pibidav Core", "Pibidav Card", "Pibidav Cal"]]}}]

