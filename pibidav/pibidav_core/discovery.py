# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Find the address books and calendars an account can see, and read changes.

Only standard WebDAV, CardDAV, CalDAV and sync-collection (RFC 6578) requests;
the Nextcloud owner-principal property is read when present.
"""

import xml.etree.ElementTree as ET

import frappe
from frappe import _
from frappe.utils import now_datetime

from pibidav.pibidav_core.audit import log_operation
from pibidav.pibidav_core.client import DAVClient, DAVError

NS = {
	"d": "DAV:",
	"card": "urn:ietf:params:xml:ns:carddav",
	"cal": "urn:ietf:params:xml:ns:caldav",
	"cs": "http://calendarserver.org/ns/",
	"oc": "http://owncloud.org/ns",
}
XML_HEADERS = {"Content-Type": "application/xml; charset=utf-8"}

for prefix, uri in NS.items():
	ET.register_namespace(prefix, uri)


def parse_multistatus(text):
	"""[(href, {tag: element}, status)] from a 207 Multi-Status body."""
	try:
		root = ET.fromstring(text)
	except ET.ParseError as e:
		raise DAVError(_("Invalid answer from the server: {0}").format(e)) from e
	out = []
	for response in root.findall("d:response", NS):
		href = response.findtext("d:href", default="", namespaces=NS)
		props, status = {}, response.findtext("d:status", default="", namespaces=NS)
		for propstat in response.findall("d:propstat", NS):
			if " 200 " not in (propstat.findtext("d:status", default="", namespaces=NS) + " "):
				continue
			prop_el = propstat.find("d:prop", NS)
			for prop in prop_el if prop_el is not None else []:
				props[prop.tag] = prop
		out.append((href, props, status))
	return out, root


def tag(prefix, name):
	return f"{{{NS[prefix]}}}{name}"


def propfind(client, href, body, depth="0"):
	response = client.request("PROPFIND", href, data=body, headers={**XML_HEADERS, "Depth": depth})
	return parse_multistatus(response.text)[0]


def find_home(client, service):
	"""Address book or calendar home of the authenticated principal."""
	body = '<d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>'
	result = propfind(client, "", body)
	principal = result and result[0][1].get(tag("d", "current-user-principal"))
	principal_href = principal is not None and principal.findtext("d:href", namespaces=NS)
	if not principal_href:
		raise DAVError(_("The server did not return the user principal"))
	home_prop = ("card", "addressbook-home-set") if service == "CardDAV" else ("cal", "calendar-home-set")
	body = f'<d:propfind xmlns:d="DAV:" xmlns:{home_prop[0]}="{NS[home_prop[0]]}"><d:prop><{home_prop[0]}:{home_prop[1]}/></d:prop></d:propfind>'
	result = propfind(client, principal_href, body)
	home = result and result[0][1].get(tag(*home_prop))
	home_href = home is not None and home.findtext("d:href", namespaces=NS)
	if not home_href:
		raise DAVError(_("The server did not return the {0} home").format(service))
	return home_href


def discover(account):
	"""Create or update the DAV Collection rows of an account. New ones start with sync off."""
	client = DAVClient(account)
	home = find_home(client, account.service)
	body = (
		'<d:propfind xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/" xmlns:oc="http://owncloud.org/ns" '
		'xmlns:cal="urn:ietf:params:xml:ns:caldav"><d:prop><d:resourcetype/><d:displayname/><cs:getctag/>'
		"<d:sync-token/><oc:owner-principal/><d:current-user-privilege-set/>"
		"<cal:supported-calendar-component-set/></d:prop></d:propfind>"
	)
	kind = tag("card", "addressbook") if account.service == "CardDAV" else tag("cal", "calendar")
	found = []
	for href, props, _status in propfind(client, home, body, depth="1"):
		resourcetype = props.get(tag("d", "resourcetype"))
		if resourcetype is None or resourcetype.find(kind) is None:
			continue
		components = props.get(tag("cal", "supported-calendar-component-set"))
		if account.service == "CalDAV" and components is not None:
			if "VEVENT" not in [c.get("name") for c in components]:
				continue
		privileges = props.get(tag("d", "current-user-privilege-set"))
		writable = privileges is None or any(
			p.find(tag("d", name)) is not None for p in privileges for name in ("write", "write-content", "all")
		)
		values = {
			"display_name": (props.get(tag("d", "displayname")).text if props.get(tag("d", "displayname")) is not None else None) or href.rstrip("/").rsplit("/", 1)[-1],
			"owner_principal": props.get(tag("oc", "owner-principal")).text if props.get(tag("oc", "owner-principal")) is not None else None,
			"read_only": 0 if writable else 1,
		}
		name = frappe.db.get_value("DAV Collection", {"dav_account": account.name, "href": href})
		doc = frappe.get_doc("DAV Collection", name) if name else frappe.new_doc("DAV Collection")
		doc.update({"dav_account": account.name, "href": href, **values})
		doc.flags.from_discovery = True
		doc.save(ignore_permissions=True)  # rows mirror the server; the owner only toggles sync
		found.append(doc.name)
	# Collections that no longer exist on the server stop syncing (they would fail with 404)
	for name in frappe.get_all(
		"DAV Collection", filters={"dav_account": account.name, "name": ("not in", found or [""]), "sync_enabled": 1}, pluck="name"
	):
		frappe.db.set_value("DAV Collection", name, "sync_enabled", 0)
	log_operation(account, "discover", resource=home, detail=f"{len(found)} collections")
	return found


def sync_changes(client, collection, extra_props=""):
	"""sync-collection REPORT. Returns (changed {href: etag}, deleted [href], new_token)."""
	token = collection.sync_token or ""
	body = (
		f'<d:sync-collection xmlns:d="DAV:"><d:sync-token>{frappe.utils.escape_html(token)}</d:sync-token>'
		f"<d:sync-level>1</d:sync-level><d:prop><d:getetag/>{extra_props}</d:prop></d:sync-collection>"
	)
	response = client.request("REPORT", collection.href, data=body, headers={**XML_HEADERS, "Depth": "1"})
	responses, root = parse_multistatus(response.text)
	changed, deleted = {}, []
	for href, props, status in responses:
		if href.rstrip("/") == collection.href.rstrip("/"):
			continue
		if " 404 " in status + " ":
			deleted.append(href)
		elif props.get(tag("d", "getetag")) is not None:
			changed[href] = props[tag("d", "getetag")].text
	return changed, deleted, root.findtext("d:sync-token", default="", namespaces=NS)


def mark_synced(collection, token):
	collection.db_set({"sync_token": token, "last_sync": now_datetime()}, update_modified=False)
