from . import __version__ as app_version

app_name = "pibidav"
app_title = "Pibidav"
app_publisher = "pibiCo"
app_description = "WebDAV, CalDAV and CardDAV Integration between Frappe and NextCloud"
app_icon = "octicon octicon-file-directory"
app_color = "grey"
app_email = "pibico.sl@gmail.com"
app_license = "MIT"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/pibidav/css/pibidav.css"
app_include_js = "/assets/pibidav/js/pibidav.js"

# include js, css files in header of web template
# web_include_css = "/assets/pibidav/css/pibidav.css"
# web_include_js = "/assets/pibidav/js/pibidav.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "pibidav/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

brand_html = '<div><img width="27px" src="/assets/pibidav/image/pibiCo_engine_largo.png"> pibi<strong>DAV</strong></div>'

website_context = {
  "favicon": "/assets/pibidav/image/favicon.svg",
  "splash_image": "/assets/pibidav/image/pibiCo_engine_largo.png"
}

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Installation
# ------------

# before_install = "pibidav.install.before_install"
# after_install = "pibidav.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "pibidav.uninstall.before_uninstall"
# after_uninstall = "pibidav.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "pibidav.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

jenv = {
  "methods": [
    "timestamp_to_date:pibidav.jinja_filters.timestamp_to_date",
    "ts_to_date:pibidav.jinja_filters.ts_to_date"
  ]
}


# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
  "*": {
    "after_insert": "pibidav.pibidav.custom.create_nc_folder"
  },
  "File": {
    "after_insert": ["pibidav.pibidav.custom.upload_file_to_nc"]
  },
  "Event": {
    "after_insert": "pibidav.pibidav.pibical.sync_caldav_event_by_user",
    "on_trash": "pibidav.pibidav.pibical.remove_caldav_event"
  }
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
#	}
}

# Scheduled Tasks
# ---------------

scheduler_events = {
# 	"all": [
# 		"pibidav.tasks.all"
# 	],
  "cron": {
    "*/5 * * * *": [
      "pibidav.pibidav.pibical.sync_outside_caldav"
    ]
  },
  "daily": [
    "pibidav.pibidav.doctype.nextcloud_settings.nextcloud_settings.daily_backup"
  ],
# 	"hourly": [
# 		"pibidav.tasks.hourly"
# 	],
  "weekly": [
    "pibidocs.pibidocs.doctype.nextcloud_settings.nextcloud_settings.weekly_backup"
  ] #,
# 	"monthly": [
# 		"pibidav.tasks.monthly"
# 	]
}

# Testing
# -------

# before_tests = "pibidav.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "pibidav.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "pibidav.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

user_data_fields = [
	{
		"doctype": "{doctype_1}",
		"filter_by": "{filter_by}",
		"redact_fields": ["{field_1}", "{field_2}"],
		"partial": 1,
	},
	{
		"doctype": "{doctype_2}",
		"filter_by": "{filter_by}",
		"partial": 1,
	},
	{
		"doctype": "{doctype_3}",
		"strict": False,
	},
	{
		"doctype": "{doctype_4}"
	}
]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"pibidav.auth.validate"
# ]

fixtures = ['Role Profile', 'Role', 'Custom Field', 'Client Script', 'Property Setter', 'Translation']

treeviews = ['Folder Set']


# Translation
# --------------------------------

# Make link fields search translated document names for these DocTypes
# Recommended only for DocTypes which have limited documents with untranslated names
# For example: Role, Gender, etc.
# translated_search_doctypes = []
