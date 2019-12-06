import pytest
from majortom_gateway import GatewayAPI
from unittest import mock
import pytest_asyncio
import asyncio
from asynctest import CoroutineMock
import ssl


# Static Tests

def test_required_args():
    with pytest.raises(TypeError):
        gw = GatewayAPI()


# Async Tests

@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_connect(event_loop):
    url = "example.com"
    token = "randomstring"
    gateway_endpoint = "wss://"+url+"/gateway_api/v1.0"
    headers = {
        "X-Gateway-Token": token
    }

    with mock.patch("websockets.connect", new=CoroutineMock()) as mocked_websocket:
        gw = GatewayAPI(host=url, gateway_token=token)
        await gw.connect()
        assert mocked_websocket.call_args[0][0] == gateway_endpoint
        assert mocked_websocket.call_args[1]['extra_headers'] == headers
