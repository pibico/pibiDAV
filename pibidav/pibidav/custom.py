# -*- coding: utf-8 -*-
# Copyright (c) 2022, PibiCo and contributors
# For license information, please see license.txt
from __future__ import unicode_literals
import frappe
from frappe import _, msgprint, throw, enqueue
from frappe.utils import cint, cstr

import json, time, requests, sys, hashlib
from datetime import date, datetime, timedelta

import pibidav.pibidav.nextcloud as nextcloud

from frappe.utils.password import get_decrypted_password
from frappe.utils.file_manager import get_file_path

import frappe.desk.doctype.tag.tag as tag

@frappe.whitelist()
def checkNCuser():
  ncuser = frappe.get_value("NextCloud Settings", "NextCloud Settings", "nc_backup_username")
  loggeduser = frappe.get_value("User", frappe.session.user, "nextcloud_username")
  if ncuser == loggeduser:
    return True
  else:
    return False

@frappe.whitelist()
def doCreateFolder(doctype):
  data = frappe.db.get_value("Reference Item", {"parent": "NextCloud Settings", "reference_doctype": doctype},['create_nc_folder','nc_enable'], as_dict = 1)
  if data is None:
    return False
  if data.create_nc_folder and data.nc_enable:
    return True
  else:
    return False

@frappe.whitelist()
def create_nc_folder(dt, dn, abbr, strmain, folder_set, sharing_option=None, secret=None):
  doc = frappe.get_doc(doctype=dt, docname=dn)
  ## Check docs excluded and included in the NC Integration
  docs_excluded = frappe.get_value("NextCloud Settings", "NextCloud Settings", "nc_doctype_excluded")
  docs_included = frappe.get_value("NextCloud Settings", "NextCloud Settings", "nc_doctype_included")
  nc_url = frappe.get_value("NextCloud Settings", "NextCloud Settings", "nc_backup_url")
  if nc_url[-1] != '/': nc_url += '/'
  
  if dt in docs_excluded or not dt in docs_included:
    return "DocType not in NC integration {}".format(docs_included)
  
  data = frappe.db.get_value("Reference Item", {"parent": "NextCloud Settings", "reference_doctype": dt},['nc_folder','create_nc_folder', 'nc_enable'], as_dict = 1)
  node_name = folder_set.strip()
  path = data.nc_folder
  
  if path is None:
    return "Failed. Not defined the Default destination Folder in NC Settings"
    
  if not data.nc_enable:
    return "Failed. Not enabled NextCloud Integration in Addon"
      
  if data.create_nc_folder and data.nc_folder != '' and data.folder_set != '':
    pibidav = check_addon(dt,dn)

    ## Get default data from NextCloud Settings
    ## Assign data to variables for creating folders in NC
    strmain = strmain.strip()
    abbreviation = abbr.strip()  
    digits = 3
    if path[-1] != '/':
      path += '/'
    if path[0] != '/':
      return frappe.throw(_("{} Root Destination Folder must start with /. Correct in your NextCloud Settings and retry".format(path)))
    
    root_path = "{}{} {}/".format(path, abbreviation, strmain)

    ## Create Folders if needed data are filled in logged in as superuser in NC
    if node_name and path and abbreviation and strmain:
      create_nc_dirs(node_name, path, abbreviation, strmain, digits)
      nclog = make_nc_session()
      ## Get data fileid from dir
      fileinfo = nclog.file_info(root_path, properties=['{http://owncloud.org/ns}fileid'])
      if fileinfo:
        fileid = fileinfo.attributes['{http://owncloud.org/ns}fileid']
        ## Create internal Link
        intlink = nc_url + 'f/' + fileid
        nc_folder_internal_link = '<a href="'
        nc_folder_internal_link += intlink + '" target="_blank">' + intlink + '</a>' 
        pibidav.nc_folder_internal_link = nc_folder_internal_link      

      pibidav.nc_folder = root_path
      pibidav.nc_folder_internal_link = nc_folder_internal_link      

      ## Create shared Link
      if secret is not None or sharing_option is not None:
        if sharing_option is None:
          pibidav.save()
          return
        share_option = sharing_option.split('-')
        share_option = int(share_option[0])
        share_link = nclog.share_file_with_link(path=root_path)
        if share_link:
          ## Create public link
          publink = share_link.get_link()
          nc_folder_share_link = '<a href="'
          nc_folder_share_link += publink +  '" target="_blank">' + publink + '</a>'
          pibidav.nc_folder_share_link = nc_folder_share_link
          intlink = share_link.get_id()
          ## Change perms from read to update
          #oth = {'perms': sharing_option, 'secret': secret}
          oth = {}
          if share_option:
            oth = { 'perms': share_option }
            pibidav.sharing_option = sharing_option
          if secret is not None and secret != '':
            oth['password'] = str(secret)
            pibidav.secret = secret
          nclog.update_share(intlink, **oth)

      pibidav.save()
      nclog.logout()

@frappe.whitelist()
def get_native(parent, filetype):
  native_list = frappe.db.get_list('Deliverable Item',
    filters={
        'docstatus': ['<', 2],
        'parent': parent,
        'filetype': filetype
    },
    fields=['attachment','delivery_date'],
    order_by='delivery_date desc'
  )

  return native_list

@frappe.whitelist()
def check_nextcloud():
  doc = frappe.get_doc("NextCloud Settings", "NextCloud Settings")
  nc_url = doc.nc_backup_url
  nc_username = doc.nc_backup_username
  nc_token = get_decrypted_password('NextCloud Settings', doc.name, 'nc_backup_token', True)
  try:
    nc = nextcloud.Client(nc_url)
    nc.login(nc_username, nc_token)
    frappe.msgprint(_("NextCloud Credentials are correct"))
    nc.logout()
  except:
    frappe.throw(_("NextCloud Credentials not correct, please rectify"))

def make_nc_session_user(user):
  if user.nextcloud_enable:
    if user.nextcloud_url and user.nextcloud_username and user.nextcloud_token:
      nc_token = get_decrypted_password('User', user.name, 'nextcloud_token', False)
      try:
        _session = nextcloud.Client(user.nextcloud_url)
        _session.login(user.nextcloud_username, nc_token)
        return _session
      except Exception as err:
        frappe.throw(_("Error in login in NC: " + str(err)))
        return "Failed" 
    else:
      frappe.msgprint(_("User has errors in credentials for NC"))
      return "Failed" 
  else:
    frappe.msgprint(_("User has not enabled NC"))
    return "Failed"

@frappe.whitelist()
def get_nc_nodes(path):
  nc_user = frappe.get_doc("User", frappe.session.user)
  nc = make_nc_session_user(nc_user)
  
  if nc == "Failed":
    return [{"title": "Check NextCloud User Settings"}]
  
  ## Get DAV List from NC Server
  """nc_nodes = nc.list(
    path,
    depth=1,
    properties=[
      '{DAV:}getetag',
      '{DAV:}getlastmodified',
      '{http://owncloud.org/ns}fileid'
    ]
  )"""
  nc_nodes = nc.list(path, depth=1, properties=['{http://owncloud.org/ns}fileid'])
        
  nodes = []
  for row in nc_nodes:
    node = {}
    if row.file_type == 'dir':
      folder = row.path[:-1]
      pos = folder.rfind("/")
      node['folder'] = 1
      node['title'] = folder[pos+1:]
    else:
      folder = row.path
      pos = folder.rfind("/")
      node['title'] = folder[pos+1:]
    node['path'] = row.path
    node['fileid'] = row.attributes['{http://owncloud.org/ns}fileid']
    nodes.append(node)

  #nc.logout()
        
  return nodes
  
def tag_file_fp(doc, method=None):
  if doc.attached_to_doctype and doc.attached_to_name:
    dctype = doc.attached_to_doctype
    dcname = doc.attached_to_name
    ## Get DocType attached to File
    dt = frappe.get_doc(dctype, dcname)
    ## Assign default tag to DocType name to the tag list 
    tag_list = [dctype]
    ## Add user tags to tag list if any
    if hasattr(dt, "_user_tags"):
      if dt._user_tags is not None:
        if len(dt._user_tags) > 0:
          user_tags = dt._user_tags.split(',')
          for lbl in user_tags:
            if lbl is not None and lbl not in tag_list and lbl != "": tag_list.append(lbl)
    ## Get all docfields for tagging the DocType from NextCloud Settings
    _fields_to_tag = frappe.db.get_value("Reference Item", {"parent": "NextCloud Settings", "reference_doctype": dctype}, "reference_docfield")
    ## Assign tags to DocType in Frappe (limited length 60 chars due to NextCloud Limits)
    if _fields_to_tag:
      fields_to_tag = _fields_to_tag.split(',')
      for item in fields_to_tag:
        try:
          if not ',' in dt.get(item):
            fp_tag = dt.get(item) #frappe.db.get_value(dctype, dcname, item)
            if fp_tag is not None and fp_tag not in tag_list and fp_tag != "": tag_list.append(fp_tag)
            for el in tag_list:
              if el != '' and el is not None and len(el) > 0 and len(el) <= 60: tag.add_tag(el, "File", doc.name)  
        except:
          pass
    else:
      tag.add_tag(dctype, "File", doc.name)
  else:
    tag_list = []
    
  return tag_list

def get_tagid(session, tag):
  taglist = session.list_tags()
  for item in taglist:
    if item.attributes['{http://owncloud.org/ns}display-name'] == tag:
      tag_id = item.attributes['{http://owncloud.org/ns}id']
      return tag_id

def tag_file_nc(nc_session, filepath, tags):
  nc_tags = []
  ## Get fileid fron nc uploaded file
  remotefile = nc_session.file_info(filepath, properties=['{http://owncloud.org/ns}fileid'])
  if remotefile:
    fileid = remotefile.attributes['{http://owncloud.org/ns}fileid']
    ## Write tags to uploaded file
    try:
      for tag in tags:
        res = nc_session.add_tag(tag)
        if res == 409:
          tagid = get_tagid(nc_session, tag)
        else:
          tag_res = res.split('/')
          tagid = tag_res[len(tag_res)-1]
        if not tagid in nc_tags:
            nc_tags.append({"display-name": tag, "tagid": tagid})
        ## Add tag to file
        nc_session.assign_tag_to_file(fileid, tagid)
    except Exception as err:
      #return err
      nc_tags = []
      pass
  return fileid, nc_tags
  
@frappe.whitelist()
def upload_file_to_nc(doc, method=None):
  ## Tag File in Frappe
  _tag_list = tag_file_fp(doc)
  ## Method only valid for Files, not WebSites
  if 'http' in doc.file_url:
    return
  ## Check docs excluded and included in the NC Integration
  docs_excluded = frappe.get_value("NextCloud Settings", "NextCloud Settings", "nc_doctype_excluded")
  ## docs_included = frappe.get_value("NextCloud Settings", "NextCloud Settings", "nc_doctype_included")
  nc_url = frappe.get_value("NextCloud Settings", "NextCloud Settings", "nc_backup_url")
  if not nc_url[-1] == '/': nc_url += '/'
  ## Check the file attached to parent docType and its inclusion in the list 
  dt = doc.attached_to_doctype
  if docs_excluded and dt:
    if dt in docs_excluded:
      return
  ## Get name of file attached to doctype and file_name and local server path
  dn = doc.attached_to_name
  file_name = doc.file_name
  local_path = get_file_path(file_name)
  ## Method only valid for docTypes not being Files
  if dt != 'File' and dn:
    ## check whether document has NC addon extension active
    document = check_addon(dt,dn)
    
    ## Check for pibiDocs deliverable data on Addon -- This is valid only for pibiDocs App installed
    if dt == "HS Document":
      deliverable_type = ""
      if hasattr(document, "deliverable_type"):
        if document.deliverable_type:
          deliverable_type = document.deliverable_type 
          ## Fill File with deliverable type and tag
          doc.deliverable_type = deliverable_type
          tag.add_tag(deliverable_type, "File", doc.name)
          _tag_list.append(deliverable_type)
    
    ## Check whether doctype has NextCloud Integration active
    if not hasattr(document, "nc_enable"):
      return
    ## Check if document has destination folder
    if document.nc_enable and not document.nc_folder:
      return frappe.msgprint(_("File uploaded only to Frappe. No NC Destination Folder Given"))
      
    ## Continues if NC Integration is enabled and NC Destination Folder given
    if document.nc_enable and document.nc_folder:
      local_site = frappe.utils.get_url()
      ## Get current logged user and makes session in NC
      nc_user = frappe.get_doc("User", frappe.session.user)
      nc = make_nc_session_user(nc_user)
      if nc == "Failed":
        return frappe.msgprint(_("Error in NC Login"))
      ## Continues to upload files to NC      
      nc_path = document.nc_folder + file_name
      nc_args = {
		    'remote_path': nc_path,
		    'local_source_file': local_path
	    }
      ## Upload file to NC
      enqueue(method=nc.put_file, queue='short',timeout=3000,now=True,**nc_args)
      ## Get Shared Link from NC
      share = enqueue(method=nc.share_file_with_link, queue='short', timeout=600, now=True, path=nc_path)
      ## Update and save File in frappe updated with NC data
      doc.uploaded_to_nextcloud = 1
      doc.folder_path = document.nc_folder
      doc.share_link = share.get_link()
      
      fileid, nctags = tag_file_nc(nc, nc_path, _tag_list)
      doc.fileid = fileid
      ## Register nc tagids into frappe tags
      if len(nctags) > 0:
        for strtag in nctags:
          fptag = frappe.get_doc("Tag", strtag['display-name'])
          if fptag:
            fptag.uploaded_to_nextcloud = 1
            fptag.tagid = strtag['tagid']
            fptag.save()
            
      doc.save()
      nc.logout()
        
      return {'fname': doc, 'local_path': local_path, 'local_site': share.get_link()}
  else:
    return

@frappe.whitelist()
def get_nc_settings(doctype):
  use_default = frappe.get_list("Reference Item", {"parent": "NextCloud Settings", "reference_doctype": doctype}, "use_default_folder")
  if use_default:
    if use_default[0]['use_default_folder']:
      path = frappe.get_list("Reference Item", {"parent": "NextCloud Settings", "reference_doctype": doctype}, "nc_folder")
      nc_folder = path[0]['nc_folder']
      if nc_folder[-1] != '/': nc_folder + '/'
      return nc_folder

@frappe.whitelist()
def update_attachment_item(dt, dn):
  nc_url = frappe.get_value("NextCloud Settings", "NextCloud Settings", "nc_backup_url")
  if not nc_url[-1] == '/': nc_url += '/'
  ## Get a list of all files attached to doctype and uploaded to NC
  attached_to_doctype = frappe.get_list(
    doctype = "File",
    fields = ["*"],
    filters = [
      ["attached_to_doctype", "=", dt],
      ["attached_to_name", "=", dn],
      ["uploaded_to_nextcloud", "=", 1],
      ["docstatus", "<", 1]
    ]
  )
  
  doc = frappe.get_doc("PibiDAV Addon", "pbc_" + dn)
  if doc is None:
    return

  if len(attached_to_doctype) > 0 and hasattr(doc, "nc_enable"):
    if hasattr(doc, "attachment_item"):
      attachment_item = doc.attachment_item
      if len(attachment_item) > 0:
        ## Update attachments uploaded to NC
        ## Get all files attached to docname
        _attachment_item = []
        for item in attachment_item:
          if item.attachment not in _attachment_item:
            _attachment_item.append(item.attachment)
        for row in attached_to_doctype:
          if row.name not in _attachment_item:
            nc_link = '<a href="'
            nc_link += nc_url + 'apps/files/?fileid=' + row.fileid
            nc_link += '" target="_blank">NextCloud</a>' 
            json_item = {
              "attachment": row.name,
              "filename": row.file_name,
              "uploaded_to_nc": row.uploaded_to_nextcloud,
              "nc_path": row.folder_path,
              "nc_link": row.share_link,
              "nc_private": nc_url + 'apps/files/?fileid=' + row.fileid,
              "nc_url": nc_link
            }
            doc.append("attachment_item", json_item)
        doc.save()
        frappe.db.commit()  
      else:
        ## Create new attachment item
        for row in attached_to_doctype:
          nc_link = '<a href="'
          nc_link += nc_url + 'apps/files/?fileid=' + row.fileid
          nc_link += '" target="_blank">NextCloud</a>'
          json_item = {
            "attachment": row.name,
            "filename": row.file_name,
            "uploaded_to_nc": row.uploaded_to_nextcloud,
            "nc_path": row.folder_path,
            "nc_link": row.share_link,
            "nc_private": nc_url + 'apps/files/?fileid=' + row.fileid,
            "nc_url": nc_link
          }
          doc.append("attachment_item", json_item)
          doc.save()
          frappe.db.commit()

@frappe.whitelist()
def upload_nc_file(remote_path, local_file):
  ## Get bench path
  fname = frappe.get_doc('File', local_file)
  ## Only applicable if File is not attached to any doctype
  if not fname.attached_to_doctype == 'File' or 'http' in fname.file_url:
    return

  local_site = frappe.utils.get_url()
  local_path = get_file_path(local_file)
  nc_user = frappe.get_doc("User", frappe.session.user)
  nc = make_nc_session_user(nc_user)
  
  if nc == "Failed":
    return frappe.msgprint(_("Error in NC Login"))
     
  nc_args = {
    'remote_path': remote_path,
    'local_source_file': local_path
  }
  enqueue(method=nc.put_file,queue='short',timeout=300,now=True,**nc_args) 

  fname.uploaded_to_nextcloud = 1
  fname.folder_path = remote_path.replace(fname.file_name, '')
  fname.save()

  nc.logout()

  return {'fname': fname, 'local_path': local_path, 'local_site': local_site}

@frappe.whitelist()
def get_nc_files_in_folder(folder, start=0, page_length=20):
  start = cint(start)
  page_length = cint(page_length)
  if folder == 0: folder = "/"

  nc_user = frappe.get_doc("User", frappe.session.user)

  nc = make_nc_session_user(nc_user)
  
  if nc == "Failed":
    return {"files": ["Enable NextCloud on User Settings"],
            "has_more": 0
            }

  ## Get DAV List from NC Server
  #nc_nodes = nc.list(path, depth=1, properties=['{DAV:}getetag','{DAV:}getlastmodified','{http://owncloud.org/ns}fileid'])
  nc_nodes = nc.list(folder, depth=1, properties=['{http://owncloud.org/ns}fileid', '{DAV:}getlastmodified'])

  nodes = []
  for row in nc_nodes:
    node = {}
    if row.file_type == 'dir':
      folder = row.path[:-1]
      pos = folder.rfind("/")
      node['is_folder'] = 1
      node['file_name'] = folder[pos+1:]
    else:
      folder = row.path
      pos = folder.rfind("/")
      node['is_folder'] = 0
      node['file_name'] = folder[pos+1:]
    node['name'] = row.path
    node['file_url'] = row.attributes['{http://owncloud.org/ns}fileid']
    node['modified'] = row.attributes['{DAV:}getlastmodified']
    nodes.append(node)
    start += 1
    if start == page_length:
      break

  #nc.logout()
        
  return {
    'files': nodes[:page_length],
    'has_more': len(nodes) > page_length
  }

@frappe.whitelist()
def make_nc_session():
    nc_settings = frappe.get_doc('NextCloud Settings', 'NextCloud Settings')
    if nc_settings.nc_backup_enable:
      nc_token = get_decrypted_password('NextCloud Settings', 'NextCloud Settings', 'nc_backup_token', True)
      args = {
        "verify_certs": False
      }
      session = nextcloud.Client(nc_settings.nc_backup_url, **args)
      session.login(nc_settings.nc_backup_username, nc_token)
      return session
    else:
      frappe.msgprint(_("NextCloud Integration not Enabled"))  
    
@frappe.whitelist()
def create_nc_group(alias):
  ## Login in NC as superuser
  nclient = make_nc_session()
  ## Create NC Group with name alias
  ## Check if group exists first
  doGroup = nclient.group_exists(alias.upper())
  if doGroup:
    frappe.msgprint(_("NC Group Already Exists"))
  else:
    res = nclient.create_group(alias.upper())
    if res:
      frappe.msgprint(_("NC Group Created"))
    else:
      frappe.msgprint(_("Error Creating NC Group"))  
    
@frappe.whitelist()
def create_nc_dirs(node_name, path, abbrv, strmain, digits):
  """ Create folders in NC Instance on path
    node_name = '(BPJ) Project' 
    path = "/Projects/"
    abbrv = "PRJ22PBC"
    ref_doctype = "pb_Project" ??
    strmain = "NC Integration" """
  
  ## Include tags as Project Name, abbreviation, Customer
  ## ----
  
  ## Login in NC as superuser
  nclient = make_nc_session()
  ## Create root path and recursively the rest as per origin structure in selected node in folder set
  root_node = node_name
  n = int(digits)
  """
  ## Check if selected node is root or not
  root_parent = frappe.db.get_value("Folder Set", {"name": node_name}, "root_parent")
  if root_parent == root_node:
  ## Change title depending on ref_doctype
    root_path = path + abbrv + " " + strmain + "/" 
  else:
    root_path = path + node_name[n+1:] + "/"
  """
  ## Root path is different from the rest of nodes
  root_path = "{}{} {}/".format(path, abbrv, strmain)
  ## Create first node in NC  
  folder = nclient.mkdir(root_path)
  ## If dir is created in NC, continues recursively with its children
  if folder:
    children = get_children(nclient, root_node, root_path, abbrv, n)
  else:
    frappe.msgprint(_("Error creating root folder in NC"))

  return frappe.msgprint(_("Successfully Created Folders in NC"))

def get_children(session, parent_node, parent_path, abr, n):
  children_list = []
  ## Get all children folders only for given node
  children = frappe.get_list(
    doctype = "Folder Set",
    filters = {
      "is_group": 1,
      "parent_folder_set": parent_node
    },
    fields = ["name", "parent_folder_set", "is_group"],
    order_by = "creation asc"
  )
  ## Get recursively the rest of children an create folders in NC
  if len(children) > 0:
    for child in children:
      if child.name not in children_list: children_list.append(child.name)
      parent_path_child = "{}{} {}/".format(parent_path, abr, child.name[n+1:])
      ## Create folder in NC
      folder = session.mkdir(parent_path_child)
      ## If folder is created continues recursively
      if folder:
        get_children(session, child.name, parent_path_child, abr, n)
      else:
        frappe.msgprint(_("Error creating child folder in NC"))

  return children_list

def check_addon(dt, dn):
  ## First we'll check and create pibiDAV Addon doctype related
  addon_list = frappe.db.get_list('PibiDAV Addon',
    filters={
      'docstatus': ['<', 2],
      'name': "pbc_{}".format(dn)
    },
    fields=['*']
  )
  if len(addon_list) == 0: 
    ## Create pibiDAV Addon doctype
    pibidav = frappe.new_doc("PibiDAV Addon")
    pibidav.ref_doctype = dt
    pibidav.ref_docname = dn
    ## Get default data from NextCloud Settings
    settings = frappe.db.get_value("Reference Item", {"parent": "NextCloud Settings", "reference_doctype": dt},['nc_folder'], as_dict = 1)
    if settings is not None:
      if settings.use_default_folder and settings.nc_folder:
        pibidav.nc_folder = settings.nc_folder
        pibidav.insert()
        frappe.db.commit()
  else:
    pibidav = frappe.get_doc("PibiDAV Addon", "pbc_{}".format(dn))
    
  return pibidav