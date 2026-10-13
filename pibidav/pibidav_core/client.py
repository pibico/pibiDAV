# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""HTTP transport shared by the CardDAV and CalDAV services.

One requests.Session per DAV Account, with the account credential, timeout
and TLS setting. Callers never build auth headers themselves.
"""

from urllib.parse import urljoin, urlparse

import frappe
import requests
from frappe import _

USER_AGENT = "pibiDAV/15 (Frappe)"


class DAVError(Exception):
	def __init__(self, message, status=None):
		super().__init__(message)
		self.status = status


def get_logger():
	return frappe.logger("pibidav.dav", allow_site=True)


def normalize_base_url(url):
	"""Validate a server base URL: https only, no credentials, no query."""
	url = (url or "").strip().rstrip("/")
	parsed = urlparse(url)
	if parsed.scheme != "https" or not parsed.hostname:
		frappe.throw(_("The server URL must be an https:// address"))
	if parsed.username or parsed.password or parsed.query or parsed.fragment:
		frappe.throw(_("The server URL must not contain credentials, query or fragment"))
	return url


def same_origin(url, base_url):
	a, b = urlparse(url), urlparse(base_url)
	return (a.scheme, a.hostname, a.port) == (b.scheme, b.hostname, b.port)


class DAVClient:
	def __init__(self, account, password=None):
		self.account = account
		self.base_url = normalize_base_url(account.server_url)
		self.dav_root = self.base_url + "/" + (account.dav_path or "").strip("/") + "/"
		self.timeout = account.timeout or 15
		self.session = requests.Session()
		self.session.verify = bool(account.verify_tls)
		self.session.headers["User-Agent"] = USER_AGENT
		if password is None:
			password = account.get_password("app_password", raise_exception=False)
		if not password:
			raise DAVError(_("The account has no credential yet"))
		self.session.auth = (account.login_name or account.username, password)

	def url(self, path=""):
		"""Absolute URL inside this server; refuses to leave it."""
		url = urljoin(self.dav_root, path)
		if not same_origin(url, self.base_url):
			raise DAVError(_("URL outside the account server: {0}").format(url))
		return url

	def request(self, method, path="", **kwargs):
		kwargs.setdefault("timeout", self.timeout)
		url = path if path.startswith("https://") else self.url(path)
		if not same_origin(url, self.base_url):
			raise DAVError(_("URL outside the account server: {0}").format(url))
		try:
			response = self.session.request(method, url, **kwargs)
		except requests.RequestException as e:
			raise DAVError(str(e)) from e
		if response.status_code == 401:
			raise DAVError(_("The server rejected the credential"), 401)
		if response.status_code >= 400:
			raise DAVError(_("{0} {1} failed with status {2}").format(method, url, response.status_code), response.status_code)
		return response

	def check(self):
		"""PROPFIND on the DAV root; returns True when the credential works."""
		body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:prop><d:current-user-principal/></d:prop></d:propfind>'
		self.request("PROPFIND", "", data=body, headers={"Depth": "0", "Content-Type": "application/xml; charset=utf-8"})
		return True

	def revoke_nextcloud_app_password(self):
		"""Delete the app password used by this session on the Nextcloud server."""
		self.request("DELETE", self.base_url + "/ocs/v2.php/core/apppassword", headers={"OCS-APIRequest": "true"})

	def nextcloud_user_id(self):
		"""Login of the authenticated user, from the Nextcloud OCS API."""
		response = self.request(
			"GET",
			self.base_url + "/ocs/v2.php/cloud/user?format=json",
			headers={"OCS-APIRequest": "true", "Accept": "application/json"},
		)
		return ((response.json().get("ocs") or {}).get("data") or {}).get("id")
