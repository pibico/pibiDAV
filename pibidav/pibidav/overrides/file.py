# -*- coding: utf-8 -*-
# Copyright (c) 2022, PibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe.core.doctype.file.file import File
from pibidav.pibidav.custom import get_file_content as custom_get_file_content


class CustomFile(File):
    def get_content(self):
        """Override to handle URL-based files (NextCloud share links and other external URLs)"""
        
        # First try our custom handler
        custom_content = custom_get_file_content(self)
        if custom_content is not None:
            # Our handler returned content, use it
            return custom_content
        
        # Otherwise, use the parent class method for normal files
        return super().get_content()