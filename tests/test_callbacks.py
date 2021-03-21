import pytest
import asyncio
from unittest.mock import AsyncMock
from unittest.mock import ANY
from majortom_gateway import GatewayAPI
from majortom_gateway import Command
import json
import base64

class TypeMatcher:
    def __init__(self, expected_type):
        self.expected_type = expected_type

    def __eq__(self, other):
        return isinstance(other, self.expected_type)

@pytest.fixture
def callback_mock():
    future = asyncio.Future()
    future.set_result(None)
    fn = AsyncMock(return_value=future) 
    return fn


@pytest.mark.asyncio
async def test_fails_when_no_command_callback(monkeypatch):
    gw = GatewayAPI("host", "gateway_token")

    # Monkey-patch fail command, which should be called when a command callback doesn't exist
    mock_fail_command = AsyncMock()
    monkeypatch.setattr(gw, "fail_command", mock_fail_command)

    message =  json.dumps({
        "type": "command",
        "command": {
            "id": 4,
            "type": "get_battery" ,
            "system": "ISS",
            "fields": []
        }
    })
    res = await gw.handle_message(message)
    
    assert(None == res)
    assert mock_fail_command.called

@pytest.mark.asyncio
async def test_calls_command_callback(callback_mock):
    gw = GatewayAPI("host", "gateway_token", command_callback=callback_mock)
    message =  json.dumps({
        "type": "command",
        "command": {
            "id": 4,
            "type": "get_battery" ,
            "system": "ISS",
            "fields": []
        }
    })

    res = await gw.handle_message(message)
    
    # Make sure that the command callback was called with the command and Gateway
    callback_mock.assert_called_once_with(TypeMatcher(Command), TypeMatcher(GatewayAPI))

@pytest.mark.asyncio
async def test_calls_cancel_callback(callback_mock):
    gw = GatewayAPI("host", "gateway_token", cancel_callback=callback_mock)
    message =  json.dumps({
        "type": "cancel",
        "timestamp": 1528391020767,
        "command": {
            "id": 20
        }
    })

    res = await gw.handle_message(message)
    
    # The cancel callback is called with the command id and the gateway
    callback_mock.assert_called_once_with(20, TypeMatcher(GatewayAPI))

@pytest.mark.asyncio
async def test_calls_rate_limit_callback(callback_mock):
    gw = GatewayAPI("host", "gateway_token", rate_limit_callback=callback_mock)
    message =  {
        "type": "rate_limit",
        "rate_limit": {
            "rate": 60,
            "retry_after": 0.5,
            "error": "Rate limit exceeded. Please limit request rate to a burst of 20 and an average of 60/second.",
        }
    }

    res = await gw.handle_message(json.dumps(message))
    
    # The rate limit callback is given the raw message
    callback_mock.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_calls_error_callback(callback_mock):
    gw = GatewayAPI("host", "gateway_token", error_callback=callback_mock)
    message = {
        "type": "error",
        "error": "This Gateway's token has been rotated. Please use the new one.",
        "disconnect": True
    }

    res = await gw.handle_message(json.dumps(message))
    
    # The error callback is given the raw message
    callback_mock.assert_called_once_with(message)


@pytest.mark.asyncio
async def test_calls_transit_callback(callback_mock):
    gw = GatewayAPI("host", "gateway_token", transit_callback=callback_mock)
    # ToDo: Update this example message
    message =  {
        "type": "transit",
    }

    res = await gw.handle_message(json.dumps(message))
    
    # The transit callback is given the raw message
    callback_mock.assert_called_once_with(message)

@pytest.mark.asyncio
async def test_calls_received_blob_callback(callback_mock):
    gw = GatewayAPI("host", "gateway_token", received_blob_callback=callback_mock)
    blob = b"I am a blob"
    message =  json.dumps({
        "type": "received_blob",
        "blob": base64.b64encode(blob).decode("utf-8"),
        "context": {
            "norad_id": 12345
        },
        "metadata": {
            "gsn_timestamp": 1234567890,
            "majortom_timestamp": 1234567890
        }
    })

    res = await gw.handle_message(message)
    
    # The received_blob callback is given the decoded blob, the context, and the gateway
    callback_mock.assert_called_once_with(blob, ANY, TypeMatcher(GatewayAPI))

