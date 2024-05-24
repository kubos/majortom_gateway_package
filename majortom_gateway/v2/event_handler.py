import base64
import logging
from typing import Optional

from majortom_gateway.v2.gateway_api_v2_sync import GatewayAPIv2Sync
from majortom_gateway.v2.types import *


logger = logging.getLogger(__name__)

class EventHandler:
  def __init__(
      self,
      gateway: GatewayAPIv2Sync,
      command_callback: Optional[CommandCallback] = None,
      error_callback: Optional[ErrorCallback] = None,
      rate_limit_callback: Optional[RateLimitCallback] = None,
      cancel_callback: Optional[CancelCallback] = None,
      transit_callback: Optional[TransitCallback] = None,
      received_blob_callback: Optional[ReceivedBlobCallback] = None
  ):
    self.gateway: GatewayAPIv2Sync = gateway
    self.command_callback: Optional[CommandCallback] = command_callback
    self.error_callback: Optional[ErrorCallback] = error_callback
    self.rate_limit_callback: Optional[RateLimitCallback] = rate_limit_callback
    self.cancel_callback: Optional[CancelCallback] = cancel_callback
    self.transit_callback: Optional[TransitCallback] = transit_callback
    self.received_blob_callback: Optional[ReceivedBlobCallback] = received_blob_callback

  def register(self, socketio):
    socketio.on("command", self.__on_command)
    socketio.on("error", self.__on_error)
    socketio.on("rate_limit", self.__on_rate_limit)
    socketio.on("cancel", self.__on_cancel)
    socketio.on("transit", self.__on_transit)
    socketio.on("received_blob", self.__on_received_blob)

  # private

  def __on_command(self, data: dict) -> None:
    command = Command(data)
    if callable(self.command_callback):
      self.command_callback(command)
    else:
      self.gateway.transmit_command_update(command.id, "failed", {
        "errors": ["No command callback implemented"]
      })

  def __on_error(self, data: ErrorMessage) -> None:
    if callable(self.error_callback):
      self.error_callback(data)

  def __on_rate_limit(self, data: RateLimitMessage) -> None:
    if callable(self.rate_limit_callback):
      self.rate_limit_callback(data)

  def __on_cancel(self, data: CancelMessage) -> None:
    command_id = data["command"]["id"]
    if callable(self.cancel_callback):
      self.cancel_callback(data)
    else:
      self.gateway.transmit_events(events=[{
        "system": None,
        "type": "Command Cancellation Failed",
        "command_id": command_id,
        "level": "warning",
        "message": "No cancel callback registered. Unable to cancel command."
      }])

  def __on_transit(self, data: TransitMessage) -> None:
    if callable(self.transit_callback):
      self.transit_callback(data)
    else:
      logger.info("Major Tom expects a ground-station transit will occur: {}".format(data))

  class ReceivedBlobMessage(TypedDict):
    blob: str # base64 encoded
    time: str # iso8601
    context: ReceivedBlobContext

  def __on_received_blob(self, data: ReceivedBlobMessage):
    if callable(self.received_blob_callback):
      encoded: str = data.get("blob", "")
      decoded: bytes = base64.b64decode(encoded)
      context: ReceivedBlobContext = data["context"]
      self.received_blob_callback(decoded, context)
    else:
      logger.debug("Major Tom received a blob (binary satellite data block)")

