import pytest
import asyncio
try:
    from unittest.mock import AsyncMock  # Python >= 3.8
except ImportError:  
    from mock import AsyncMock  # Python < 3.8

# Import websockets early for the purpose of monkeypatching
import websockets

from majortom_gateway import GatewayAPI
import logging

def test_logging_output():
    # A simple test to see what output is being captured
    logging.debug("DEBUG: Testing")
    logging.info("INFO: Testing")
    logging.warning("WARN: Testing")
    logging.error("ERROR: Testing")
    print("PRINT: Testing")

def test_required_args():
    with pytest.raises(TypeError):
        gw = GatewayAPI()

@pytest.mark.asyncio
async def test_connecting_with_retries_actually_retries_on_OsError(monkeypatch):

    # First, we set up a mock that will raise an error first, followed by returning success
    mock_connect = AsyncMock(side_effect=[OSError, "Success!"])

    # Patch our class with the mock, so calls to .connect get redirected to the mock.
    monkeypatch.setattr(GatewayAPI, "connect", mock_connect)

    gateway = GatewayAPI(
        host="host",
        gateway_token="token",
        http=True)

    retval = await gateway.connect_with_retries()

    # Assertions
    assert mock_connect.call_count == 2, "There should be 2 calls to the connect function. The first failing, the second succeeding."
    assert retval == "Success!"


@pytest.mark.asyncio
async def test_connect_retries_when_websocket_returns_None(monkeypatch):

    # This is an asynchronous generator. It can be used to mock messages coming
    # off a successful websocket connection
    async def websocket_messages():
        yield '{"type":"hello"}'
        await asyncio.sleep(0)

    # First, we set up a mock that will return a series of None's followed by an async iterator that represents success.
    mock_connect = AsyncMock(side_effect=[None, websocket_messages()])

    # Patch websockets with the mock
    monkeypatch.setattr(websockets, "connect", mock_connect)

    gateway = GatewayAPI(
        host="host",
        gateway_token="token")

    await gateway.connect()

    # Assertions
    assert mock_connect.call_count == 2, "There should be 2 calls to the connect function. The first failing, the second succeeding."


