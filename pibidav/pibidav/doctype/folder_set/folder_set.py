# Copyright (c) 2022, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils.nestedset import NestedSet

import frappe.model.rename_doc

class FolderSet(NestedSet):
	def before_save(doc):
		if doc.parent_folder_set and doc.parent_folder_set != '':
			doc.root_parent = frappe.db.get_value('Folder Set', doc.parent_folder_set, 'root_parent')

	def after_insert(doc):
		old_name = doc.name
		r = frappe.db.get_value('Folder Set', doc.title, 'name')
		if r and r == doc.title:
			doc.name = doc.title + ' (' + old_name + ')'
		else:
			doc.name = doc.title

		if not doc.parent_folder_set or doc.parent_folder_set == '':
			doc.root_parent = doc.name
		frappe.db.set_value('Folder Set', old_name, {
			'name': doc.name,
			'root_parent': doc.root_parent,
			'title': doc.name
			}, update_modified=False)

@frappe.whitelist()
def get_children(doctype, parent='', **filters):
	return _get_children(doctype, parent)

def _get_children(doctype, parent='', ignore_permissions=False):
	parent_field = 'parent_' + doctype.lower().replace(' ', '_')
	filters = [['ifnull(`{0}`,"")'.format(parent_field), '=', parent],
		['docstatus', '<' ,'2']]

	meta = frappe.get_meta(doctype)

	return frappe.get_list(
		doctype,
		fields=[
			'name as value',
			'{0} as title'.format(meta.get('title_field') or 'name'),
			'is_group as expandable'
		],
		filters=filters,
		order_by='title',
		ignore_permissions=ignore_permissions
	)

@frappe.whitelist()
def rename(old, new, debug=False):
	return frappe.model.rename_doc.rename_doc('Folder Set', old, new, debug)