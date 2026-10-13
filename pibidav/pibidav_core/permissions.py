# Copyright (c) 2026, pibiCo and contributors
# For license information, please see license.txt

"""Owner-only access for rows that belong to a DAV Account (field `user`)."""

from contextlib import contextmanager

import frappe

from pibidav.pibidav_core.doctype.dav_account.dav_account import is_admin


def has_owner_permission(doc, ptype=None, user=None, debug=False):
	user = user or frappe.session.user
	if is_admin(user):
		return True
	if ptype == "create":
		return False
	return doc.user == user


def owner_condition(doctype, user=None):
	user = user or frappe.session.user
	if is_admin(user):
		return ""
	return f"`tab{doctype}`.`user` = {frappe.db.escape(user)}"


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
