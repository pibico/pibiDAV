# -*- coding: utf-8 -*-
# Copyright (c) 2022, PibiCo and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
from frappe import _, msgprint, throw, enqueue
from frappe.utils import cint, cstr
from frappe.desk.doctype.tag.tag import DocTags
from frappe.modules.utils import get_doctype_module, get_module_app

import json, time, requests, sys, hashlib
from urllib.parse import urljoin

from icalendar import Calendar, Event
from icalendar import vCalAddress, vText, vRecur
from pytz import UTC, timezone

import caldav

from datetime import date, datetime, timedelta

from frappe.utils.password import get_decrypted_password

madrid = timezone('Europe/Madrid')

@frappe.whitelist()
def get_calendar(nuser):
  fp_user = frappe.get_doc("User", nuser)
  if not fp_user.get('nextcloud_enable'):
    return
  caldav_client, caldav_url, caldav_username, caldav_token = make_caldav_session(fp_user)
  if caldav_client == "Failed":
    frappe.throw(_("calDAV Connection Failed"))
    return
  
  cal_principal = caldav_client.principal()
  # fetching calendars from server
  calendars = cal_principal.calendars()
  arr_cal = []
  if calendars:
    # print("[INFO] Received %i calendars:" % len(calendars))
    cal_url = caldav_url.replace("principals/users","calendars")
    for c in calendars:
      print("Name: %-20s  URL: %s" % (c.name, c.url.replace(cal_url +"/" , "").replace("/","")))
      scal = {}
      scal['name'] = c.name
      scal['url'] = str(c.url)
      arr_cal.append(scal)
  else:
    frappe.throw(_("Server has no calendars for your user"))
    
  return arr_cal

@frappe.whitelist()
def sync_caldav_event_by_user(doc, method=None):
  """
    Synchronize a CalDAV event with a user.
    Args:
        doc (frappe.model.Document): The document representing the event.
        method (str, optional): The synchronization method. If not provided, a method will be chosen based on the document's status.
    Returns:
        str: A message indicating the result of the synchronization.
    """
  # If the document is not set to be synchronized with CalDAV, do nothing
  if not doc.sync_with_caldav:
    return 'Document is not set to be synchronized with CalDAV.'

  create_or_update_event_on_caldav(doc)
  
  #frappe.msgprint(_('Synchronization successful.'))
  #return 'Synchronization successful.'

def create_or_update_event_on_caldav(doc, method=None):
  """
    Create or update an event on a CalDAV server.

    Args:
        doc (frappe.model.Document): The document representing the event.
        client (caldav.DAVClient): The CalDAV client to use.

    Returns:
        str: A message indicating the result of the operation.
  """
  
  user = frappe.get_doc('User', frappe.session.user)
  if not user.get('nextcloud_enable'):
    return
  # If the document has no CalDAV ID URL, there is no calendar to update
  # Fill CalDav URL with selected CalDav Calendar
  frappe.publish_progress(12, title='Event Progress', description='Synchronizing Event in NC')
  # Fetch the user's CalDAV credentials
  client, url, username, password = make_caldav_session(user)
  # If the CalDAV session could not be created, return an error message
  if client == 'Failed':
    frappe.msgprint(f"Failed to create CalDAV session {url}")
    return f"Failed to create CalDAV session {url}"
  
  doc.caldav_id_url = doc.caldav_id_calendar
  if not doc.caldav_id_url:
    frappe.throw(_('Document has no CalDAV ID URL.'))
    return 'Document has no CalDAV ID URL.'

  # Fetch the calendar
  calendar = client.calendar(url=doc.caldav_id_url)

  # If the calendar could not be found, return an error message
  if not calendar:
    frappe.throw(_('Failed to fetch calendar: ' + doc.caldav_id_url))
    return 'Failed to fetch calendar: ' + doc.caldav_id_url
  
  # Search for the event for events scheduled from yesterday to 30 days onwards. Not overdue
  start_date = datetime.now() - timedelta(days=720)  # Yesterday
  end_date = datetime.now() + timedelta(days=720)  # 30 days from now
  events = calendar.date_search(start=start_date, end=end_date)

  """
  # Try to find an existing event to update
  for event in events:
    # If this event matches the document's event UID, update it
    if event.vobject_instance.vevent.uid.value == doc.event_uid:
      # DTSTAMP from current time
      doc.event_stamp = datetime.now()
      event.vobject_instance.vevent.dtstamp.value = doc.event_stamp
      # DTSTART from start
      dtstart = datetime.strptime(doc.starts_on, '%Y-%m-%d %H:%M:%S')
      if doc.all_day:
        dtstart = date(dtstart.year, dtstart.month, dtstart.day)
      else:  
        dtstart = datetime(dtstart.year, dtstart.month, dtstart.day, dtstart.hour, dtstart.minute, dtstart.second, tzinfo=madrid) 
      event.vobject_instance.vevent.dtstart.value = dtstart
      # DTEND if end
      if doc.ends_on:
        dtend = datetime.strptime(doc.ends_on, '%Y-%m-%d %H:%M:%S')
        if doc.all_day:
          dtend = date(dtend.year, dtend.month, dtend.day)
        else:  
          dtend = datetime(dtend.year, dtend.month, dtend.day, dtend.hour, dtend.minute, dtend.second, tzinfo=madrid)
        event.vobject_instance.vevent.dtend.value = dtend
      # SUMMARY from subject
      event.vobject_instance.vevent.summary.value = doc.subject
      # DESCRIPTION if any
      if doc.description: event.vobject_instance.vevent.description.value = doc.description
      # LOCATION if any
      if doc.location: event.vobject_instance.vevent.location.value = doc.location
      event.save()
      frappe.publish_progress(100, title='Event Progress', description='Synchronizing Event in NC')
      frappe.msgprint(_('Event updated successfully.'))
      return 'Event updated successfully.'
  """
  
  for event in events:
    if hasattr(event.instance, 'vevent') and hasattr(event.instance.vevent, 'uid'):
      vevent = event.instance.vevent
      if vevent.uid.value == doc.event_uid:
        # Update event logic
        # DTSTAMP from current time
        doc.event_stamp = datetime.now()
        event.vobject_instance.vevent.dtstamp.value = doc.event_stamp
        # DTSTART from start
        dtstart = datetime.strptime(doc.starts_on, '%Y-%m-%d %H:%M:%S')
        if doc.all_day:
          dtstart = date(dtstart.year, dtstart.month, dtstart.day)
        else:  
          dtstart = datetime(dtstart.year, dtstart.month, dtstart.day, dtstart.hour, dtstart.minute, dtstart.second, tzinfo=madrid) 
        event.vobject_instance.vevent.dtstart.value = dtstart
        # DTEND if end
        if doc.ends_on:
          dtend = datetime.strptime(doc.ends_on, '%Y-%m-%d %H:%M:%S')
          if doc.all_day:
            dtend = date(dtend.year, dtend.month, dtend.day)
          else:  
            dtend = datetime(dtend.year, dtend.month, dtend.day, dtend.hour, dtend.minute, dtend.second, tzinfo=madrid)
          event.vobject_instance.vevent.dtend.value = dtend
        # SUMMARY from subject
        event.vobject_instance.vevent.summary.value = doc.subject
        # DESCRIPTION if any
        if doc.description: event.vobject_instance.vevent.description.value = doc.description
        # LOCATION if any
        if doc.location: event.vobject_instance.vevent.location.value = doc.location
        event.save()
        frappe.publish_progress(100, title='Event Progress', description='Synchronizing Event in NC')
        frappe.msgprint(_('Event updated successfully.'))
        return 'Event updated successfully.'

  # Create uid for new events
  uid_date = datetime.now().strftime("%Y%m%dT%H%M%S")
  uid = 'frappe' + hashlib.md5(uid_date.encode('utf-8')).hexdigest() + '@pibico.es'
  if not doc.event_uid:
    doc.event_uid = uid
  else:
    uid = doc.event_uid

  #If no matching event was found, create a new one
  #ical_event = """
  #  BEGIN:VCALENDAR
  #  VERSION:2.0
  #  PRODID:-//pibiDAV//pibico.org//EN
  #  BEGIN:VEVENT
  #  UID:{uid}
  #  DTSTAMP:{timestamp}
  #  DTSTART:{start}
  #  DTEND:{end}
  #  SUMMARY:{summary}
  #  END:VEVENT
  #  END:VCALENDAR
  #  """.format(uid=doc.event_uid, timestamp=doc.event_stamp, start=doc.start_date, end=doc.end_date, summary=doc.event_summary)
 
  #Prepare iCalendar
  cal = Calendar()
  #VERSION
  cal.add('version', '2.0')
  #PRODID
  cal.add('prodid', '-//pibiDAV//pibico.org//')
  # Initialize Event
  event = Event()
  # Fill data to Event
  #UID
  event['uid'] = doc.event_uid
  # DTSTAMP from current time
  doc.event_stamp = datetime.now()
  event.add('dtstamp', doc.event_stamp)
  # DTSTART from start
  dtstart = datetime.strptime(doc.starts_on, '%Y-%m-%d %H:%M:%S')
  if doc.all_day:
    dtstart = date(dtstart.year, dtstart.month, dtstart.day)
  else:  
    dtstart = datetime(dtstart.year, dtstart.month, dtstart.day, dtstart.hour, dtstart.minute, dtstart.second, tzinfo=madrid)
  event.add('dtstart', dtstart)
  # DTEND if end
  if doc.ends_on:
    dtend = datetime.strptime(doc.ends_on, '%Y-%m-%d %H:%M:%S')
    if doc.all_day:
      dtend = date(dtend.year, dtend.month, dtend.day)
    else:  
      dtend = datetime(dtend.year, dtend.month, dtend.day, dtend.hour, dtend.minute, dtend.second, tzinfo=madrid)
    event.add('dtend', dtend)
  # SUMMARY from Subject
  event.add('summary', doc.subject)
  # DESCRIPTION if any
  if doc.description: event.add('description', doc.description)
  # LOCATION if any
  if doc.location: event.add('location', doc.location)
  # CATEGORIES from event_category
  category = _(doc.event_category)
  event.add('categories', [category])
  # ORGANIZER from user session
  fp_user = frappe.get_doc("User", frappe.session.user)
  if not fp_user in ["Administrator", "Guest"]:
    organizer = vCalAddress(u'mailto:%s' % fp_user)
    organizer.params['cn'] = vText(fp_user.nextcloud_username)
    organizer.params['ROLE'] = vText('ORGANIZER')
    event.add('organizer', organizer)
  # ATTENDEE if participants
  """
    attendee_params = {
     "CUTYPE"   => "INDIVIDUAL",
     "ROLE"     => "REQ-PARTICIPANT",
     "PARTSTAT" => "NEEDS-ACTION",
     "RSVP"     => "TRUE",
     "CN"       => "Firstname Lastname",
     "X-NUM-GUESTS" => "0" }
  """        
  if doc.event_participants:
    if len(doc.event_participants) > 0:
      for _contact in doc.event_participants:
        if _contact.reference_doctype in ["Contact", "Customer", "Lead"]:
          if _contact.reference_doctype == "Contact":
            email = frappe.db.get_value("Contact", _contact.reference_docname, "email_id")
          elif _contact.reference_doctype == "Customer":
            email = frappe.db.get_value("Customer", _contact.reference_docname, "email_id")
          elif _contact.reference_doctype == "Lead":
            email = frappe.db.get_value("Lead", _contact.reference_docname, "email_id")
          contact = vCalAddress(u'mailto:%s' % email)
          contact.params['cn'] = vText(_contact.reference_docname)
          contact.params['partstat'] = vText('NEEDS-ACTION')
          contact.params['rsvp'] = vText(str(bool(_contact.send_email)).upper())  
        elif _contact.reference_doctype == "User":
          if not _contact.reference_docname in ["Administrator", "Guest"]:
            contact = vCalAddress(u'mailto:%s' % _contact.reference_docname)
            contact.params['cn'] = vText(_contact.reference_docname)
            contact.params['partstat'] = vText('NEEDS-ACTION')
            contact.params['rsvp'] = vText(str(bool(_contact.send_email)).upper())
          else:
            contact = vCalAddress(u'mailto:%s' % "")
            contact.params['cn'] = vText(_contact.reference_docname)
          if _contact.participant_type:
            if _contact.participant_type == "Chairperson":
              contact.params['ROLE'] = vText('CHAIR') 
            elif _contact.participant_type == "Required":
              contact.params['ROLE'] = vText('REQ-PARTICIPANT') 
            elif _contact.participant_type == "Optional":
              contact.params['ROLE'] = vText('OPT-PARTICIPANT')
            elif _contact.participant_type == "Non Participant":
              contact.params['ROLE'] = vText('NON-PARTICIPANT')
          else:
            contact.params['ROLE'] = vText('REQ-PARTICIPANT')
          if contact:
            event.add('attendee', contact)
  # Add Recurring events
  if doc.repeat_this_event:
    if doc.repeat_on:
      if not doc.repeat_till:
        if doc.repeat_on.lower() == 'weekly':
          sday = []
          if doc.monday: sday.append('MO')
          if doc.tuesday: sday.append('TU')
          if doc.wednesday: sday.append('WE')
          if doc.thursday: sday.append('TH')
          if doc.friday: sday.append('FR')
          if doc.saturday: sday.append('SA')
          if doc.sunday: sday.append('SU')
          if len(sday) > 0:  
            event.add('rrule', {'freq': [doc.repeat_on.lower()], 'byday': sday})
          else:
            event.add('rrule', {'freq': [doc.repeat_on.lower()]})
        else:
          event.add('rrule', {'freq': [doc.repeat_on.lower()]})
      else:
        dtuntil = datetime.strptime(doc.repeat_till, '%Y-%m-%d')
        dtuntil = datetime(dtuntil.year, dtuntil.month, dtuntil.day, tzinfo=madrid)
        if doc.repeat_on.lower() == 'weekly':
          sday = []
          if doc.monday: sday.append('MO')
          if doc.tuesday: sday.append('TU')
          if doc.wednesday: sday.append('WE')
          if doc.thursday: sday.append('TH')
          if doc.friday: sday.append('FR')
          if doc.saturday: sday.append('SA')
          if doc.sunday: sday.append('SU')
          if len(sday) > 0:  
            event.add('rrule', {'freq': [doc.repeat_on.lower()], 'byday': sday, 'until': [dtuntil]})
          else:
            event.add('rrule', {'freq': [doc.repeat_on.lower()], 'until': [dtuntil]})

  # Add event to iCalendar
  cal.add_component(event)
  # Save event
  calendar.save_event(cal.to_ical())
  doc.save()
  frappe.publish_progress(100, title='Event Progress', description='Synchronizing Event in NC')
  frappe.msgprint(_('Event created successfully.'))
  return 'Event created successfully.'

@frappe.whitelist()
def remove_caldav_event(doc, method=None):
  """
    Remove an event from a CalDAV server if it exists.

    Args:
        doc (frappe.model.Document): The document representing the event.
        client (caldav.DAVClient): The CalDAV client to use.

    Returns:
        str: A message indicating the result of the operation.
  """
  # If the document has no CalDAV ID URL, there is nothing to remove
  if not doc.caldav_id_url:
    return 'Document has no CalDAV ID URL.'
  # Get CalDav Data from logged in user
  fp_user = frappe.get_doc("User", frappe.session.user)
  if not fp_user.get('nextcloud_enable'):
    return
    
  client, url, username, password = make_caldav_session(fp_user)  
  
  if not client:
    frappe.throw(_('User has not calDAV credentials'))
    return 'User has not calDAV credentials'
    
  # Fetch the calendar
  calendar = client.calendar(url=doc.caldav_id_url)
  # If the calendar could not be found, return an error message
  if not calendar:
    return 'Failed to fetch calendar: ' + doc.caldav_id_url
  # Search for the event for events scheduled from yesterday to 30 days onwards. Not overdue
  start_date = datetime.now() - timedelta(days=1)  # Yesterday
  end_date = datetime.now() + timedelta(days=30)  # 30 days from now
  events = calendar.date_search(start=start_date, end=end_date)
  # Loop through the events
  for event in events:
    # If this event matches the document's event UID, remove it
    if event.vobject_instance.vevent.uid.value == doc.event_uid:
      event.delete()
      frappe.msgprint(_('Event removed successfully.'))
      return 'Event removed successfully.'

  # If no matching event was found, return a message indicating this
  frappe.throw(_('No matching event found.'))
  return 'No matching event found.'

def sync_outside_caldav():
  # Get All Users with CalDav Credentials
  caldav_users = frappe.get_list(
    doctype = "User",
    fields = ["name", "caldav_url", "nextcloud_username", "nextcloud_token"],
    filters = [['enabled', '=', 1], ['name', '!=', 'Guest'], ['name', '!=', 'Administrator'], ['nextcloud_username', '!=', '']]
  )
  if caldav_users:
    if len(caldav_users) > 0:
      # Array for include processed uuid events
      sel_uuid = []
      for caldav_user in caldav_users:
        # Get CalDav Session for selected caldav_user to connect
        caldav_client, caldav_url, user, token = make_caldav_session(caldav_user)
        if caldav_client == "Failed":
          return
        
        cal_principal = caldav_client.principal()
        # Fetching calendars from server
        calendars = cal_principal.calendars()
        if calendars:
          # Loop on CalDav User Calendars to check events scheduled from yesterday to 30 days onwards
          for c in calendars:
            sel_events = c.date_search(datetime.now().date()-timedelta(days=1), datetime.now().date()+timedelta(days=+30))
            # Loop through selected events by scheduled dates
            for url_event in sel_events:
              cal_url = str(url_event).replace("Event: https://", "https://" + user + ":" + token +"@")
              req = requests.get(cal_url)
              cal = Calendar.from_ical(req.text)
              # Sync CalDav calendar from OutSide Server
              for evento in cal.walk('vevent'):
                # Check if already processed uuid event
                if not evento.decoded('uid').decode("utf-8").lower() in sel_uuid:
                  # Add uuid event to processed events array
                  sel_uuid.append(evento.decoded('uid').decode("utf-8").lower())
                  # Processing event if dtstamp has changed or not in frappe events
                  fp_event = frappe.get_list(
                    doctype = 'Event',
                    fields = ['*'],
                    filters = [['docstatus', '<', 2], ['event_uid', '=', evento.decoded('uid').decode("utf-8").lower()]]
                  )
                  #print(evento.decoded('uid').decode("utf-8").lower(), len(fp_event))
                  
                  if fp_event:
                    # Check if dtstamp has changed meaning it has been updated on NextCloud   
                    if fp_event[0].event_stamp.strftime("%Y-%m-%d %H:%M:%S") != evento.decoded('dtstamp').astimezone().strftime("%Y-%m-%d %H:%M:%S"):
                      cal_event = frappe.get_doc("Event", fp_event[0].name)
                      # caldav_id_url
                      cal_event.caldav_id_url = str(c.url)
                      upd_event = prepare_fp_event(cal_event, evento)  
                      upd_event.save()
                      #print(upd_event.as_dict())
                  else:
                    #Create new event in Frappe
                    new_cal_event = frappe.new_doc("Event")
                    new_cal_event.caldav_id_url = str(c.url)
                    new_event = prepare_fp_event(new_cal_event, evento)
                    new_event.save()
                    frappe.db.commit()
                    #print(new_event.as_dict())
                    
def prepare_fp_event(event, cal_event):
  # Prepare event for Frappe
  """
  VEVENT(
   {
    'SUMMARY': vText('b'Modificacion en NC''),
    'DTSTART': <icalendar.prop.vDDDTypes object at 0xb5ac7210>,
    'DTSTAMP': <icalendar.prop.vDDDTypes object at 0xb34d7910>,
    'UID': vText('b'frappe2e1b86d90aefb1d0ff340b382acfa756@pibico.es''),
    'DESCRIPTION': vText('b'<div>Para ir completando programa\\, y modificando eventos\\, esta vez por PibiCo</div>''),
    'LOCATION': vText('b'Ubicacion''),
    'CATEGORIES': <icalendar.prop.vCategory object at 0xb34d7470>,
    'ATTENDEE': vCalAddress('b'mailto:francisco.alaez@pibico.es''),
    'ORGANIZER': vCalAddress('b'mailto:pibidesk@gmail.com''),
    'RRULE': vRecur(
           {
		    'FREQ': ['YEARLY'],
		    'BYMONTH': [9],
		    'UNTIL': [datetime.datetime(2021, 9, 15, 6, 48, tzinfo=<UTC>)]
		   }
          ),
   'SEQUENCE': 2,
   'LAST-MODIFIED': <icalendar.prop.vDDDTypes object at 0xb3411110>
   },
   VALARM(
    {
    'ACTION': vText('b'DISPLAY''),
    'TRIGGER': <icalendar.prop.vDDDTypes object at 0xb3411130>
    }
   )
  )
  """
  # event_type.  ALWAYS PUBLIC
  event.event_type = "Public"
  # sync_with_caldav. ALWAYS TRUE
  event.sync_with_caldav = 1
  # subject
  if not 'summary' in cal_event:
    event.subject = (_("Untitled event"))
  else:
    event.subject = cal_event.decoded('summary').decode("utf-8")

  # starts_on
  dtstart = None
  if isinstance(cal_event.decoded('dtstart'), datetime):
    event.all_day = False
    dtstart = cal_event.decoded('dtstart').astimezone()
    event.starts_on = dtstart.strftime("%Y-%m-%d %H:%M:%S")
  else:
    event.all_day = True
    dtstart = cal_event.decoded('dtstart')
    event.starts_on = dtstart.strftime("%Y-%m-%d")
  
  # ends_on
  event.ends_on = None
  if 'dtend' in cal_event:
    dtend = None
    if isinstance(cal_event.decoded('dtend'), datetime):
      dtend = cal_event.decoded('dtend').astimezone()
    else:
      dtend = cal_event.decoded('dtend')
    
    if dtend and dtend > dtstart:
      event.ends_on = dtend.strftime("%Y-%m-%d %H:%M:%S" if isinstance(dtend, datetime) else "%Y-%m-%d")
  
  # event_dtstamp
  event.event_stamp = cal_event.decoded('dtstamp').astimezone().strftime("%Y-%m-%d %H:%M:%S")
  # event_uid
  event.event_uid = cal_event.decoded('uid').decode("utf-8").lower()
  # description
  if 'description' in cal_event:
    event.description = cal_event.decoded('description').decode("utf-8")
  # location
  if 'location' in cal_event:
    event.location = cal_event.decoded('location').decode("utf-8")
  # event_category
  if not event.event_category:
    event.event_category = "Other"
  # event_participants child_table
  if 'attendee' in cal_event:
    for attendee in cal_event.get('attendee', []):
      contact = attendee.replace("mailto:", "")
      contact_name = frappe.db.get_value("Contact", {"email_id": contact})
      event_participants = {}
      if contact_name:
        isInvited = True
        if 'event_participants' in event.as_dict():
          for row in event.event_participants:
            if contact_name == row.reference_docname or contact == row.reference_docname:
              isInvited = False
        if isInvited:
          event_participants['reference_doctype'] = 'Contact'
          event_participants['reference_docname'] = contact_name
          if 'ROLE' in attendee.params:
            role = attendee.params['role']
            if role == 'REQ-PARTICIPANT':
              participant_type = 'Required'
            elif role == 'CHAIR':
              participant_type = 'Chairperson'
            elif role == 'OPT-PARTICIPANT':
              participant_type = 'Optional'
            elif role == 'NON-PARTICIPANT':
              participant_type = 'Non Participant'
            if participant_type:
              event_participants['participant_type'] = participant_type  
          if 'CN' in attendee.params:
            print(attendee.params['cn'])
          if 'PARTSTAT' in attendee.params:
            partstat = attendee.params['partstat']
            if partstat == 'ACCEPTED':
              invitation_accepted = True
              event_participants['invitation_accepted'] = invitation_accepted
          if 'RSVP' in attendee.params:
            rsvp = attendee.params['rsvp']
            if rsvp == 'TRUE':
              send_email = True
            else:
              send_email = False
            if send_email:
              event_participants['send_email'] = send_email    
          
          event.append('event_participants', event_participants)
  # For future development  
  if 'rrule' in cal_event:
    """ {'FREQ': ['WEEKLY'], 'UNTIL': [datetime.datetime(2021, 10, 3, 0, 0)], 'BYDAY': ['TU', 'TH', 'SA']} """
    event.repeat_this_event = 1
    rule = cal_event.get('rrule')
    if rule:
      rrule = dict(rule)
      if 'FREQ' in rrule:
        frequency = rrule['FREQ'][0].lower().capitalize()
        event.repeat_on = frequency
        if frequency == "Weekly":
          if 'BYDAY' in rrule:
            if 'MO' in rrule['BYDAY']:
              event.monday = True             
            if 'TU' in rrule['BYDAY']:
              event.tuesday = True
            if 'WE' in rrule['BYDAY']:
              event.wednesday = True
            if 'TH' in rrule['BYDAY']:
              event.thursday = True
            if 'FR' in rrule['BYDAY']:
              event.friday = True
            if 'SA' in rrule['BYDAY']:
              event.saturday = True
            if 'SU' in rrule['BYDAY']:
              event.sunday = True 
      if 'UNTIL' in rrule:
        event.repeat_till = rrule['UNTIL'][0].strftime("%Y-%m-%d")
                                  
  #print(event.as_dict())
  return event

def make_caldav_session(user):
    """
    Create a CalDAV session for the given user.
    Args:
        user (User): The user for whom to create a CalDAV session.
    Returns:
        tuple: A 4-tuple containing the CalDAV client, the CalDAV URL, the username,
            and the password. If the session could not be created, the tuple contains
            an error message and three None values.
    """
    # Validate the necessary attributes
    if not (user.caldav_url and user.nextcloud_username and user.nextcloud_token):
        return 'Failed', None, None, None

    # Form the CalDAV URL
    username = user.nextcloud_username
    principals = user.caldav_url
    if principals[-1] == "/":
        url = principals + "users/" + username
    else:
        url = principals + "/users/" + username

    # Get the decrypted password
    password = get_decrypted_password('User', user.name, 'nextcloud_token', False)
    if not password:
        return 'Failed to decrypt password', None, None, None

    # Set connection to caldav calendar with CalDav user credentials
    client = caldav.DAVClient(url=url, username=username, password=password)

    return client, url, username, password