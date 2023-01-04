import asyncio
import base64
import json
import os
import re
import ssl
import logging
import time
import inspect
from base64 import b64encode
import requests
import hashlib
from asgiref.sync import sync_to_async
try:
    # python <= 3.7:
    from asyncio.streams import IncompleteReadError
except ImportError:
    # python >= 3.8:
    from asyncio.exceptions import IncompleteReadError

import websockets

from majortom_gateway.command import Command

logger = logging.getLogger(__name__)

MAX_QUEUE_LENGTH = 10000

class MissingContextError(KeyError):
    pass


class GatewayAPI:
    def __init__(self, host, gateway_token, ssl_verify=False, basic_auth=None, http=False, ssl_ca_bundle=None, command_callback=None, error_callback=None, rate_limit_callback=None, cancel_callback=None, transit_callback=None, received_blob_callback=None):
        self.host = host
        self.gateway_token = gateway_token
        self.ssl_verify = ssl_verify
        self.basic_auth = basic_auth
        self.http = http
        if ssl_verify is True and ssl_ca_bundle is None:
            raise(ValueError('"ssl_ca_bundle" must be a valid path to a certificate bundle if "ssl_verify" is True. Could fetch from https://curl.haxx.se/docs/caextract.html'))
        else:
            self.ssl_ca_bundle = ssl_ca_bundle
        self.__build_endpoints()
        self.command_callback = command_callback
        self.error_callback = error_callback
        self.rate_limit_callback = rate_limit_callback
        self.cancel_callback = cancel_callback
        self.transit_callback = transit_callback
        self.received_blob_callback = received_blob_callback
        self.websocket = None
        self.mission_name = None
        self.queued_payloads = []
        self.headers = {
            "X-Gateway-Token": self.gateway_token
        }
        if self.basic_auth != None:
            userAndPass = b64encode(str.encode(f"{self.basic_auth}")).decode("ascii")
            self.headers['Authorization'] = f'Basic {userAndPass}'

    def __build_endpoints(self):
        if self.http:
            self.gateway_endpoint = "ws://" + self.host + "/gateway_api/v1.0"
        else:
            self.gateway_endpoint = "wss://" + self.host + "/gateway_api/v1.0"

    async def connect(self):
        if self.http:
            ssl_context = None
        else:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

            if self.ssl_verify:
                ssl_context.verify_mode = ssl.CERT_REQUIRED
                ssl_context.check_hostname = True
                # Should probably fetch from https://curl.haxx.se/docs/caextract.html
                ssl_context.load_verify_locations(self.ssl_ca_bundle)
            else:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE

        logger.info("Connecting to Major Tom")
        self.websocket = await websockets.connect(self.gateway_endpoint,
                                                  extra_headers=self.headers,
                                                  ssl=ssl_context)

        logger.info("Connected to Major Tom")
        await asyncio.sleep(1)
        await self.empty_queue()
        async for message in self.websocket:
            asyncio.ensure_future(self.handle_message(message))
            await asyncio.sleep(0)  # Allows execution to jump to wherever it may be needed, such as future or prev message

    async def connect_with_retries(self):
        while True:
            try:
                return await self.connect()
            except (OSError, IncompleteReadError, websockets.ConnectionClosed) as e:
                self.websocket = None
                logger.warning("Connection error encountered, retrying in 5 seconds ({})".format(e))
                await asyncio.sleep(5)
            except websockets.exceptions.InvalidStatusCode as e:
                self.websocket = None
                if e.status_code == 401:
                    e.args = [
                        f"{self.host} requires BasicAuth credentials. Please either include that argument or check the validity. Websocket Error: {e.args}"]
                    raise(e)
                elif e.status_code == 403:
                    e.args = [
                        f"Gateway Token is Invalid: {self.gateway_token} Websocket Error: {e.args}"]
                    raise(e)
                elif e.status_code == 404 or e.status_code >= 500:
                    logger.warning(f"Received {e.status_code} when trying to connect, retrying.")
                    await asyncio.sleep(5)
                else:
                    e.args = [f"Unhandled status code returned: {e.status_code}"]
                    raise(e)
            except Exception as e:
                logger.error("Unhandled {} in `connect_with_retries`".format(e.__class__.__name__))
                raise(e)

    async def callCallback(self, cb, *args, **kwargs):
        ''' Calls a callback, handling both when it is an async coroutine or
        a regular sync function.
        Returns: An awaitable task
        '''
        if callable(cb):
            if asyncio.iscoroutinefunction(cb) or inspect.isawaitable(cb) :
                task = asyncio.ensure_future( cb(*args, **kwargs) )
            else:
                # sync_to_async with thread_sensitive=False runs the sync function in its own thread
                # see https://docs.djangoproject.com/en/3.2/topics/async/#asgiref.sync.sync_to_async
                task = asyncio.ensure_future( sync_to_async(cb, thread_sensitive=False)(*args, **kwargs))
            task.add_done_callback(self._handle_task_result)
        else:
            raise ValueError('cb is not callable: {}'.format(dir(cb)))

    def _handle_task_result(self, task: asyncio.Task) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            pass  # Task cancellation should not be logged as an error.
        except Exception:  # pylint: disable=broad-except
            logger.exception('Exception raised by task = %r', task)

    async def handle_message(self, json_data):
        message = json.loads(json_data)
        message_type = message["type"]
        logger.debug("From Major Tom: {}".format(message))

        if message_type == "command":
            command = Command(message["command"])
            if self.command_callback is not None:
                """
                TODO: Track the task and ensure it completes without errors
                reference: https://medium.com/@yeraydiazdiaz/asyncio-coroutine-patterns-errors-and-cancellation-3bb422e961ff
                """
                asyncio.ensure_future(self.callCallback(self.command_callback, command, self))
            else:
                asyncio.ensure_future(self.fail_command(command.id, errors=["No command callback implemented"]))
        elif message_type == "cancel":
            if self.cancel_callback is not None:
                """
                TODO: Track the task and ensure it completes without errors
                reference: https://medium.com/@yeraydiazdiaz/asyncio-coroutine-patterns-errors-and-cancellation-3bb422e961ff
                """
                asyncio.ensure_future(self.callCallback(self.cancel_callback, message["command"]["id"], self))
            else:
                asyncio.ensure_future(self.transmit_events(events=[{
                    "system": None,
                    "type": "Command Cancellation Failed",
                    "command_id": message["command"]["id"],
                    "level": "warning",
                    "message": "No cancel callback registered. Unable to cancel command."
                }]))
        elif message_type == "transit":
            if self.transit_callback is not None:
                asyncio.ensure_future(self.callCallback(self.transit_callback, message))
            else:
                logger.info("Major Tom expects a ground-station transit will occur: {}".format(message))
        elif message_type == "received_blob":
            if self.received_blob_callback is not None:
                encoded = message.get("blob", "")
                decoded = base64.b64decode(encoded)
                context = message["context"]
                asyncio.ensure_future(self.callCallback(self.received_blob_callback, decoded, context, self))
            else:
                logger.debug("Major Tom received a blob (binary satellite data block)")
        elif message_type == "error":
            logger.error("Error from Major Tom: {}".format(message["error"]))
            if self.error_callback is not None:
                asyncio.ensure_future(self.callCallback(self.error_callback, message))
        elif message_type == "rate_limit":
            logger.error("Rate limit from Major Tom: {}".format(message["rate_limit"]))
            if self.rate_limit_callback is not None:
                asyncio.ensure_future(self.callCallback(self.rate_limit_callback, message))
        elif message_type == "hello":
            self.mission_name = message.get('hello', {}).get('mission')
            logger.info("Major Tom says hello: {}".format(message))
        else:
            logger.warning("Unknown message type {} received from Major Tom: {}".format(
                message_type, message))

    async def empty_queue(self):
        while len(self.queued_payloads) > 0 and self.websocket:
            payload = self.queued_payloads.pop(0)
            await self.transmit(payload)
            await asyncio.sleep(0.1)

    async def transmit(self, payload):
        if self.websocket:
            logger.debug("To Major Tom: {}".format(payload))
            try:
                await self.websocket.send(json.dumps(payload))
            except Exception as e:
                logger.error(
                    f"Websocket experienced an error when attempting to transmit: {type(e).__name__}: {e}")
                self.websocket = None
                if len(self.queued_payloads) < MAX_QUEUE_LENGTH:
                    self.queued_payloads.append(payload)
                else:
                    logger.warn(
                        f"Major Tom Client local queue maxed out at {MAX_QUEUE_LENGTH} items. Packet is being dropped.")
        else:
            logger.info(
                "Websocket is not connected, queueing payload until connection is re-established.")
            # Switch to https://docs.python.org/3/library/asyncio-queue.html
            if len(self.queued_payloads) < MAX_QUEUE_LENGTH:
                self.queued_payloads.append(payload)
            else:
                logger.warn(
                    f"Major Tom Client local queue maxed out at {MAX_QUEUE_LENGTH} items. Packet is being dropped.")

    async def transmit_metrics(self, metrics):
        """
        "metrics" must be of the format:
        [
            {
                "system": "foo",
                "subsystem": "foo2",
                "metric": "foo3",
                "value": 42,
                "timestamp": milliseconds utc
            },
            ...
        ]
        """
        await self.transmit({
            "type": "measurements",
            "measurements": [
                {
                    "system": metric["system"],
                    "subsystem": metric["subsystem"],
                    "metric": metric["metric"],
                    "value": metric["value"],
                    # Timestamp is expected to be millisecond unix epoch
                    "timestamp": metric.get("timestamp", int(time.time() * 1000))
                } for metric in metrics
            ]
        })

    async def transmit_events(self, events):
        await self.transmit({
            "type": "events",
            "events": [
                {
                    "system": event.get("system", None),

                    "type": event.get("type", "Gateway Event"),

                    "command_id": event.get("command_id", None),

                    "debug": event.get("debug", None),

                    # Can be "debug", "nominal", "warning", or "error".
                    "level": event.get("level", "nominal"),

                    "message": event["message"],

                    # Timestamp is expected to be millisecond unix epoch
                    "timestamp": event.get("timestamp", int(time.time() * 1000))
                } for event in events
            ]
        })

    async def transmit_command_update(self, command_id: int, state: str, dict={}):
        update = {
            "type": "command_update",
            "command": {
                "id": command_id,
                "state": state
            }
        }
        for field in dict:
            update['command'][field] = dict[field]
        await self.transmit(update)

    async def transmit_blob(self, blob: bytes, context: dict):
        # Transmit bytes to a satellite via a groundstation network. The
        # required context depends on the specific gsn.
        await self.transmit({
            "type": "transmit_blob",
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
        """
        "definitions" must be of the format:
        {
          "command": {
            "display_name": "Command Name To Display",
            "description": "Description to give context to the operator.",
            "fields": [
              {"name": "Field Name 1", "type": "number"},
              ...
            ]
          },
          ...
        }
        """
        await self.transmit({
            "type": "command_definitions_update",
            "command_definitions": {
                "system": system,
                "definitions": definitions
            }
        })

    async def update_file_list(self, system: str, files: list, timestamp=int(time.time() * 1000)):
        """
        "files" must be of the format:
        [
          {
            "name": "earth.tiff",
            "size": 1231040,
            "timestamp": 1528391000000,
            "metadata": { "type": "image", "lat": 40.730610, "lng": -73.935242 }
          },
          ...
        ]
        """
        await self.transmit({
            "type": "file_list",
            "file_list": {
                "system": system,
                "timestamp": timestamp,
                "files": files
            }
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
            raise(RuntimeError(f"File Download Failed. Status code: {r.status_code}"))
        filename = re.findall('filename="(.+)";', r.headers['Content-Disposition'])[0]
        logger.info(f"Downloaded Staged File: {filename}")
        return filename, r.content

    def upload_downlinked_file(self, filename: str, filepath: str, system: str, timestamp=time.time()*1000, content_type="binary/octet-stream", command_id=None, metadata=None):

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
            raise(RuntimeError(f"File Upload Request Failed. Status code: {request_r.status_code}"))
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
            raise(RuntimeError(f"File Upload Request Failed. Status code: {upload_r.status_code}"))

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
            raise(RuntimeError(f"File Data Post Failed. Status code: {file_data_r.status_code}"))
