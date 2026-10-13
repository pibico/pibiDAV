# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe.query_builder.functions import Coalesce
from frappe.utils import cint, getdate, nowdate


def complete_past_events():
	"""Open events that already took place become Completed, so nobody has to close them.
	A repeating event is one document in Frappe: it is completed only when its series ends."""
	if not cint(frappe.db.get_single_value("DAV Settings", "complete_past_events")):
		return 0
	event = frappe.qb.DocType("Event")
	today = getdate(nowdate())
	single = (Coalesce(event.repeat_this_event, 0) == 0) & (Coalesce(event.ends_on, event.starts_on) < today)
	series_over = (event.repeat_this_event == 1) & event.repeat_till.isnotnull() & (event.repeat_till < today)
	names = (
		frappe.qb.from_(event).select(event.name).where((event.status == "Open") & (single | series_over)).run(pluck=True)
	)
	if names:
		# Status only: no CalDAV push is needed, the server keeps its own status
		frappe.qb.update(event).set(event.status, "Completed").where(event.name.isin(names)).run()
		frappe.logger("pibidav.cal").info(f"complete_past_events: {len(names)} events completed")
	return len(names)
