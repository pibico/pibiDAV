# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Owner-only access for rows that belong to a DAV Account (field `user`)."""

from contextlib import contextmanager

import frappe

from pibidav.pibidav_core.doctype.dav_account.dav_account import is_admin


def has_owner_permission(doc, ptype=None, user=None, debug=False):
	"""Sync rows (links, pending vCards): the owner reads them; only pibiDAV's own code,
	which saves them with ignore_permissions, changes them."""
	user = user or frappe.session.user
	if is_admin(user):
		return True
	if ptype not in ("read", "select", "print", "email"):
		return False
	return doc.user == user


def has_owner_edit_permission(doc, ptype=None, user=None, debug=False):
	"""DAV Account and DAV Collection: the owner reads and edits (each controller limits
	which fields); only an administrator creates or deletes them."""
	user = user or frappe.session.user
	if is_admin(user):
		return True
	if ptype in ("create", "delete"):
		return False
	return doc.user == user


def owner_condition(doctype, user=None):
	user = user or frappe.session.user
	if is_admin(user):
		return ""
	return f"`tab{doctype}`.`user` = {frappe.db.escape(user)}"


def account_query(user=None):
	return owner_condition("DAV Account", user)


def collection_query(user=None):
	return owner_condition("DAV Collection", user)


def card_link_query(user=None):
	return owner_condition("DAV Card Link", user)


def pending_contact_query(user=None):
	return owner_condition("DAV Pending Contact", user)


def cal_link_query(user=None):
	return owner_condition("DAV Cal Link", user)


@contextmanager
def acting_as(user):
	"""Run sync work as the account owner, so Frappe permissions are theirs."""
	previous = frappe.session.user
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(previous)
