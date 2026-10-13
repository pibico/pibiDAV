# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.password import remove_encrypted_password

from pibidav.pibidav_core.audit import log_operation
from pibidav.pibidav_core.client import (
	DAVClient,
	DAVError,
	get_logger,
	normalize_base_url,
	same_origin,
)

# Fields the account owner may change; everything else is set by the administrator
OWNER_EDITABLE = {"app_password", "enabled"}
LOGIN_FLOW_TTL = 20 * 60


def is_admin(user=None):
	return "System Manager" in frappe.get_roles(user)


class DAVAccount(Document):
	def validate(self):
		self.server_url = normalize_base_url(self.server_url)
		self.dav_path = "/" + (self.dav_path or "").strip().strip("/")
		self.username = (self.username or "").strip()
		self.validate_owner_changes()
		self.validate_unique()
		if not self.enabled:
			self.status = "Disabled"
		elif self.status == "Disabled":
			self.status = "Pending"

	def validate_owner_changes(self):
		if is_admin():
			return
		if self.is_new():
			frappe.throw(_("Only an administrator can create DAV accounts"), frappe.PermissionError)
		before = self.get_doc_before_save()
		for df in self.meta.fields:
			if df.fieldtype in ("Section Break", "Column Break") or df.read_only or df.fieldname in OWNER_EDITABLE:
				continue
			if before and before.get(df.fieldname) != self.get(df.fieldname):
				frappe.throw(_("Only an administrator can change {0}").format(_(df.label)), frappe.PermissionError)

	def validate_unique(self):
		same_service = {"service": self.service, "server_url": self.server_url, "name": ("!=", self.name)}
		if frappe.db.exists("DAV Account", {**same_service, "user": self.user}):
			frappe.throw(_("{0} already has a {1} account on this server").format(self.user, self.service))
		# Accounts are personal (ISO 27001 A 5.16): one server login cannot be shared by two users
		other = frappe.db.get_value("DAV Account", {**same_service, "username": self.username, "user": ("!=", self.user)}, "user")
		if other:
			frappe.throw(_("The server login {0} is already assigned to {1}").format(self.username, other))

	def before_save(self):
		# A new server login invalidates the credential of the previous one
		if not self.is_new() and self.has_value_changed("username"):
			self.login_name = None
			self.app_password = None
			self.flags.drop_credential = True

	def on_update(self):
		if self.flags.drop_credential:
			remove_encrypted_password(self.doctype, self.name, "app_password")
			self.db_set({"status": "Pending", "last_error": None})
		elif self.has_value_changed("app_password") and self.app_password:
			self.db_set({"status": "Pending", "last_error": None})


def has_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if is_admin(user):
		return True
	if ptype in ("create", "delete"):
		return False
	return doc.user == user


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if is_admin(user):
		return ""
	return f"`tabDAV Account`.`user` = {frappe.db.escape(user)}"


def get_own_account(name):
	account = frappe.get_doc("DAV Account", name)
	if account.user != frappe.session.user:
		frappe.throw(_("Only the owner of the account can connect it"), frappe.PermissionError)
	return account


def verify_identity(account, client):
	"""The authenticated login must be the one fixed by the administrator."""
	if account.server_type != "Nextcloud":
		return
	login = client.nextcloud_user_id()
	if (login or "").lower() != account.username.lower():
		raise DAVError(_("The credential belongs to {0}, not to {1}").format(login, account.username))


def mark(account, status, error=None):
	account.db_set({"status": status, "last_check": now_datetime(), "last_error": (error or None) and error[:500]})


@frappe.whitelist()
def test_connection(name):
	account = frappe.get_doc("DAV Account", name)
	account.check_permission("read")
	try:
		client = DAVClient(account)
		verify_identity(account, client)
		client.check()
	except DAVError as e:
		mark(account, "Error", str(e))
		log_operation(account, "check", result="Error", detail=str(e))
		return {"ok": False, "error": str(e)}
	mark(account, "Connected")
	log_operation(account, "check")
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
def start_login_flow(name):
	"""Nextcloud Login Flow v2: returns the URL the owner must open to grant an app password."""
	account = get_own_account(name)
	if account.server_type != "Nextcloud":
		frappe.throw(_("Login flow is only available for Nextcloud servers"))
	base = normalize_base_url(account.server_url)
	try:
		response = requests.post(
			base + "/index.php/login/v2",
			timeout=account.timeout or 15,
			verify=bool(account.verify_tls),
			headers={"User-Agent": "pibiDAV/15 (Frappe)"},
		)
		response.raise_for_status()
		data = response.json()
	except (requests.RequestException, ValueError) as e:
		get_logger().warning(f"Login flow start failed for DAV Account {name}: {e}")
		frappe.throw(_("Could not start the Nextcloud login: {0}").format(e))
	poll = data.get("poll") or {}
	if not (poll.get("token") and same_origin(poll.get("endpoint", ""), base) and same_origin(data.get("login", ""), base)):
		frappe.throw(_("Unexpected answer from the Nextcloud server"))
	frappe.cache.set_value(f"pibidav:loginflow:{name}", poll, expires_in_sec=LOGIN_FLOW_TTL)
	log_operation(account, "login_flow_start")
	return {"login_url": data["login"]}


@frappe.whitelist(methods=["POST"])
def poll_login_flow(name):
	"""Called by the form until the owner approves the login in Nextcloud."""
	account = get_own_account(name)
	poll = frappe.cache.get_value(f"pibidav:loginflow:{name}")
	if not poll:
		return {"status": "expired"}
	try:
		response = requests.post(
			poll["endpoint"],
			data={"token": poll["token"]},
			timeout=account.timeout or 15,
			verify=bool(account.verify_tls),
		)
	except requests.RequestException as e:
		return {"status": "waiting", "error": str(e)}
	if response.status_code == 404:
		return {"status": "waiting"}
	if response.status_code != 200:
		return {"status": "error", "error": _("Status {0}").format(response.status_code)}
	frappe.cache.delete_value(f"pibidav:loginflow:{name}")
	result = response.json()
	# The login may be the account id or its e-mail: ask the server who it really is
	account.login_name = result.get("loginName")
	client = DAVClient(account, password=result.get("appPassword"))
	try:
		verify_identity(account, client)
	except DAVError as e:
		try:
			client.revoke_nextcloud_app_password()
		except DAVError:
			get_logger().warning(f"Could not revoke a mismatching app password for DAV Account {name}")
		log_operation(account, "login_flow_done", result="Error", detail="login mismatch")
		return {"status": "error", "error": str(e)}
	account.app_password = result.get("appPassword")
	account.save()
	log_operation(account, "login_flow_done")
	return {"status": "done", **test_connection(name)}


def disable_accounts_of_user(doc, method=None):
	"""User doc_event: when a user is disabled, so are their DAV accounts."""
	if doc.enabled or not doc.has_value_changed("enabled"):
		return
	for name in frappe.get_all("DAV Account", filters={"user": doc.name, "enabled": 1}, pluck="name"):
		frappe.db.set_value("DAV Account", name, {"enabled": 0, "status": "Disabled"})
		account = frappe.get_doc("DAV Account", name)
		log_operation(account, "disable", detail="user disabled; revoke the app password on the server", user=doc.name)
