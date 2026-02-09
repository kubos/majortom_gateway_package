import pytest
import asyncio
try:
    from unittest.mock import AsyncMock, MagicMock, patch
except ImportError:
    from mock import AsyncMock, MagicMock, patch
from majortom_gateway import GatewayAPI, DEFAULT_MAX_QUEUE_SIZE
from majortom_gateway.exceptions import ValidationError
import websockets
import logging

logger = logging.getLogger(__name__)


class MockWebSocket:
    def __init__(self, messages=None, close_after=None):
        self.messages = messages or []
        self.close_after = close_after
        self.message_index = 0
        self.closed = False
        self.sent_messages = []

    async def send(self, message):
        self.sent_messages.append(message)

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.closed:
            raise StopAsyncIteration
        if self.close_after is not None and self.message_index >= self.close_after:
            raise websockets.ConnectionClosedError(None, None)
        if self.message_index >= len(self.messages):
            await asyncio.sleep(0.1)
            if self.close_after is not None:
                raise websockets.ConnectionClosedError(None, None)
            raise StopAsyncIteration
        msg = self.messages[self.message_index]
        self.message_index += 1
        return msg


@pytest.mark.asyncio
async def test_reconnects_on_connection_closed_error():
    gw = GatewayAPI("host", "gateway_token")
    connect_count = 0
    max_connects = 3

    async def mock_connect(*args, **kwargs):
        nonlocal connect_count
        connect_count += 1
        logger.info(f"Mock connect called (count: {connect_count})")
        if connect_count >= max_connects:
            gw.shutdown_intended = True
        return MockWebSocket(close_after=0)

    with patch.object(websockets, 'connect', side_effect=mock_connect):
        await gw.connect_with_retries()

    assert connect_count == max_connects, f"Expected {max_connects} connection attempts, got {connect_count}"


@pytest.mark.asyncio
async def test_reconnects_on_abrupt_disconnect():
    gw = GatewayAPI("host", "gateway_token")
    connect_count = 0
    max_connects = 2

    async def mock_connect(*args, **kwargs):
        nonlocal connect_count
        connect_count += 1
        logger.info(f"Mock connect called (count: {connect_count})")
        ws = MockWebSocket(messages=['{"type": "hello", "hello": {"mission": "test"}}'], close_after=1)
        if connect_count >= max_connects:
            gw.shutdown_intended = True
        return ws

    with patch.object(websockets, 'connect', side_effect=mock_connect):
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await gw.connect_with_retries()

    assert connect_count == max_connects, f"Expected {max_connects} connection attempts, got {connect_count}"


@pytest.mark.asyncio
async def test_stops_reconnecting_on_intentional_disconnect():
    gw = GatewayAPI("host", "gateway_token")
    connect_count = 0

    async def mock_connect(*args, **kwargs):
        nonlocal connect_count
        connect_count += 1
        gw.shutdown_intended = True
        raise websockets.ConnectionClosed(None, None)

    with patch.object(websockets, 'connect', side_effect=mock_connect):
        await gw.connect_with_retries()

    assert connect_count == 1, "Should stop after intentional disconnect"


@pytest.mark.asyncio
async def test_reconnects_on_os_error():
    gw = GatewayAPI("host", "gateway_token")
    connect_count = 0
    max_connects = 2

    async def mock_connect(*args, **kwargs):
        nonlocal connect_count
        connect_count += 1
        if connect_count >= max_connects:
            gw.shutdown_intended = True
            raise websockets.ConnectionClosed(None, None)
        raise OSError("Connection refused")

    with patch.object(websockets, 'connect', side_effect=mock_connect):
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await gw.connect_with_retries()

    assert connect_count == max_connects, f"Expected {max_connects} attempts after OSError, got {connect_count}"


@pytest.mark.asyncio
async def test_queues_messages_during_disconnect():
    gw = GatewayAPI("host", "gateway_token")
    gw.websocket = None

    await gw.transmit({"type": "test", "data": "message1"})
    await gw.transmit({"type": "test", "data": "message2"})

    assert len(gw.queued_payloads) == 2
    assert gw.queued_payloads[0]["data"] == "message1"
    assert gw.queued_payloads[1]["data"] == "message2"


@pytest.mark.asyncio
async def test_empties_queue_on_reconnect():
    gw = GatewayAPI("host", "gateway_token")
    gw.queued_payloads = [
        {"type": "test", "data": "queued1"},
        {"type": "test", "data": "queued2"},
    ]

    mock_ws = MockWebSocket()
    gw.websocket = mock_ws

    await gw.empty_queue()

    assert len(gw.queued_payloads) == 0
    assert len(mock_ws.sent_messages) == 2


def test_default_max_queue_size():
    gw = GatewayAPI("host", "gateway_token")
    assert gw.max_queue_size == DEFAULT_MAX_QUEUE_SIZE


def test_custom_max_queue_size():
    gw = GatewayAPI("host", "gateway_token", max_queue_size=500)
    assert gw.max_queue_size == 500


def test_max_queue_size_zero_disables_queueing():
    gw = GatewayAPI("host", "gateway_token", max_queue_size=0)
    assert gw.max_queue_size == 0


def test_invalid_max_queue_size_negative():
    with pytest.raises(ValidationError):
        GatewayAPI("host", "gateway_token", max_queue_size=-1)


def test_invalid_max_queue_size_non_integer():
    with pytest.raises(ValidationError):
        GatewayAPI("host", "gateway_token", max_queue_size="100")


@pytest.mark.asyncio
async def test_queue_respects_custom_max_size():
    gw = GatewayAPI("host", "gateway_token", max_queue_size=3)
    gw.websocket = None

    for i in range(5):
        await gw.transmit({"type": "test", "data": f"message{i}"})

    assert len(gw.queued_payloads) == 3
    assert gw.queued_payloads[0]["data"] == "message0"
    assert gw.queued_payloads[2]["data"] == "message2"


@pytest.mark.asyncio
async def test_queue_drops_when_max_size_zero():
    gw = GatewayAPI("host", "gateway_token", max_queue_size=0)
    gw.websocket = None

    await gw.transmit({"type": "test", "data": "message"})

    assert len(gw.queued_payloads) == 0
