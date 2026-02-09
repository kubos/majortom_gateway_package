import asyncio
import json
import os
import re
import ssl
import logging
import time
import inspect
from base64 import b64encode, b64decode
import requests
import hashlib
from asgiref.sync import sync_to_async
from majortom_gateway.exceptions import ValidationError, FileDownloadError, FileUploadError
try:
    # python <= 3.7:
    from asyncio.streams import IncompleteReadError
except ImportError:
    # python >= 3.8:
    from asyncio.exceptions import IncompleteReadError

import websockets

from majortom_gateway.command import Command

logger = logging.getLogger(__name__)

DEFAULT_MAX_QUEUE_SIZE = 100


class MissingContextError(KeyError):
    pass


class GatewayAPI:
    def __init__(self, host, gateway_token, ssl_verify=False, basic_auth=None, http=False, ssl_ca_bundle=None, command_callback=None, error_callback=None, rate_limit_callback=None, cancel_callback=None, transit_callback=None, received_blob_callback=None, max_queue_size=None):
        # Validate required parameters
        if not host or not isinstance(host, str) or not host.strip():
            raise ValidationError("'host' must be a non-empty string")

        if not gateway_token or not isinstance(gateway_token, str) or not gateway_token.strip():
            raise ValidationError("'gateway_token' must be a non-empty string")

        # Validate optional parameters
        if not isinstance(ssl_verify, bool):
            raise ValidationError("'ssl_verify' must be a boolean")

        if not isinstance(http, bool):
            raise ValidationError("'http' must be a boolean")

        if basic_auth is not None:
            if not isinstance(basic_auth, str) or ":" not in basic_auth:
                raise ValidationError("'basic_auth' must be a string in format 'username:password'")
            username, password = basic_auth.split(":", 1)
            if not username or not password:
                raise ValidationError("'basic_auth' username and password must both be non-empty")

        if ssl_ca_bundle is not None:
            if not isinstance(ssl_ca_bundle, str):
                raise ValidationError("'ssl_ca_bundle' must be a string path to a certificate bundle")
            if not os.path.isfile(ssl_ca_bundle):
                raise ValidationError(f"'ssl_ca_bundle' file does not exist: {ssl_ca_bundle}")

        if ssl_verify is True and ssl_ca_bundle is None:
            raise ValidationError('"ssl_ca_bundle" must be a valid path to a certificate bundle if "ssl_verify" is True. Could fetch from https://curl.haxx.se/docs/caextract.html')

        # Validate callbacks
        callbacks = {
            'command_callback': command_callback,
            'error_callback': error_callback,
            'rate_limit_callback': rate_limit_callback,
            'cancel_callback': cancel_callback,
            'transit_callback': transit_callback,
            'received_blob_callback': received_blob_callback,
        }
        for name, callback in callbacks.items():
            if callback is not None and not callable(callback):
                raise ValidationError(f"'{name}' must be callable (function or coroutine)")

        if max_queue_size is not None:
            if not isinstance(max_queue_size, int) or max_queue_size < 0:
                raise ValidationError("'max_queue_size' must be a non-negative integer")

        # Set validated attributes
        self.host = host.strip()
        self.gateway_token = gateway_token.strip()
        self.ssl_verify = ssl_verify
        self.basic_auth = basic_auth
        self.http = http
        self.ssl_ca_bundle = ssl_ca_bundle
        self.__build_endpoints()
        self.command_callback = command_callback
        self.error_callback = error_callback
        self.rate_limit_callback = rate_limit_callback
        self.cancel_callback = cancel_callback
        self.transit_callback = transit_callback
        self.received_blob_callback = received_blob_callback
        self.max_queue_size = max_queue_size if max_queue_size is not None else DEFAULT_MAX_QUEUE_SIZE
        self.websocket = None
        self.mission_name = None
        self.queued_payloads = []
        self.shutdown_intended = False
        self.headers = {
            "X-Gateway-Token": self.gateway_token
        }
        if self.basic_auth is not None:
            userAndPass = b64encode(str.encode(f"{self.basic_auth}")).decode("ascii")
            self.headers['Authorization'] = f'Basic {userAndPass}'

    def __build_endpoints(self):
        if self.http:
            self.gateway_endpoint = "ws://" + self.host + "/gateway_api/v1.0"
        else:
            self.gateway_endpoint = "wss://" + self.host + "/gateway_api/v1.0"

    async def connect(self):
        self.shutdown_intended = False

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

        logger.info("Connecting to Major Tom at {}".format(self.gateway_endpoint))
        self.websocket = await websockets.connect(
            self.gateway_endpoint,
            additional_headers=self.headers,
            ssl=ssl_context,
            open_timeout=120,
            ping_interval=None,
            ping_timeout=None
        )

        logger.info("Connected to Major Tom")
        await asyncio.sleep(1)

        await self.empty_queue()
        if not self.websocket:
            logger.warning("Websocket was closed during empty_queue, will retry connection")
            raise websockets.ConnectionClosed(None, None)
        try:
            async for message in self.websocket:
                asyncio.ensure_future(self.handle_message(message))
                await asyncio.sleep(0)
        except websockets.ConnectionClosed:
            raise
        finally:
            self.websocket = None

        if not self.shutdown_intended:
            logger.warning("Websocket connection ended unexpectedly, triggering reconnect")
            raise websockets.ConnectionClosed(None, None)

    async def disconnect(self):
        ws = self.websocket
        if ws:
            self.shutdown_intended = True
            await ws.close()
        else:
            logger.warning(
                "disconnect called but no open websocket connection exists"
            )

    async def connect_with_retries(self):
        retry_count = 0
        while True:
            try:
                retry_count = 0
                return await self.connect()
            except (websockets.ConnectionClosed, websockets.ConnectionClosedError) as e:
                if self.shutdown_intended:
                    self.websocket = None
                    logger.info("Websocket disconnected intentionally")
                    return
                else:
                    retry_count += 1
                    self.websocket = None
                    logger.warning("Connection closed unexpectedly (attempt {}), retrying in 5 seconds. Error: {}".format(retry_count, str(e)))
                    await asyncio.sleep(5)
            except (OSError, IncompleteReadError) as e:
                retry_count += 1
                self.websocket = None
                logger.warning("Connection error encountered (attempt {}), retrying in 5 seconds. Error type: {}, Error: {}".format(retry_count, type(e).__name__, str(e)))
                await asyncio.sleep(5)
            except websockets.InvalidStatusCode as e:
                self.websocket = None
                if e.status_code == 401:
                    e.args = [
                        f"{self.host} requires BasicAuth credentials. Please either include that argument or check the validity. Websocket Error: {e.args}"]
                    raise e
                elif e.status_code == 403:
                    e.args = [
                        f"Gateway Token is Invalid: {self.gateway_token} Websocket Error: {e.args}"]
                    raise e
                elif e.status_code == 404 or e.status_code >= 500:
                    retry_count += 1
                    logger.warning(f"Received {e.status_code} when trying to connect (attempt {retry_count}), retrying in 5 seconds.")
                    await asyncio.sleep(5)
                else:
                    e.args = [f"Unhandled status code returned: {e.status_code}"]
                    raise e
            except Exception as e:
                logger.error("Unhandled {} in `connect_with_retries`: {}".format(e.__class__.__name__, str(e)))
                raise e

    async def callCallback(self, cb, *args, **kwargs):
        ''' Calls a callback, handling both when it is an async coroutine or
        a regular sync function.
        Returns: An awaitable task
        '''
        if callable(cb):
            if inspect.iscoroutinefunction(cb) or inspect.isawaitable(cb):
                task = asyncio.ensure_future(cb(*args, **kwargs))
            else:
                # sync_to_async with thread_sensitive=False runs the sync function in its own thread
                # see https://docs.djangoproject.com/en/3.2/topics/async/#asgiref.sync.sync_to_async
                task = asyncio.ensure_future(sync_to_async(cb, thread_sensitive=False)(*args, **kwargs))
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
                decoded = b64decode(encoded)
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
                if len(self.queued_payloads) < self.max_queue_size:
                    self.queued_payloads.append(payload)
                else:
                    logger.warning(
                        f"Major Tom Client local queue maxed out at {self.max_queue_size} items. Packet is being dropped.")
        else:
            logger.info(
                "Websocket is not connected, queueing payload until connection is re-established.")
            if len(self.queued_payloads) < self.max_queue_size:
                self.queued_payloads.append(payload)
            else:
                logger.warning(
                    f"Major Tom Client local queue maxed out at {self.max_queue_size} items. Packet is being dropped.")

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

    async def transmit_command_update(self, command_id: int, state: str, extra_fields=None):
        update = {
            "type": "command_update",
            "command": {
                "id": command_id,
                "state": state
            }
        }
        if extra_fields:
            for field, value in extra_fields.items():
                update['command'][field] = value
        await self.transmit(update)

    async def transmit_blob(self, blob: bytes, context: dict):
        # Transmit bytes to a satellite via a groundstation network. The
        # required context depends on the specific gsn.
        await self.transmit({
            "type": "transmit_blob",
            "context": context,
            "blob": b64encode(blob).decode("utf-8")
        })

    async def fail_command(self, command_id: int, errors: list):
        await self.transmit_command_update(command_id=command_id, state="failed", extra_fields={"errors": errors})

    async def complete_command(self, command_id: int, output: str):
        await self.transmit_command_update(command_id=command_id, state="completed", extra_fields={"output": output})

    async def cancel_command(self, command_id: int):
        await self.transmit_command_update(command_id=command_id, state="cancelled")

    async def transmitted_command(self, command_id: int, payload="None Provided"):
        await self.transmit_command_update(command_id=command_id, state="transmitted_to_system", extra_fields={"payload": payload})

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
            raise FileDownloadError(f"File Download Failed. Status code: {r.status_code}")

        # Extract filename from Content-Disposition header
        content_disposition = r.headers.get('Content-Disposition')
        if not content_disposition:
            raise FileDownloadError("Missing Content-Disposition header in response")

        filename_match = re.findall('filename="(.+)";', content_disposition)
        if not filename_match:
            raise FileDownloadError(f"Could not extract filename from Content-Disposition: {content_disposition}")
        filename = filename_match[0]
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
            raise FileUploadError(f"File Upload Request Failed. Status code: {request_r.status_code}")
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
            raise FileUploadError(f"File Upload Request Failed. Status code: {upload_r.status_code}")

        # Data about the file to show to the operator
        file_data = {
            "signed_id": request_content["signed_id"],
            "name": filename,
            "timestamp": timestamp,
            "system": system
        }
        if command_id is not None:
            file_data["command_id"] = command_id
        if metadata is not None:
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
            raise FileUploadError(f"File Data Post Failed. Status code: {file_data_r.status_code}")
