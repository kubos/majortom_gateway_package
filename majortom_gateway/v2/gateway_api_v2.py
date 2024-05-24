import asyncio
import base64
from base64 import b64encode
import hashlib
import inspect
import json
import logging
import os
import re
import requests
import socketio
from asgiref.sync import sync_to_async
import time

from majortom_gateway.command import Command

logger = logging.getLogger(__name__)

class GatewayAPIv2:
  def __init__(self, host, gateway_token, basic_auth=None, http=False, command_callback=None, error_callback=None, rate_limit_callback=None, cancel_callback=None, transit_callback=None, received_blob_callback=None):
    self.endpoint = ("http://" if http else "https://") + host + "/gateway_api/v2.0"
    self.auth = {
      "token": gateway_token
    }
    self.basic_auth = {} if basic_auth == None else {
      "Authorization": "Basic " + b64encode(str.encode(f"{basic_auth}")).decode("ascii")
    }
    self.sio = socketio.AsyncClient()
    handlers = self.EventHandlers(self, command_callback, error_callback, rate_limit_callback, cancel_callback, transit_callback, received_blob_callback)
    self.sio.register_namespace(handlers)
    self.mission_name = None

  # Public API
  async def connect(self):
    logger.info("Connecting to Major Tom")
    await self.sio.connect(self.endpoint, auth=self.auth, headers=self.basic_auth, namespaces=["/"])

  async def disconnect(self):
    await self.sio.disconnect()

  async def connect_with_retries(self):
    await self.connect()

  async def transmit_metrics(self, metrics):
    await self.sio.emit("measurements", metrics)

  async def transmit_events(self, events):
    await self.sio.emit("events", [
      {
        "system": event.get("system", None),
        "type": event.get("type", "Gateway Event"),
        "command_id": event.get("command_id", None),
        "debug": event.get("debug", None),
        "level": event.get("level", "nominal"),
        "message": event["message"],
        "timestamp": event.get("timestamp", int(time.time() * 1000)),
      } for event in events
    ])

  async def transmit_command_update(self, command_id: int, state: str, dict={}):
    command = {
      "id": command_id,
      "state": state,
    }
    for field in dict:
      command[field] = dict[field]
    await self.sio.emit("command_update", command)

  async def transmit_blob(self, blob: bytes, context: dict):
    await self.sio.emit("transmit_blob", {
      "context": context,
      "blob": base64.b64encode(blob).decode("cp437")
    })

  async def fail_command(self, command_id: int, errors: list):
    await self.transmit_command_update(command_id=command_id, state="failed", dict={"errors": errors})

  async def complete_command(self, command_id: int, output: str):
    await self.transmit_command_update(command_id=command_id, state="completed", dict={"output": output})

  async def cancel_command(self, command_id: int):
    await self.transmit_command_update(command_id=command_id, state="cancelled")

  async def transmitted_command(self, command_id: int, payload="None Provided"):
    await self.transmit_command_update(command_id=command_id, state="transmitted_to_system", dict={"payload": payload})

  async def update_command_definitions(self, system: str, definitions: dict):
    await self.sio.emit("command_definitions_update", {
      "system": system,
      "definitions": definitions
    })

  async def update_file_list(self, system: str, files: list, timestamp=int(time.time() * 1000)):
    await self.sio.emit("file_list", {
      "system": system,
      "timestamp": timestamp,
      "files": files
    })

  def download_staged_file(self, gateway_download_path):
    if self.http:
      download_url = "http://"
    else:
      download_url = "https://"
    download_url = download_url + self.host + gateway_download_path

    # Download the file
    r = requests.get(download_url, headers=self.headers)
    for field in r.headers:
      logger.debug(f'{field}  :  {r.headers[field]}')
    if r.status_code != 200:
      raise (RuntimeError(f"File Download Failed. Status code: {r.status_code}"))
    filename = re.findall('filename="(.+)";', r.headers['Content-Disposition'])[0]
    logger.info(f"Downloaded Staged File: {filename}")
    return filename, r.content

  def upload_downlinked_file(
    self,
    filename: str,
    filepath: str,
    system: str,
    timestamp=time.time()*1000,
    content_type="binary/octet-stream",
    command_id=None,
    metadata=None,
  ):
    # Get size and checksum
    byte_size = int(os.path.getsize(filepath))
    with open(filepath, 'rb') as file_handle:
      checksum = b64encode(hashlib.md5(file_handle.read()).digest())

    # Data to request upload
    request_data = {
      "filename": filename,
      "byte_size": byte_size,
      "content_type": content_type,
      "checksum": checksum
    }

    # POST file info to Major Tom and get upload info
    if self.http:
      request_url = "http://"
    else:
      request_url = "https://"
    request_url += self.host + "/rails/active_storage/direct_uploads"
    logging.debug(f"Requesting {request_url} with data: {request_data}")
    request_r = requests.post(url=request_url, headers=self.headers, data=request_data)
    if request_r.status_code != 200:
      logger.error(
        f"Transaction Failed. Status code: {request_r.status_code} \n Text Response: {request_r.text}")
      raise (RuntimeError(f"File Upload Request Failed. Status code: {request_r.status_code}"))
    request_content = json.loads(request_r.content)
    for field in request_content:
      logger.debug(f'{field}  :  {request_content[field]}')

    # PUT file to MT file bucket (S3 or Minio)
    headers = {
      "Content-Type": content_type,
      "Content-MD5": checksum
    }
    upload_url = request_content["direct_upload"]["url"]
    logger.debug(f"Headers: {headers}\nUpload URL: {upload_url}")
    with open(filepath, 'rb') as file_handle:
      upload_r = requests.put(
        url=upload_url,
        headers=headers,
        data=file_handle)

    if upload_r.status_code not in (200, 204):
      logger.error(
        f"Transaction Failed. Status code: {upload_r.status_code} \n Text Response: {upload_r.text}")
      raise (RuntimeError(f"File Upload Request Failed. Status code: {upload_r.status_code}"))

    # Data about the file to show to the operator
    file_data = {
      "signed_id": request_content["signed_id"],
      "name": filename,
      "timestamp": timestamp,
      "system": system
    }
    if command_id != None:
      file_data["command_id"] = command_id
    if metadata != None:
      file_data["metadata"] = metadata

    # POST file data to Major Tom
    if self.http:
      file_data_url = "http://"
    else:
      file_data_url = "https://"
    file_data_url += self.host + "/gateway_api/v1.0/downlinked_files"
    file_data_r = requests.post(url=file_data_url, headers=self.headers, json=file_data)
    if file_data_r.status_code != 200:
      logger.error(
        f"Transaction Failed. Status code: {file_data_r.status_code} \n Text Response: {file_data_r.text}")
      raise (RuntimeError(f"File Data Post Failed. Status code: {file_data_r.status_code}"))

  class EventHandlers(socketio.AsyncClientNamespace):
    def __init__(self, gateway_api, command_callback=None, error_callback=None, rate_limit_callback=None, cancel_callback=None, transit_callback=None, received_blob_callback=None):
      super().__init__("*") # catchall namespace
      self.api = gateway_api
      self.command_callback = command_callback
      self.error_callback = error_callback
      self.rate_limit_callback = rate_limit_callback
      self.cancel_callback = cancel_callback
      self.transit_callback = transit_callback
      self.received_blob_callback = received_blob_callback

    def __invoke_callback(self, cb, *args, **kwargs):
      if callable(cb):
        if asyncio.iscoroutinefunction(cb) or inspect.isawaitable(cb):
          task = asyncio.ensure_future(cb(*args, **kwargs))
        else:
          task = asyncio.ensure_future(sync_to_async(cb, thread_sensitive=False)(*args, **kwargs))
        task.add_done_callback(self.__handle_task_result)
      else:
        raise ValueError('cb is not callable: {}'.format(dir(cb)))

    def __handle_task_result(self, task: asyncio.Task) -> None:
      try:
        task.result()
      except asyncio.CancelledError:
        pass
      except Exception: # pylint: disable=broad-except
        logger.exception("Exception raised by task = %r", task)

    def on_connect(self):
      logger.info("Connected to Major Tom")
    
    def on_connect_error(self, data, _unknown):
      logger.error("Connection failed! {}".format(data))

    def on_disconnect(self):
      logger.info("Disconnected from Major Tom")

    async def on_command(self, data):
      command = Command(data)
      if self.command_callback is not None:
        asyncio.ensure_future(self.__invoke_callback(self.command_callback, command, self))
      else:
        asyncio.ensure_future(self.api.fail_command(command.id, errors=["No command callback implemented"]))

    async def on_cancel(self, data):
      if self.cancel_callback is not None:
        asyncio.ensure_future(self.__invoke_callback(self.cancel_callback, data["command"]["id"], self))
      else:
        asyncio.ensure_future(self.api.transmit_events(events=[{
          "system": None,
          "type": "Command Cancellation Failed",
          "command_id": data["command"]["id"],
          "level": "warning",
          "message": "No cancel callback registered. Unable to cancel command."
        }]))

    async def on_transit(self, data):
      if self.transit_callback is not None:
        asyncio.ensure_future(self.__invoke_callback(self.transit_callback, data))
      else:
        logger.info("Major Tom expects a ground-station transit will occur: {}".format(data))

    async def on_received_blob(self, data):
      if self.received_blob_callback is not None:
        encoded = data.get("blob", "")
        decoded = base64.b64decode(encoded)
        context = data["context"]
        asyncio.ensure_future(self.__invoke_callback(self.received_blob_callback, decoded, context, self))
      else:
        logger.debug("Major Tom received a blob (binary satellite data block)")

    async def on_error(self, data):
      logger.error("Error from Major Tom: {}".format(data["error"]))
      if self.error_callback is not None:
        asyncio.ensure_future(self.__invoke_callback(self.error_callback, data))

    async def on_rate_limit(self, data):
      logger.error("Rate limit from Major Tom: {}".format(data["rate_limit"]))
      if self.rate_limit_callback is not None:
        asyncio.ensure_future(self.__invoke_callback(self.rate_limit_callback, data))

    async def on_hello(self, data):
      self.api.mission_name = data.get("hello", {}).get("mission")
      logger.info("Major Tom says hello: {}".format(data))
