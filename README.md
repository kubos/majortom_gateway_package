[![CircleCI](https://circleci.com/gh/kubos/majortom_gateway_package.svg?style=svg)](https://circleci.com/gh/kubos/majortom_gateway_package)

# Major Tom Gateway API Package

Python package for interacting with Major Tom's Gateway API. This package provides a WebSocket-based client for bidirectional communication with Major Tom, supporting command execution, telemetry transmission, file transfers, and more.

## Installation

```bash
pip install majortom-gateway
```

## Quick Start

```python
import asyncio
from majortom_gateway import GatewayAPI

async def command_callback(command, gateway):
    """Handle incoming commands from Major Tom"""
    print(f"Received command: {command.type}")
    # Process command...
    await gateway.complete_command(command.id, output="Command executed successfully")

async def main():
    # Initialize the gateway
    gateway = GatewayAPI(
        host="your-majortom-instance.com",
        gateway_token="your-gateway-token",
        command_callback=command_callback
    )

    # Connect with automatic retries
    await gateway.connect_with_retries()

if __name__ == "__main__":
    asyncio.run(main())
```

## Features

- **WebSocket-based Communication**: Real-time bidirectional messaging with Major Tom
- **Automatic Reconnection**: Built-in retry logic with exponential backoff
- **Async/Sync Callbacks**: Support for both async and synchronous callback functions
- **File Transfers**: Upload and download files to/from Major Tom
- **Comprehensive Validation**: Input validation with clear error messages
- **Custom Exceptions**: Structured exception hierarchy for better error handling
- **SSL/TLS Support**: Configurable certificate verification

## Usage Examples

### Initialization Parameters

```python
from majortom_gateway import GatewayAPI

gateway = GatewayAPI(
    host="your-instance.com",              # Required: Major Tom hostname
    gateway_token="your-token",             # Required: Gateway authentication token
    ssl_verify=False,                       # Optional: Verify SSL certificates (default: False)
    basic_auth="username:password",         # Optional: HTTP Basic Auth credentials
    http=False,                             # Optional: Use ws:// instead of wss:// (default: False)
    ssl_ca_bundle="/path/to/cacert.pem",   # Optional: Path to CA certificate bundle
    command_callback=handle_command,        # Optional: Handler for command messages
    error_callback=handle_error,            # Optional: Handler for error messages
    rate_limit_callback=handle_rate_limit,  # Optional: Handler for rate limit messages
    cancel_callback=handle_cancel,          # Optional: Handler for command cancellation
    transit_callback=handle_transit,        # Optional: Handler for ground station transits
    received_blob_callback=handle_blob      # Optional: Handler for received binary data
)
```

### Transmitting Telemetry

```python
# Send metrics to Major Tom
await gateway.transmit_metrics([
    {
        "system": "spacecraft",
        "subsystem": "power",
        "metric": "battery_voltage",
        "value": 28.5,
        "timestamp": int(time.time() * 1000)  # Milliseconds since epoch
    }
])
```

### Transmitting Events

```python
# Send events to Major Tom
await gateway.transmit_events([
    {
        "system": "spacecraft",
        "type": "System Status",
        "level": "nominal",  # Can be: "debug", "nominal", "warning", or "error"
        "message": "System operating normally",
        "timestamp": int(time.time() * 1000)
    }
])
```

### Handling Commands

```python
async def command_callback(command, gateway):
    """Process commands from Major Tom"""
    try:
        if command.type == "ping":
            await gateway.complete_command(command.id, output="pong")
        elif command.type == "get_status":
            status = get_system_status()
            await gateway.complete_command(command.id, output=status)
        else:
            await gateway.fail_command(
                command.id,
                errors=[f"Unknown command type: {command.type}"]
            )
    except Exception as e:
        await gateway.fail_command(command.id, errors=[str(e)])
```

### File Operations

```python
# Download a staged file from Major Tom
filename, content = gateway.download_staged_file("/gateway/download/path/file.bin")
with open(filename, 'wb') as f:
    f.write(content)

# Upload a file to Major Tom
gateway.upload_downlinked_file(
    filename="telemetry_log.csv",
    filepath="/path/to/telemetry_log.csv",
    system="spacecraft",
    content_type="text/csv",
    command_id=123,  # Optional: associate with a command
    metadata={"duration": 3600}  # Optional: custom metadata
)
```

### Proper Shutdown

```python
# Disconnect gracefully (note: disconnect() is async)
await gateway.disconnect()
```

## Error Handling

The package provides a structured exception hierarchy for better error handling:

```python
from majortom_gateway import (
    GatewayAPIError,      # Base exception for all gateway errors
    ValidationError,      # Invalid parameters
    FileDownloadError,    # File download failures
    FileUploadError,      # File upload failures
)

try:
    gateway = GatewayAPI(
        host="",  # Invalid: empty host
        gateway_token="token"
    )
except ValidationError as e:
    print(f"Invalid configuration: {e}")

try:
    filename, content = gateway.download_staged_file("/invalid/path")
except FileDownloadError as e:
    print(f"Download failed: {e}")

# Catch all gateway-related errors
try:
    await gateway.transmit_metrics(metrics)
except GatewayAPIError as e:
    print(f"Gateway error: {e}")
```

## Migration Guide

### From 0.1.5 to Unreleased

**Breaking Change**: The `disconnect()` method is now async and must be awaited.

**Before:**
```python
gateway.disconnect()  # Old synchronous version
```

**After:**
```python
await gateway.disconnect()  # New async version
```

**Other Changes**:
- File operation errors now raise specific exceptions (`FileDownloadError`, `FileUploadError`) instead of `RuntimeError`
- Input parameters are now validated at initialization with clear error messages via `ValidationError`
- The `dict` parameter in `transmit_command_update()` has been renamed to `extra_fields`

## Requirements

- Python 3.6+
- websockets >= 8.1
- requests
- asgiref

## Development

The Gateway API Package is currently in Beta. Please [submit an issue](https://github.com/kubos/majortom_gateway_package/issues/new) or [come talk to us](https://slack.kubos.com) if you have any comments/questions/feedback.

### Quick Testing with test_gateway.py

A test script is included to quickly verify your connection to Major Tom and test basic gateway functionality:

```bash
# Set up virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run the test gateway
python test_gateway.py <host> <gateway_token> [options]
```

**Command-line options:**
- `--system NAME` - System name for command definitions (default: test_gateway)
- `--http` - Use HTTP/WS instead of HTTPS/WSS (for local testing)
- `--ssl-verify` - Verify SSL certificates
- `--ca-bundle PATH` - Path to CA certificate bundle
- `--basic-auth USER:PASS` - HTTP Basic Auth credentials
- `--debug` - Enable debug logging

**Example usage:**
```bash
# Connect to Major Tom production
python test_gateway.py majortom.example.com abc123token --system my_satellite

# Local development
python test_gateway.py localhost:3000 test_token --http --system test_sat

# With SSL verification
python test_gateway.py majortom.example.com token123 --ssl-verify --ca-bundle /path/to/ca.pem
```

The test gateway automatically registers these commands with Major Tom:
- **ping** - Simple connectivity test, responds with "pong"
- **echo** - Echo back a message (accepts a "message" field)
- **test_telemetry** - Sends sample telemetry data
- **test_event** - Sends a test event

After connecting, you can send these commands from Major Tom's UI to verify bidirectional communication.

### Testing

To run all tests:

```bash
# Using Docker (recommended)
./dockertest.sh

# Or using a virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt -r test_requirements.txt
pytest tests/ -v
```

## Additional Resources

- [Demo Gateway](https://github.com/kubos/example-python-gateway) - Complete example implementation
- [Major Tom Documentation](https://docs.majortom.cloud/) - Platform documentation
- [API Reference](https://docs.majortom.cloud/docs/gateway-api) - Gateway API specification

## License

See LICENSE file for details.