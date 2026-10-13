# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DAVSettings(Document):
	def validate(self):
		if self.cal_push_enabled or self.cal_pull_enabled:
			self.check_pibical_stopped()

	def check_pibical_stopped(self):
		"""pibical and pibidav must not sync the same calendars: events would be duplicated."""
		if "pibical" not in frappe.get_installed_apps():
			return
		running = frappe.db.exists("Scheduled Job Type", {"method": ("like", "pibical.%"), "stopped": 0})
		users = frappe.db.has_column("User", "caldav_url") and frappe.db.count("User", {"caldav_url": ("is", "set")})
		if running or users:
			frappe.throw(
				_("Calendar sync cannot be enabled while pibical is still syncing: stop its scheduled job and clear the CalDAV fields of the users first.")
			)
