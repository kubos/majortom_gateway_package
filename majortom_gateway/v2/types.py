import enum
from typing import Callable, Optional, TypedDict

from majortom_gateway.command import Command

###### Type hints for customer use

# A CommandAcknowledgement is passed as the first argument to an AckCallback function
# and indicates whether the command was acknowledged by Major Tom. Note that a command
# might be acknowledged but not successfully processed; this ack is only an indication
# that the command arrived. If the `ack` field is false, the `error` may provide useful
# information about what went wrong; typically this will indicate a timeout.
class CommandAcknowledgement(TypedDict):
  ack: bool
  error: Optional[str]

# New to GatewayAPIv2, each message sent to Major Tom by the gateway can
# be acknowledged by the server individually. This acknowledgement is only
# a confirmation that the server received the message, not that the
# message was handled and processed. (For that, listen to `error` messages
# by supplying the GatewayAPIv2 with an ErrorCallback function.) This
# acknowledgement is implemented as an AckCallback function that you pass
# to the message-sending function when you sent the message; your callback
# will be invoked with a CommandAcknowledgement object when the server
# has acknowledged it. If the server does not acknowledge the message within
# a short time, a `TimeoutError` will be raised and you should handle that.
AckCallback = Optional[Callable[[CommandAcknowledgement], None]]

# The `transmit_metrics` function expects a list of Measurement objects
class Measurement(TypedDict):
  system: str
  subsystem: str
  metric: str
  value: str
  timestamp: int # expected to be millisecond unix epoch

# A severity level for an Event
class EventLevel(enum.Enum):
  DEBUG = "debug"
  NOMINAL = "nominal"
  WARNING = "warning"
  ERROR = "error"

# The `transmit_events` function expects a list of Event objects
class Event(TypedDict):
  message: str
  system: Optional[str]
  type: Optional[str]
  command_id: Optional[int]
  debug: Optional[str]
  level: Optional[EventLevel]
  timestamp: Optional[int] # expected to be millisecond unix epoch

# The possible states of a Command
class CommandState(enum.Enum):
  QUEUED = "queued"
  WAITING_FOR_GATEWAY = "waiting_for_gateway"
  SENT_TO_GATEWAY = "sent_to_gateway"
  PREPARING_ON_GATEWAY = "preparing_on_gateway"
  UPLINKING_TO_SYSTEM = "uplinking_to_system"
  TRANSMITTED_TO_SYSTEM = "transmitted_to_system"
  ACKED_BY_SYSTEM = "acked_by_system"
  EXECUTING_ON_SYSTEM = "executing_on_system"
  DOWNLINKING_FROM_SYSTEM = "downlinking_from_system"
  PROCESSING_ON_GATEWAY = "processing_on_gateway"
  CANCELLED = "cancelled"
  COMPLETED = "completed"
  FAILED = "failed"

# The `transmit_command_update` function expects a CommandUpdate object
class CommandUpdate(TypedDict):
  id: int
  state: CommandState
  payload: Optional[str]
  status: Optional[str]
  output: Optional[str]
  errors: Optional[list[str]]
  progress_1_current: Optional[int]
  progress_1_max: Optional[int]
  progress_1_label: Optional[int]
  progress_2_current: Optional[int]
  progress_2_max: Optional[int]
  progress_2_label: Optional[int]

# The `transmit_blob` function expects a BlobTransmission object
# The type of the value of the `context` key is a little vague at present
class BlobTransmission(TypedDict):
  context: dict
  blob: str # base64 encoded

# Each field of a command definition is a dictionary of this shape
class CommandDefinitionField(TypedDict):
  name: str
  type: str

# Each value of a CommandDefinitionUpdate dictionary has this shape
class CommandDefinition(TypedDict):
  display_name: str
  description: str
  fields: list[CommandDefinitionField]

# The `update_command_definitions` function expects CommandDefinitionUpdate object
CommandDefinitionUpdate = dict[str, CommandDefinition]

# The `update_file_list` function expects a list of FileData objects
class FileData(TypedDict):
  name: str
  size: int
  timestamp: int # millisecond unix epoch
  metadata: Optional[dict]

###### Types that we will pass to customer callbacks for incoming events


# Customers may supply a CommandCallback to be called when a `command` message is received
# from Major Tom, which will be called with a single argument, a Command object.
CommandCallback = Callable[[Command], None]

# Customers may supply an ErrorCallback to be called when an `error` message is received
# from Major Tom, which will be called with a single argument, an ErrorMessage object.
class ErrorMessage(TypedDict):
  error: str
ErrorCallback = Callable[[ErrorMessage], None]

# Customers may supply a RateLimitCallback to be called when a `rate_limit` message is received
# from Major Tom, which will be called with a single argument, a RateLimitMessage object.
class RateLimitMessage(TypedDict):
  rate_limit: int
  retry_after: int
  error: str
RateLimitCallback = Callable[[RateLimitMessage], None]

# Customers may supply a CancelCallback to be called when a `cancel` message is received
# from Major Tom, which will be called with a single argument, a CancelMessage object.
class CommandReference(TypedDict):
  id: str
class CancelMessage(TypedDict):
  timestamp: int
  command: CommandReference
CancelCallback = Callable[[CancelMessage], None]

# Customers may supply a TransitCallback to be called when a `transit` message is received
# from Major Tom, which will be called with a single argument, a TransitMessage object.
class TransitMessage(TypedDict):
  satellite_name: str
  satellite_id: int
  transit_id: int
  ground_station_name: str
  ground_station_id: int
  approximate_start: str
  approximate_end: str
  approximate_duration: float
  approximate_min_azimuth: float
  approximate_max_azimuth: float
  approximate_apex_azimuth: float
  approximate_max_elevation: float
  approximate_start_latitude: float
  approximate_start_longitude: float
  approximate_start_altitude: float
  approximate_end_latitude: float
  approximate_end_longitude: float
  approximate_end_altitude: float
TransitCallback = Callable[[TransitMessage], None]

# Customers may supply a ReceivedBlobCallback to be called when a `received_blob` message
# is received from Major Tom, which will be called with two arguments: the `bytes` that
# were received and a ReceivedBlobContext object.
class ReceivedBlobContext(TypedDict):
  version: int
  bytes: int
  system: str
  seq: int
ReceivedBlobCallback = Callable[[bytes, ReceivedBlobContext], None]
