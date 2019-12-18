import pytest
import majortom_gateway
from unittest import mock
import pytest_asyncio
import asyncio
from asynctest import CoroutineMock
import ssl
import json
from typing import AsyncIterator


MT_URL = "example.com"
MT_TOKEN = "randomstring"
LOOP = asyncio.get_event_loop()


# Static Tests

def test_required_args():
    with pytest.raises(TypeError):
        gw = majortom_gateway.GatewayAPI()


# Async Tests

@pytest.mark.asyncio
async def test_connect(event_loop):
    expected_gateway_endpoint = "wss://"+MT_URL+"/gateway_api/v1.0"
    expected_headers = {
        "X-Gateway-Token": MT_TOKEN
    }

    with mock.patch("websockets.connect", new=CoroutineMock()) as mocked_websocket:
        gateway = majortom_gateway.GatewayAPI(host=MT_URL, gateway_token=MT_TOKEN)
        await gateway.connect()
        assert mocked_websocket.call_args != None
        assert mocked_websocket.call_args[0][0] == expected_gateway_endpoint
        assert mocked_websocket.call_args[1]['extra_headers'] == expected_headers


@pytest.mark.asyncio
async def test_transmit(event_loop):
    payload = {"stuff": "things"}
    expected_payload = json.dumps(payload)

    with mock.patch("websockets.connect", new=CoroutineMock()) as mocked_websocket, mock.patch("majortom_gateway.GatewayAPI._transmit", new=CoroutineMock()) as mock_transmit, mock.patch("majortom_gateway.GatewayAPI._message_receive_loop", new=CoroutineMock()) as mock_receive:
        # Set websocket return value so the API thinks it's connected
        mocked_websocket.return_value = True
        gateway = majortom_gateway.GatewayAPI(host=MT_URL, gateway_token=MT_TOKEN)
        await gateway.connect()
        await gateway.transmit(payload)
        assert mock_transmit.call_args != None
        assert mock_transmit.call_args[0][0] == expected_payload


@pytest.mark.asyncio
async def test_receive(event_loop):
    message = '{"type":"hello"}'
    expected_message = "Major Tom says hello: {}".format(json.loads(message))

    with mock.patch("websockets.connect", new=CoroutineMock()) as mocked_websocket, mock.patch("majortom_gateway.GatewayAPI._transmit", new=CoroutineMock()) as mock_transmit, mock.patch("majortom_gateway.GatewayAPI._message_receive_loop", new=CoroutineMock()) as mock_receive, mock.patch("majortom_gateway.gateway_api.logger.info") as mock_logger:
        # Set websocket return value so the API thinks it's connected
        mocked_websocket.return_value = True
        gateway = majortom_gateway.GatewayAPI(host=MT_URL, gateway_token=MT_TOKEN)
        await gateway.connect()
        await gateway.handle_message(message)
        assert mock_logger.call_args != None
        assert mock_logger.call_args[0][0] == expected_message
