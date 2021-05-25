import pytest
import asyncio
try:
    # Python 3.8+
    from unittest.mock import AsyncMock
except ImportError:
    # Python 3.6+
    from mock import AsyncMock
from unittest.mock import ANY
from majortom_gateway import GatewayAPI
from majortom_gateway import Command
import json
import base64
import logging
import time

MESSAGE = json.dumps({
        "type": "command",
        "command": {
            "id": 4,
            "type": "get_battery" ,
            "system": "ISS",
            "fields": []
        }
    })

@pytest.mark.asyncio
async def test_sync_callbacks_can_be_run_async():
    def cb(command, *args, **kwargs):
        time.sleep(1)
        logging.debug(f"Finished command {command.id}")

    gw = GatewayAPI("host", "gateway_token", command_callback=cb)
    async def ticker():
        for i in range(10):
            yield json.dumps({
                "type": "command",
                "command": {
                    "id": i,
                    "type": "get_batt",
                    "system": "ISS",
                    "fields": []
                }
            })
            await asyncio.sleep(0.1)
    
    logging.info("start await")
    async for message in ticker():
        await gw.handle_message(message)
    logging.info("end await")
    
    # The sync commands should finish before this is done
    # If they don't, a bunch of errors will (hopefully) be generated.
    await asyncio.sleep(3)  

@pytest.mark.asyncio
async def test_calls_SYNC_command_callback():
    result = { "worked": False }

    def cb(*args, **kwargs):
        result["worked"] = True

    gw = GatewayAPI("host", "gateway_token", command_callback=cb)

    await gw.handle_message(MESSAGE)
    await asyncio.sleep(1)

    assert result["worked"]


@pytest.mark.asyncio
async def test_error_propagation_on_SYNC_command_callback(caplog):
    def cb(*args, **kwargs):
        # You should NOT see 'Task exception was never retrieved'
        raise RuntimeError("This exception message should be visible.")

    gw = GatewayAPI("host", "gateway_token", command_callback=cb)

    await gw.handle_message(MESSAGE)
    await asyncio.sleep(1)  # Give time for the callback to run
    
    assert 'This exception message should be visible' in caplog.text

@pytest.mark.asyncio
async def test_calls_SYNC_cancel_callback():
    result = { "worked": False }

    def cb(*args, **kwargs):
        result["worked"] = True

    gw = GatewayAPI("host", "gateway_token", cancel_callback=cb)
    message =  json.dumps({
        "type": "cancel",
        "timestamp": 1528391020767,
        "command": {
            "id": 20
        }
    })

    await gw.handle_message(message)
    await asyncio.sleep(1)
    
    assert result["worked"]

@pytest.mark.asyncio
async def test_calls_SYNC_rate_limit_callback():
    result = { "worked": False }

    def cb(*args, **kwargs):
        result["worked"] = True

    gw = GatewayAPI("host", "gateway_token", rate_limit_callback=cb)
    message =  {
        "type": "rate_limit",
        "rate_limit": {
            "rate": 60,
            "retry_after": 0.5,
            "error": "Rate limit exceeded. Please limit request rate to a burst of 20 and an average of 60/second.",
        }
    }

    await gw.handle_message(json.dumps(message))
    await asyncio.sleep(1)
    
    assert result["worked"]


@pytest.mark.asyncio
async def test_calls_SYNC_error_callback():
    result = { "worked": False }

    def cb(*args, **kwargs):
        result["worked"] = True

    gw = GatewayAPI("host", "gateway_token", error_callback=cb)
    message = {
        "type": "error",
        "error": "This Gateway's token has been rotated. Please use the new one.",
        "disconnect": True
    }

    await gw.handle_message(json.dumps(message))
    await asyncio.sleep(1)
    


@pytest.mark.asyncio
async def test_calls_transit_callback():
    result = { "worked": False }

    def cb(*args, **kwargs):
        result["worked"] = True

    gw = GatewayAPI("host", "gateway_token", transit_callback=cb)
    # ToDo: Update this example message
    message =  {
        "type": "transit",
    }

    await gw.handle_message(json.dumps(message))
    await asyncio.sleep(1)
    

@pytest.mark.asyncio
async def test_calls_SYNC_received_blob_callback():
    result = { "worked": False }

    def cb(*args, **kwargs):
        result["worked"] = True

    gw = GatewayAPI("host", "gateway_token", received_blob_callback=cb)
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

    await gw.handle_message(message)
    await asyncio.sleep(1)
    

