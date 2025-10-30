#!/usr/bin/env python3
"""
Simple test script for Major Tom Gateway API.

Usage:
    python test_gateway.py <host> <gateway_token> [--http] [--ssl-verify] [--ca-bundle PATH]

Examples:
    python test_gateway.py majortom.example.com abc123token
    python test_gateway.py localhost:3000 test_token --http
    python test_gateway.py majortom.example.com token123 --ssl-verify --ca-bundle /path/to/ca.pem
"""

import asyncio
import argparse
import logging
import sys
import time
from majortom_gateway import GatewayAPI, ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestGateway:
    """Simple test gateway implementation."""

    # Test command definitions to register with Major Tom
    COMMAND_DEFINITIONS = {
        "ping": {
            "display_name": "Ping",
            "description": "Test gateway connectivity with a simple ping command",
            "tags": ["test"],
            "fields": []
        },
        "echo": {
            "display_name": "Echo",
            "description": "Echo back a message to test command field handling",
            "tags": ["test"],
            "fields": [
                {
                    "name": "message",
                    "type": "string",
                    "default": "Hello from Major Tom!"
                }
            ]
        },
        "test_telemetry": {
            "display_name": "Test Telemetry",
            "description": "Send test telemetry data to Major Tom",
            "tags": ["test"],
            "fields": []
        },
        "test_event": {
            "display_name": "Test Event",
            "description": "Send a test event to Major Tom",
            "tags": ["test"],
            "fields": []
        }
    }

    def __init__(self, host, gateway_token, system_name="test_gateway", **kwargs):
        self.host = host
        self.gateway_token = gateway_token
        self.system_name = system_name
        self.command_count = 0

        logger.info(f"Initializing gateway for host: {host}")
        logger.info(f"System name: {system_name}")

        try:
            self.gateway = GatewayAPI(
                host=host,
                gateway_token=gateway_token,
                command_callback=self.handle_command,
                error_callback=self.handle_error,
                rate_limit_callback=self.handle_rate_limit,
                cancel_callback=self.handle_cancel,
                transit_callback=self.handle_transit,
                received_blob_callback=self.handle_blob,
                **kwargs
            )
            logger.info("Gateway initialized successfully")
        except ValidationError as e:
            logger.error(f"Validation error: {e}")
            sys.exit(1)

    async def handle_command(self, command, gateway):
        """Handle incoming commands from Major Tom."""
        self.command_count += 1
        logger.info(f"📥 Command #{self.command_count} received:")
        logger.info(f"  ID: {command.id}")
        logger.info(f"  Type: {command.type}")
        logger.info(f"  System: {command.system}")
        logger.info(f"  Fields: {command.fields}")

        try:
            # Handle some basic test commands
            if command.type == "ping":
                logger.info("  → Responding with 'pong'")
                await gateway.complete_command(command.id, output="pong")

            elif command.type == "echo":
                message = command.fields.get("message", "Hello from gateway!")
                logger.info(f"  → Echoing: {message}")
                await gateway.complete_command(command.id, output=message)

            elif command.type == "test_telemetry":
                logger.info("  → Sending test telemetry")
                await gateway.transmit_metrics([
                    {
                        "system": self.system_name,
                        "subsystem": "test",
                        "metric": "test_value",
                        "value": 42.0,
                        "timestamp": int(time.time() * 1000)
                    }
                ])
                await gateway.complete_command(command.id, output="Telemetry sent")

            elif command.type == "test_event":
                logger.info("  → Sending test event")
                await gateway.transmit_events([
                    {
                        "system": self.system_name,
                        "type": "Test Event",
                        "level": "nominal",
                        "message": "This is a test event from the gateway",
                        "timestamp": int(time.time() * 1000)
                    }
                ])
                await gateway.complete_command(command.id, output="Event sent")

            else:
                logger.warning(f"  → Unknown command type: {command.type}")
                await gateway.fail_command(
                    command.id,
                    errors=[f"Unknown command type: {command.type}"]
                )

        except Exception as e:
            logger.error(f"  ❌ Error handling command: {e}")
            await gateway.fail_command(command.id, errors=[str(e)])

    async def handle_error(self, message, gateway):
        """Handle error messages from Major Tom."""
        logger.error(f"❌ Error from Major Tom: {message.get('error', 'Unknown error')}")
        if message.get('disconnect'):
            logger.warning("Major Tom requested disconnect")

    async def handle_rate_limit(self, message, gateway):
        """Handle rate limit notifications."""
        rate_limit = message.get('rate_limit', {})
        logger.warning(f"⚠️  Rate limit: {rate_limit.get('error', 'Rate limited')}")
        logger.warning(f"   Retry after: {rate_limit.get('retry_after', 'unknown')} seconds")

    async def handle_cancel(self, command_id, gateway):
        """Handle command cancellation requests."""
        logger.info(f"🚫 Cancel request for command ID: {command_id}")

    async def handle_transit(self, message, gateway):
        """Handle ground station transit notifications."""
        logger.info(f"🛰️  Transit notification: {message}")

    async def handle_blob(self, blob, context, gateway):
        """Handle received binary data."""
        logger.info(f"📦 Received blob: {len(blob)} bytes")
        logger.info(f"   Context: {context}")

    async def _wait_for_connection(self, timeout: int = 30) -> None:
        """Wait for WebSocket connection to be established."""
        logger.info("⏳ Waiting for connection to be established...")
        start_time = asyncio.get_event_loop().time()

        while not self.gateway.websocket:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError(f"Failed to connect within {timeout} seconds")
            await asyncio.sleep(0.5)

        logger.info("✅ Connection established")

    async def _register_command_definitions(self) -> None:
        """Send command definitions to Major Tom."""
        try:
            if not self.gateway.websocket:
                logger.warning("Cannot send command definitions - websocket not connected")
                return

            logger.info(f"📝 Registering {len(self.COMMAND_DEFINITIONS)} command definitions...")
            await self.gateway.update_command_definitions(
                system=self.system_name,
                definitions=self.COMMAND_DEFINITIONS
            )
            logger.info("✅ Command definitions registered with Major Tom")

        except Exception as e:
            logger.error(f"❌ Failed to register command definitions: {e}")

    async def run(self):
        """Connect to Major Tom and run the gateway."""
        logger.info("=" * 60)
        logger.info("🚀 Starting Major Tom Gateway Test")
        logger.info("=" * 60)
        logger.info(f"Host: {self.host}")
        logger.info(f"System: {self.system_name}")
        logger.info(f"Mission: {self.gateway.mission_name or 'Not connected yet'}")
        logger.info("")
        logger.info("Available test commands:")
        logger.info("  - ping: Responds with 'pong'")
        logger.info("  - echo: Echoes a message (field: 'message')")
        logger.info("  - test_telemetry: Sends test telemetry")
        logger.info("  - test_event: Sends test event")
        logger.info("")
        logger.info("Press Ctrl+C to shutdown gracefully")
        logger.info("=" * 60)
        logger.info("")

        try:
            # Start connection in background
            logger.info("🔌 Connecting to Major Tom...")
            connection_task = asyncio.create_task(self.gateway.connect_with_retries())

            # Wait for connection to be established
            await self._wait_for_connection()

            # Register command definitions
            await self._register_command_definitions()

            logger.info("")
            logger.info("✅ Gateway is ready and listening for commands")
            logger.info("")

            # Wait for connection task or interruption
            await connection_task

        except KeyboardInterrupt:
            logger.info("\n🛑 Shutdown requested by user")
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
        finally:
            logger.info("Disconnecting from Major Tom...")
            await self.gateway.disconnect()
            logger.info("✅ Disconnected successfully")
            logger.info(f"📊 Total commands processed: {self.command_count}")


def main():
    """Parse arguments and run the test gateway."""
    parser = argparse.ArgumentParser(
        description='Test script for Major Tom Gateway API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('host', help='Major Tom host (e.g., majortom.example.com)')
    parser.add_argument('gateway_token', help='Gateway authentication token')
    parser.add_argument('--system', default='test_gateway',
                       help='System name for command definitions (default: test_gateway)')
    parser.add_argument('--http', action='store_true',
                       help='Use HTTP/WS instead of HTTPS/WSS (for local testing)')
    parser.add_argument('--ssl-verify', action='store_true',
                       help='Verify SSL certificates')
    parser.add_argument('--ca-bundle', metavar='PATH',
                       help='Path to CA certificate bundle (required if --ssl-verify is used)')
    parser.add_argument('--basic-auth', metavar='USER:PASS',
                       help='HTTP Basic Auth credentials in format username:password')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')

    args = parser.parse_args()

    # Update logging level if debug is requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Validate SSL options
    if args.ssl_verify and not args.ca_bundle:
        logger.error("Error: --ca-bundle is required when --ssl-verify is used")
        sys.exit(1)

    # Build gateway kwargs
    gateway_kwargs = {
        'http': args.http,
        'ssl_verify': args.ssl_verify,
    }

    if args.ca_bundle:
        gateway_kwargs['ssl_ca_bundle'] = args.ca_bundle

    if args.basic_auth:
        gateway_kwargs['basic_auth'] = args.basic_auth

    # Create and run the test gateway
    test_gateway = TestGateway(args.host, args.gateway_token, system_name=args.system, **gateway_kwargs)

    try:
        asyncio.run(test_gateway.run())
    except KeyboardInterrupt:
        logger.info("\n👋 Goodbye!")


if __name__ == '__main__':
    main()
