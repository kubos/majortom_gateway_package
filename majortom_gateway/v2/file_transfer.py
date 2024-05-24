from base64 import b64encode
import hashlib
import json
import os
import re
import time
import requests


class FileTransfer:
  def __init__(self, base_url, gateway_token):
    self.base_url = base_url
    self.gateway_token = gateway_token
    self.mt_auth_headers = { "X-Gateway-Token": self.gateway_token }

  def download(self, gateway_download_path) -> tuple[str, str]:
    r = requests.get(self.base_url + gateway_download_path, headers=self.mt_auth_headers)
    if r.status_code != 200:
      raise RuntimeError(f"File Download Failed. Status code: {r.status_code}")
    filename = re.findall('filename="(.+)";', r.headers['Content-Disposition'])[0]
    return filename, r.content

  def upload(
      self,
      filename: str,
      filepath: str,
      system: str,
      timestamp=time.time() * 1000,
      content_type="binary/octet-stream",
      command_id=None,
      metadata=None):
    # compile metadata necessary to request an upload ticket
    ticket_request = {
      "filename": filename,
      "content_type": content_type,
      "byte_size": self.__get_file_size(filepath),
      "checksum": self.__get_file_checksum(filepath)
    }

    # get upload ticket from Major Tom
    upload_url, signed_id = self.__request_file_upload_ticket(ticket_request)

    # upload the file using the ticket
    with open(filepath, 'rb') as file_handle:
      self.__put_file(file_handle, upload_url, ticket_request)

    # send file details to Major Tom
    file_details = {
      "signed_id": signed_id,
      "name": filename,
      "timestamp": timestamp,
      "system": system
    }
    if command_id != None:
      file_details["command_id"] = command_id
    if metadata != None:
      file_details["metadata"] = metadata
    self.__update_file_details(file_details)

  # private

  def __request_file_upload_ticket(self, data) -> tuple[str, str]:
    r = requests.post(self.base_url + "/rails/active_storage/direct_uploads", headers=self.mt_auth_headers, data=data)
    if r.status_code != 200:
      raise RuntimeError(f"File Upload Request Failed. Status code: {r.status_code}")
    content = json.loads(r.content)
    return (content["direct_upload"]["url"], content["signed_id"])

  def __put_file(self, file_handle, upload_url, ticket_request):
    r = requests.put(url=upload_url, data=file_handle, headers={
      "Content-Type": ticket_request["content_type"],
      "Content-MD5": ticket_request["checksum"]
    })
    if r.status_code not in (200, 204):
      raise RuntimeError(f"File Upload Request Failed. Status code: {r.status_code}")

  def __update_file_details(self, file_details: dict):
    r = requests.post(self.base_url + "/gateway_api/v1.0/downlinked_files", headers=self.mt_auth_headers, json=file_details)
    if r.status_code != 200:
      raise RuntimeError(f"File Data Post Failed. Status code: {r.status_code}")

  def __get_file_size(self, filepath: str) -> int:
    return int(os.path.getsize(filepath))

  def __get_file_checksum(self, filepath: str) -> dict:
    with open(filepath, 'rb') as file_handle:
      return b64encode(hashlib.md5(file_handle.read()).digest())


