# Copyright (c) 2022, pibiCo and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _, msgprint, throw

from frappe.utils.background_jobs import enqueue
from frappe.utils.backups import new_backup
from frappe.integrations.offsite_backup_utils import send_email, validate_file_size

import pibidav.pibidav.nextcloud as nextcloud

from frappe.utils.password import get_decrypted_password
from frappe.utils.file_manager import get_file_path

import requests, os, datetime
from rq.timeouts import JobTimeoutException
from urllib.parse import urlparse

class NextCloudSettings(Document):
  error_log = []
  failed_uploads = []
  timeout = 1500
  
  def start_taking_backup(self, retry_count=0, upload_db_backup=True):
    try:
      if self.nc_backup_enable:
        validate_file_size()
        self.backup_to_nextcloud(upload_db_backup)
        if self.error_log:
          raise Exception
        if self.send_email_for_successful_backup:
          send_email(True, "NextCloud", "NextCloud Settings", "send_notifications_to")
    except JobTimeoutException:
      if retry_count < 2:
        timeout += 1500
        args = {
          "retry_count": retry_count + 1,
          "upload_db_backup": False ## considering till worker timeout db backup is uploaded 
        }
        enqueue(self.start_taking_backup, queue='long', timeout=timeout, **args) ##
    except Exception:
      if isinstance(self.error_log, str):
        error_message = self.error_log + "\n" + frappe.get_traceback()
      else:
        file_and_error =  [" - ".join(f) for f in zip(self.failed_uploads if self.failed_uploads else '', list(set(self.error_log)))]
        error_message = ("\n".join(file_and_error) + "\n" + frappe.get_traceback())
      send_email(False, "NextCloud", "NextCloud Settings", "send_notifications_to", error_message)  
        
  def backup_to_nextcloud(self, upload_db_backup=True):
    if not frappe.db:
      frappe.connect()
    if upload_db_backup:
      base_url = self.make_baseurl()
      if not base_url:
        self.error_log.append(_("Wrong NextCloud URL"))
        return
      self.make_upload_path(base_url)
      self.make_session(base_url)
        
      ## Check if folder exist and upload
      self.check_for_upload_folder()
      self.process_uploading()
      
      ## Logout session
      self.session.logout() 

  def make_baseurl(self):
    vurl = urlparse(self.nc_backup_url)
    if not vurl.scheme:
      return None
    if not vurl.netloc:
      return None
    if not vurl.port:
      port = 443 if vurl.scheme == 'https' else 80
    else:
      port_url = vurl.netloc
      nc_url = port_url.replace(":" + str(vurl.port),"")
      
    base_url = '{0}://{1}:{2}'.format(vurl.scheme, vurl.netloc if not vurl.port else nc_url, vurl.port if vurl.port else port)
    if base_url.endswith('/'):
      base_url = base_url[:-1]
    
    return base_url
    
  def make_upload_path(self, base_url):
    """This function checks if path is provided and if not makes default"""
    if self.nc_backup_path:
      self.upload_path = '{}'.format(self.nc_backup_path)
    else:
      self.upload_path = '{}'.format('/Frappe Backups/')  

  def make_session(self, base_url):
    nc_token = get_decrypted_password('NextCloud Settings', 'NextCloud Settings', 'nc_backup_token', True)
    session = nextcloud.Client(base_url)
    session.login(self.nc_backup_username, nc_token)
    self.session = session
  
  def check_for_upload_folder(self):
    """If a path (only the root directory) is provided in NextCloud Settings, this function checks if path exists.
    If no path is provided, /Frappe Backups/ dir will be created for backup user"""
    try:
      ## Check for directory listing if exists
      response = self.session.list(self.upload_path, depth=0)
    except Exception as e:
      ## Error due to non existing directory. We'll create
      self.error_log.append(e)
      response = self.session.mkdir(self.upload_path)

  def process_uploading(self):
    db_backup, site_config, public_file_backup, private_file_backup = self.prepare_backup()
  
    db_response = self.upload_backup(db_backup)
    if db_response == "Failed":
      self.failed_uploads.append(db_backup)
      self.error_log.append(_('\r\nFailed while uploading DB'))
      
    site_config_response = self.upload_backup(site_config)
    if site_config_response == "Failed":
      self.failed_uploads.append(site_config)
      self.error_log.append(_('\r\nFailed while uploading Site Config'))
      
    ## File Backup
    if self.backup_files and db_response != "Failed" and site_config_response != "Failed":
      self.file_upload(public_file_backup, private_file_backup) 
      
  def file_upload(self, public_file_backup, private_file_backup):
    if public_file_backup:
      response_public_file = self.upload_backup(public_file_backup)
      if response_public_file == "Failed":
        self.failed_uploads_append(public_file_backup)
        self.error_log.append(_('\r\nFailed while uploading Public Files'))
    if private_file_backup:
      response_private_file = self.upload_backup(private_file_backup)
      if response_private_file == "Failed":
        self.failed_uploads_append(private_file_backup)
        self.error_log.append(_('\r\nFailed while uploading Private Files'))  

  def upload_backup(self, filebackup):
    if not os.path.exists(filebackup):
      return
    local_fileobj = filebackup
    fileobj = local_fileobj.split('/')
    dir_length = len(fileobj) - 1
    ## remove datetime
    remote_fileobj = str(datetime.datetime.today().weekday()) + fileobj[dir_length].encode("ascii", "ignore").decode("ascii")[15:]
    if self.upload_path.endswith('/'):
      remote_path = '{0}{1}'.format(self.upload_path, remote_fileobj)
    else:
      remote_path = '{0}/{1}'.format(self.upload_path, remote_fileobj)
    
    try:
      response = self.session.put_file(remote_path = remote_path, local_source_file = filebackup)
      return response
    except Exception as e:
      return "Failed"
    
  def prepare_backup(self):
    odb = new_backup(ignore_files=False if self.backup_files else True, force=frappe.flags.create_new_backup)
    database, public, private, config = odb.get_recent_backup(older_than=24 * 30)
    return database, config, public, private 

@frappe.whitelist()
def take_backup():
  """Enqueue long job for taking backup to NC"""
  enqueue("pibidav.pibidav.doctype.nextcloud_settings.nextcloud_settings.start_backup", queue='long', timeout=3000)
  frappe.msgprint(_("Queued for Backup. It may take a long time depending on your backup files size. Rest Easy!!!"))
  
def daily_backup():
  take_backups_if("Daily")

def weekly_backup():
  take_backups_if("Weekly")

def take_backups_if(freq):
  if frappe.db.get_single_value("NextCloud Settings", "backup_frequency") == freq:
    start_backup()

def start_backup():
  backup = frappe.get_doc("NextCloud Settings", "NextCloud Settings")
  backup.start_taking_backup()
