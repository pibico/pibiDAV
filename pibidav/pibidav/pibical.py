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
  caldav_client, caldav_url, caldav_username, caldav_token = make_caldav_session(fp_user)
  if caldav_client == "Failed":
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
    frappe.msgprint(_("Server has no calendars for your user"))
    
  return arr_cal

@frappe.whitelist()
def sync_caldav_event_by_user(doc, method=None):
  if doc.sync_with_caldav:
    # Get CalDav Data from logged in user
    fp_user = frappe.get_doc("User", frappe.session.user)
    # Continue if CalDav Data exists on logged in user
    if fp_user.caldav_url and fp_user.nextcloud_username and fp_user.nextcloud_token:
      # Check if selected calendar matches with previously recorded and delete event if not matching
      if doc.caldav_id_url:
        s_cal = doc.caldav_id_url.split("/")
        ocal = s_cal[len(s_cal)-2]
        if '_shared_by_' in ocal:
          pos = ocal.find("_shared_by_")
          ocal = ocal[0:pos]
        if doc.caldav_id_calendar == None:
          doc.caldav_id_url = doc.event_uid = doc.event_stamp = None
        else:
          if not ocal in doc.caldav_id_calendar or not 'frappe' in doc.event_uid:
            args = { "doc": doc }
            #remove_caldav_event(doc)
            enqueue(method=remove_caldav_event, queue='short', timeout=300, now=True, *args)
            doc.caldav_id_url = doc.event_uid = doc.event_stamp = None
      # Fill CalDav URL with selected CalDav Calendar
      doc.caldav_id_url = doc.caldav_id_calendar
      # Create uid for new events
      str_uid = datetime.now().strftime("%Y%m%dT%H%M%S")
      uidstamp = 'frappe' + hashlib.md5(str_uid.encode('utf-8')).hexdigest() + '@pibico.es'
      if not doc.event_uid:
        doc.event_uid = uidstamp
      else:
        uidstamp = doc.event_uid
      ucal = str(doc.caldav_id_url).split("/")
      # Get Calendar Name from URL as last portion in URL
      cal_name = ucal[len(ucal)-2]
      # Set connection to caldav calendar with CalDav user credentials
      caldav_client, caldav_url, caldav_username, caldav_token = make_caldav_session(fp_user)
      if caldav_client == "Failed":
        return
    
      cal_principal = caldav_client.principal()
      # Fetching calendars from server
      calendars = cal_principal.calendars()
      if calendars:
        # Loop on CalDav User Calendars to check if event exists
        for c in calendars:
          scal = str(c.url).split("/")
          str_user = scal[len(scal)-3]
          str_cal = scal[len(scal)-2]
          # Check if CalDav calendar name or calendar name shared by another user matches
          if str_cal == cal_name or str_cal + "_shared_by_"  in str(doc.caldav_id_url):
            # Prepare iCalendar Event
            # Initialise iCalendar
            cal = Calendar()
            cal.add('prodid', '-//pibiDAV//pibico.org//')
            cal.add('version', '2.0')
            # Initialize Event
            event = Event()
            # Fill data to Event
            # UID  
            event['uid'] = uidstamp
            # SUMMARY from Subject
            event.add('summary', doc.subject)
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
            # DESCRIPTION if any
            if doc.description: event.add('description', doc.description)
            # LOCATION if any
            if doc.location: event.add('location', doc.location)
            # CATEGORIES from event_category
            category = _(doc.event_category)
            event.add('categories', [category])
            # ORGANIZER from user session
            if not fp_user in ["Administrator", "Guest"]:
              organizer = vCalAddress(u'mailto:%s' % fp_user)
              organizer.params['cn'] = vText(fp_user.nextcloud_username)
              organizer.params['ROLE'] = vText('ORGANIZER')
              event.add('organizer', organizer)
            # ATTENDEE if participants
            """
            attendee_params = { "CUTYPE"   => "INDIVIDUAL",
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
            # Save/Update Frappe Event
            c.save_event(cal.to_ical())
            doc.save()
            frappe.db.commit()
            # This portion makes events not saving event doc and thus not existing in database and promoting double entries
            """
            # Get all events in matched calendar just to inform about existing or new event
            all_events = c.events()
            args = {
                "all_events": all_events,
                "caldav_username": caldav_username,
                "caldav_token": caldav_token,
                "uidstamp": uidstamp
            }
            enqueue(method=check_event_exists, queue='long', timeout=600, now=True, **args)
            """
  else:
    if doc.event_uid:
      args = {"doc": doc}
      #remove_caldav_event(doc)
      enqueue(method=remove_caldav_event, queue='short', timeout=300, now=True, *args)
      doc.caldav_id_url = doc.event_uid = doc.event_stamp = None
      doc.save()
      frappe.db.commit()

def check_event_exists(all_events, caldav_username, caldav_token, uidstamp):
  # Loop through events to check if current event exists
  for url_event in all_events:
    cal_url = str(url_event).replace("Event: https://", "https://" + caldav_username + ":" + caldav_token + "@")
    req = requests.get(cal_url)
    cal = Calendar.from_ical(req.text)
    for evento in cal.walk('vevent'):
      if uidstamp in str(evento.decoded('uid')):
        # print(evento.decoded('summary'), evento.decoded('attendee'), evento.decoded('dtstart'), evento.decoded('dtend'), evento.decoded('dtstamp'))  
        frappe.msgprint(_("Updated/Created Event in Calendar"))
        return

@frappe.whitelist()
def remove_caldav_event(doc, method=None):
  if doc.sync_with_caldav and doc.event_uid:
    # Get CalDav Data from logged in user
    fp_user = frappe.get_doc("User", frappe.session.user)
    # Continue if CalDav Data exists on logged in user
    if fp_user.caldav_url and fp_user.nextcloud_username and fp_user.nextcloud_token:
      uidstamp = doc.event_uid
      cal_name = None
      if doc.caldav_id_url:
        ucal = str(doc.caldav_id_url).split("/")
        # Get Calendar Name from URL as last portion in URL
        cal_name = ucal[len(ucal)-2]
      
      # Get CalDav URL, CalDav User and Token
      if fp_user.caldav_url[-1] == "/":
        caldav_url = fp_user.caldav_url + "users/" + fp_user.nextcloud_username
      else:
        caldav_url = fp_user.caldav_url + "/users/" + fp_user.nextcloud_username
      caldav_username = fp_user.nextcloud_username
      caldav_token = get_decrypted_password('User', frappe.session.user, 'nextcloud_token', False)
      # Set connection to caldav calendar with CalDav user credentials
      caldav_client = caldav.DAVClient(url=caldav_url, username=caldav_username, password=caldav_token)
      
      cal_principal = caldav_client.principal()
      # Fetching calendars from server
      calendars = cal_principal.calendars()
      doExists = False
      if calendars:
        # Loop on CalDav User Calendars to check if event exists
        for c in calendars:
          scal = str(c.url).split("/")
          str_user = scal[len(scal)-3]
          str_cal = scal[len(scal)-2]
          # Check if CalDav calendar name or calendar name shared by another user matches
          if str_cal == cal_name or str_cal + "_shared_by_"  in str(doc.caldav_id_url):
            # Get all events in matched calendar just to inform about existing or new event
            all_events = c.events()
            # Loop through events to check if current event exists
            for url_event in all_events:
              cal_url = str(url_event).replace("Event: https://", "https://" + caldav_username + ":" + caldav_token +"@")
              req = requests.get(cal_url)
              cal = Calendar.from_ical(req.text)
              for evento in cal.walk('vevent'):
                if uidstamp in str(evento.decoded('uid').decode('utf-8').lower()):
                  doExists = True
                  break
              if doExists:
                url_event.delete()
                frappe.msgprint(_("Deleted Event in CalDav Calendar ") + str(c.name))
                break

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
                  print(evento.decoded('uid').decode("utf-8").lower(), len(fp_event))
                  
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
  if isinstance(cal_event.decoded('dtstart'), datetime):
    event.all_day = False
    event.starts_on = cal_event.decoded('dtstart').astimezone().strftime("%Y-%m-%d %H:%M:%S")
  else:
    event.all_day = True
    event.starts_on = cal_event.decoded('dtstart').strftime("%Y-%m-%d")
  # ends_on
  if 'dtend' in cal_event:
    if isinstance(cal_event.decoded('dtend'), datetime):
      event.ends_on = cal_event.decoded('dtend').astimezone().strftime("%Y-%m-%d %H:%M:%S")
    else:
      event.ends_on = cal_event.decoded('dtend').strftime("%Y-%m-%d")
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
  if user.caldav_url and user.nextcloud_username and user.nextcloud_token:
    caldav_username = user.nextcloud_username
    caldav_principals = user.caldav_url
    if caldav_principals[-1] == "/":
      caldav_url = caldav_principals + "users/" + caldav_username
    else:
      caldav_url = caldav_principals + "/users/" + caldav_username
    caldav_token = get_decrypted_password('User', user.name, 'nextcloud_token', False)
    # Set connection to caldav calendar with CalDav user credentials
    caldav_client = caldav.DAVClient(url=caldav_url, username=caldav_username, password=caldav_token)

    return caldav_client, caldav_url, caldav_username, caldav_token
  else:
    return 'Failed', None, None, None