from __future__ import unicode_literals

import frappe
from datetime import tzinfo, timedelta, datetime

def timestamp_to_date(value, format='%a %H:%M'):
  if value:
    return datetime.fromtimestamp(int(value)).strftime(format)

def ts_to_date(value, format='%a %d/%m/%y %H:%M'):
  if value:
    return datetime.fromtimestamp(int(value)).strftime(format)