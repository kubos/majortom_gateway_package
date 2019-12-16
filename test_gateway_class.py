import pytest
from majortom_gateway import GatewayAPI
from unittest import mock
import pytest_asyncio
import asyncio
from asynctest import CoroutineMock
import ssl
import json


MT_URL = "example.com"
MT_TOKEN = "randomstring"


# Static Tests

def test_required_args():
    with pytest.raises(TypeError):
        gw = GatewayAPI()


# Async Tests

@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    # Needs a yield for each async test
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_connect(event_loop):
    url = "example.com"
    token = "randomstring"
    expected_gateway_endpoint = "wss://"+url+"/gateway_api/v1.0"
    expected_headers = {
        "X-Gateway-Token": token
    }

    with mock.patch("websockets.connect", new=CoroutineMock()) as mocked_websocket:
        gateway = GatewayAPI(host=MT_URL, gateway_token=MT_TOKEN)
        await gateway.connect()
        assert mocked_websocket.call_args != None
        assert mocked_websocket.call_args[0][0] == expected_gateway_endpoint
        assert mocked_websocket.call_args[1]['extra_headers'] == expected_headers
