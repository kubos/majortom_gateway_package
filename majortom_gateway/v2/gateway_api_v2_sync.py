import base64
from base64 import b64encode
import logging
from majortom_gateway.v2.event_handler import EventHandler
from majortom_gateway.v2.file_transfer import FileTransfer
from majortom_gateway.v2.types import *
import socketio
import time
from typing import Any, Optional



logger = logging.getLogger(__name__)

class GatewayAPIv2Sync:
  def __init__(
      self,
      host: str,
      gateway_token: str,
      basic_auth: str=None,
      http: bool=False,
      command_callback: Optional[CommandCallback]=None,
      error_callback: Optional[ErrorCallback]=None,
      rate_limit_callback: Optional[RateLimitCallback]=None,
      cancel_callback: Optional[CancelCallback]=None,
      transit_callback: Optional[TransitCallback]=None,
      received_blob_callback: Optional[ReceivedBlobCallback]=None
  ):
    self.mission_name: str = None
    self.sio = socketio.Client(
      logger=True,
      engineio_logger=True,
      reconnection=True,
      reconnection_attempts=0, # infinite
      reconnection_delay=1, # seconds between attempts, doubles each time
      handle_sigint=True
    )
    self.endpoint: str = ("http://" + host) if http else ("https://" + host)
    self.token: dict = { "token": gateway_token }
    self.basic_auth: dict = { "Authorization": "Basic " + b64encode(str.encode(f"{basic_auth}")).decode("ascii") }
    self.file_transfer = FileTransfer(self.endpoint, gateway_token)
    self.event_handler = EventHandler(
      self,
      command_callback,
      error_callback,
      rate_limit_callback,
      cancel_callback,
      transit_callback,
      received_blob_callback
    )

  # public API
  def connect(self) -> None:
    self.sio.connect(self.endpoint, auth=self.token, headers=self.basic_auth)

    # connection-handling callbacks
    self.sio.on("connect", self.__on_connect)
    self.sio.on("connect_error", self.__on_connect_error)
    self.sio.on("disconnect", self.__on_disconnect)
    self.sio.on("hello", self.__on_hello)

    # event handlers for Major Tom messages
    self.event_handler.register(self.sio)

  def connect_with_retries(self) -> None:
    self.connect()

  def disconnect(self) -> None:
    self.sio.disconnect()

  def transmit_metrics(self, metrics: list[Measurement], ack_cb:AckCallback=None) -> None:
    self.sio.emit("measurements", [
      Measurement(
        system=metric["system"],
        subsystem=metric["subsystem"],
        metric=metric["metric"],
        value=metric["value"],
        timestamp=metric.get("timestamp", int(time.time() * 1000))
      ) for metric in metrics
    ], callback=ack_cb)

  def transmit_events(self, events: list[Event], ack_cb:AckCallback=None) -> None:
    self.sio.emit("event", [
      Event(
        system=event.get("system", None),
        type=event.get("type", "Gateway Event"),
        command_id=event.get("command_id", None),
        debug=event.get("debug", None),
        level=event.get("level", "nominal"),
        message=event["message"],
        timestamp=event.get("timestamp", int(time.time() * 1000))
      ) for event in events
    ], callback=ack_cb)

  def transmit_command_update(self, command_id: int, state: str, dict: CommandUpdate={}, ack_cb:AckCallback=None) -> None:
    command = CommandUpdate(id=command_id, state=dict["state"])
    for field in dict:
      command[field] = dict[field]
    self.sio.emit("command_update", command, callback=ack_cb)

  def transmit_blob(self, blob: bytes, context: dict, ack_cb:AckCallback=None) -> None:
    self.sio.emit("transmit_blob", BlobTransmission(
      blob=base64.b64encode(blob).decode("cp437"),
      context=context
    ), callback=ack_cb)

  def update_command_definitions(self, system: str, definitions: CommandDefinitionUpdate, ack_cb:AckCallback=None) -> None:
    self.sio.emit("command_definitions_update", {
      "system": system,
      "definitions": definitions
    }, callback=ack_cb)

  def update_file_list(self, system: str, files: list[FileData], timestamp=int(time.time() * 1000), ack_cb:AckCallback=None) -> None:
    self.sio.emit("file_list", {
      "system": system,
      "timestamp": timestamp,
      "files": files
    }, callback=ack_cb)

  def download_staged_file(self, gateway_download_path: str) -> None:
    return self.file_transfer.download(gateway_download_path)

  def upload_downlinked_file(
      self,
      filename: str,
      filepath: str,
      system: str,
      timestamp: int=time.time() * 1000,
      content_type: str="binary/octet-stream",
      command_id: int=None,
      metadata: dict=None,
  ) -> None:
    self.file_transfer.upload(filename, filepath, system, timestamp, content_type, command_id, metadata)

  def wait(self) -> None:
    self.sio.wait()

  # private

  class HelloMessage(TypedDict):
    gateway_id: int
    gateway: str
    mission_id: int
    mission: str
    team_id: int
    team: str

  def __on_hello(self, data: HelloMessage) -> None:
    self.mission_name = data["mission"]
    logger.info("Major Tom says hello: {}".format(data))

  def __on_connect(self):
    print("connected to server")
    self.measure_latency()

  def __on_connect_error(self, data: Any):
    print("connection error " + data)
    self.sio.wait()

  def __on_disconnect(self):
    print("disconnect, will attempt reconnect")
    self.sio.wait()

if __name__ == '__main__':
  gateway = GatewayAPIv2Sync(
    "staging.testing.majortom.cloud",
    "7c7e9c61623c14da067d086e8ca039e2be8ba42f1b672f2b9c32725060386dc4",
    basic_auth="staging:password1"
  )
  gateway.connect()
  gateway.wait()
  print("*** done waiting")
