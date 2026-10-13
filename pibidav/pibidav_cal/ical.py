# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""iCalendar ↔ Event mapping.

Frappe manages the summary, description, start, end, all-day flag, simple
recurrences and cancellation. When the event already exists on the server
only those properties of the master VEVENT are replaced; alarms, attendees,
classification and recurrence exceptions are kept.
"""

import datetime as dt
import html
import re
import uuid
from zoneinfo import ZoneInfo

from frappe.utils import (
	cstr,
	get_datetime,
	get_system_timezone,
	getdate,
	now_datetime,
	strip_html,
)
from icalendar import Calendar, vCalAddress, vRecur
from icalendar import Event as VEvent

FREQS = {"DAILY": "Daily", "WEEKLY": "Weekly", "MONTHLY": "Monthly", "YEARLY": "Yearly"}
DAYS = {"MO": "monday", "TU": "tuesday", "WE": "wednesday", "TH": "thursday", "FR": "friday", "SA": "saturday", "SU": "sunday"}


def html_to_text(value):
	"""Frappe Text Editor HTML → plain text with line breaks and decoded entities."""
	text = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", cstr(value))
	return html.unescape(strip_html(text)).strip()


def new_uid():
	return str(uuid.uuid4())


def system_tz():
	return ZoneInfo(get_system_timezone())


def parse(text):
	try:
		return Calendar.from_ical(text)
	except Exception:
		return None


def master(cal):
	"""The VEVENT without RECURRENCE-ID (exceptions of a series are kept apart)."""
	for comp in cal.walk("VEVENT"):
		if comp.get("RECURRENCE-ID") is None:
			return comp
	return None


def uid_of(cal):
	vevent = master(cal) if cal is not None else None
	return cstr(vevent.get("UID")).strip() if vevent is not None and vevent.get("UID") else None


def to_local(value):
	"""Server value → naive datetime in the system time zone (dates stay dates)."""
	if isinstance(value, dt.datetime):
		return value.astimezone(system_tz()).replace(tzinfo=None) if value.tzinfo else value
	return value


def rrule_supported(rule):
	"""Frappe repeats: one FREQ, interval 1, optional UNTIL, BYDAY only for weekly."""
	keys = set(rule) - {"FREQ", "UNTIL", "BYDAY", "INTERVAL", "WKST"}
	freq = (rule.get("FREQ") or [None])[0]
	interval = (rule.get("INTERVAL") or [1])[0]
	return not keys and freq in FREQS and int(interval) == 1 and (freq == "WEEKLY" or not rule.get("BYDAY"))


def apply(event, cal):
	"""Copy the managed values of the master VEVENT into an Event.
	Returns False when the server recurrence cannot be represented in Frappe."""
	vevent = master(cal)
	start = to_local(vevent.decoded("DTSTART"))
	if vevent.get("DTEND") is not None:
		end = to_local(vevent.decoded("DTEND"))
	elif vevent.get("DURATION") is not None:
		end = start + vevent.decoded("DURATION")
	else:
		end = start
	if type(end) is not type(start) or end < start:
		# Some clients store an end before the start; Frappe rejects it
		end = start

	event.subject = cstr(vevent.get("SUMMARY")) or "(no title)"
	if isinstance(start, dt.datetime):
		event.all_day = 0
		event.starts_on, event.ends_on = start, end
	else:
		# All-day: DTEND is exclusive in iCalendar
		event.all_day = 1
		last_day = end - dt.timedelta(days=1) if end > start else start
		event.starts_on = dt.datetime.combine(start, dt.time())
		event.ends_on = dt.datetime.combine(last_day, dt.time())

	remote_text = cstr(vevent.get("DESCRIPTION")).strip()
	if remote_text != html_to_text(event.description):
		event.description = html.escape(remote_text).replace("\n", "<br>") if remote_text else None
	if cstr(vevent.get("STATUS")).upper() == "CANCELLED":
		event.status = "Cancelled"
	elif event.status == "Cancelled":
		event.status = "Open"

	rule = vevent.get("RRULE")
	if rule is None:
		event.repeat_this_event = 0
		return True
	if not rrule_supported(rule):
		event.repeat_this_event = 0
		return False
	event.repeat_this_event = 1
	event.repeat_on = FREQS[rule["FREQ"][0]]
	until = (rule.get("UNTIL") or [None])[0]
	event.repeat_till = getdate(to_local(until)) if until else None
	for code, field in DAYS.items():
		event.set(field, 1 if code in [cstr(d)[-2:] for d in rule.get("BYDAY", [])] else 0)
	return True


def _when(event, value):
	value = get_datetime(value)
	if event.all_day:
		return value.date()
	return value.replace(tzinfo=system_tz())


def build(event, uid, base_text=None, keep_server_rrule=False):
	"""iCalendar text for an Event; base_text is the server's current resource, if any."""
	cal = parse(base_text) if base_text else None
	vevent = master(cal) if cal is not None else None
	if vevent is None:
		cal = Calendar()
		cal.add("prodid", "-//pibiCo//pibiDAV 15//EN")
		cal.add("version", "2.0")
		vevent = VEvent()
		cal.add_component(vevent)

	sequence = int(vevent.get("SEQUENCE") or 0) + (1 if base_text else 0)
	for key in ("UID", "SUMMARY", "DESCRIPTION", "DTSTART", "DTEND", "DURATION", "DTSTAMP", "LAST-MODIFIED", "SEQUENCE"):
		vevent.pop(key, None)
	vevent.add("uid", uid)
	vevent.add("summary", cstr(event.subject))
	text = html_to_text(event.description)
	if text:
		vevent.add("description", text)
	start = _when(event, event.starts_on)
	end = _when(event, event.ends_on or event.starts_on)
	if event.all_day:
		end = end + dt.timedelta(days=1)
	vevent.add("dtstart", start)
	vevent.add("dtend", end)
	now = now_datetime().replace(tzinfo=system_tz())
	vevent.add("dtstamp", now)
	vevent.add("last-modified", now)
	vevent.add("sequence", sequence)
	if event.status == "Cancelled":
		vevent.pop("STATUS", None)
		vevent.add("status", "CANCELLED")
	elif cstr(vevent.get("STATUS")).upper() == "CANCELLED":
		vevent.pop("STATUS", None)

	if event.repeat_this_event and event.repeat_on:
		vevent.pop("RRULE", None)
		rule = {"FREQ": [k for k, v in FREQS.items() if v == event.repeat_on][0]}
		if event.repeat_on == "Weekly":
			days = [code for code, field in DAYS.items() if event.get(field)]
			if days:
				rule["BYDAY"] = days
		if event.repeat_till:
			rule["UNTIL"] = dt.datetime.combine(getdate(event.repeat_till), dt.time(23, 59, 59)).replace(tzinfo=system_tz()).astimezone(dt.timezone.utc)
		vevent.add("rrule", vRecur(rule))
	elif not keep_server_rrule:
		vevent.pop("RRULE", None)

	cal.add_missing_timezones()
	return cal.to_ical().decode()


def invitation(event, uid, organizer_email, organizer_name, attendees):
	"""iTIP REQUEST (RFC 5546) for e-mail invitations; attendees is [(email, name)]."""
	cal = Calendar.from_ical(build(event, uid))
	cal.add("method", "REQUEST")
	vevent = master(cal)
	if cstr(vevent.get("STATUS")).upper() != "CANCELLED":
		vevent.pop("STATUS", None)
		vevent.add("status", "CONFIRMED")
	organizer = vCalAddress(f"mailto:{organizer_email}")
	organizer.params["cn"] = organizer_name
	vevent.add("organizer", organizer)
	for email, name in attendees:
		attendee = vCalAddress(f"mailto:{email}")
		attendee.params.update({"cn": name, "role": "REQ-PARTICIPANT", "partstat": "NEEDS-ACTION", "rsvp": "TRUE"})
		vevent.add("attendee", attendee)
	return cal.to_ical()
