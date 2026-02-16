# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Configurable `max_queue_size` parameter to control how many payloads are queued while disconnected (default: 100, previously unlimited)

### Fixed
- Fixed `TypeError: BaseEventLoop.create_connection() got an unexpected keyword argument 'additional_headers'` by importing `connect` from `websockets.asyncio.client` (the new API) instead of using `websockets.connect` (which resolves to the legacy API even in websockets 13.x)

## [0.1.5] - 2026-01-13

### Added
- `test_gateway.py` - Interactive test script for quick gateway connectivity testing
  - Supports command-line arguments for host, token, and system name
  - Automatically registers test commands (ping, echo, test_telemetry, test_event)
  - Includes SSL verification and basic auth support
  - Provides example implementation of all callback handlers
- Custom exception hierarchy for better error handling:
  - `GatewayAPIError` - Base exception for all gateway errors
  - `ValidationError` - Raised for invalid parameters
  - `FileTransferError` - Base exception for file operations
  - `FileDownloadError` - Raised when file download fails
  - `FileUploadError` - Raised when file upload fails
- Comprehensive input validation in `GatewayAPI.__init__()`:
  - Validates all required parameters (host, gateway_token)
  - Type checking for all optional parameters
  - Format validation for basic_auth
  - File existence check for ssl_ca_bundle
  - Validates all callbacks are callable
- Increased WebSocket connection timeout to 120 seconds for high-latency connections
- Better error messages throughout connection handling
- New test suite for reconnection scenarios (`test_reconnection.py`)

### Changed
- **BREAKING**: `disconnect()` method is now async and must be awaited
- Improved file download error handling with better Content-Disposition parsing
- File operation errors now use specific exception types instead of generic RuntimeError
- Improved error logging to include error types and more context
- Changed deprecated `logger.warn()` to `logger.warning()`
- Fixed import style: using `from base64 import b64encode, b64decode` instead of `import base64`
- Replaced deprecated `asyncio.iscoroutinefunction()` with `inspect.iscoroutinefunction()`

### Fixed
- Fixed reconnection failing after server-side connection termination (e.g., during server restarts). The `connect()` method now properly propagates `ConnectionClosedError` to `connect_with_retries()` which triggers automatic reconnection with exponential backoff logging.
- Added explicit handling for both `websockets.ConnectionClosed` and `websockets.ConnectionClosedError` exceptions
- Improved logging during reconnection attempts with retry count tracking
- Disabled client-side ping timeout that caused connections to drop after ~22 seconds. Major Tom server handles keep-alive pings.
- Fixed TypeError when websocket becomes None after unexpected disconnection during `empty_queue()`. Now properly raises `ConnectionClosed` to trigger retry instead of failing with "'async for' requires an object with __aiter__ method"
- Fixed critical bug in `transmit_blob()` - changed from `base64.b64encode` to `b64encode` to match new imports
- Fixed encoding inconsistency in blob transmission (now consistently uses UTF-8 instead of cp437)
- Fixed race condition in `disconnect()` method by storing websocket reference before closing
- Fixed non-Pythonic `!= None` comparisons to use `is not None` (PEP 8)
- Fixed parameter name shadowing: renamed `dict` parameter to `extra_fields` in `transmit_command_update()`
- Fixed mutable default argument antipattern in `transmit_command_update()`
- Fixed websockets 10.0+ compatibility: changed `extra_headers` to `additional_headers`
- Updated minimum websockets version from 8.1 to 10.0 to reflect API changes
- Fixed test fixture for Python 3.14 compatibility

## [0.1.5] - 2023-11-21
- Retry connect when websocket connection is clobbered in empty_queue

## [0.1.4] - 2023-01-05
- Added a `disconnect` method to the gateway API. This allows a user to use the `connect_with_retries` method, but to shut down the connection from their implementation code without triggering automatic re-connect attempts.

## [0.1.3] - 2023-01-03
- Guarded against a KeyError if a `received_blob` message is received with an empty or missing `"blob"` key

## [0.1.2] - 2022-02-23
- Expanded set of HTTP response status codes that will trigger retry of websocket connection attempts

## [0.1.1] - 2021-09-01
- Added self.mission_name, which is populated when a connection is established

## [0.1.0] - 2021-05-24
### Added
- CHANGELOG!
- Automatic CI/CD process
- Multi-environment testing
- Allow callbacks to be written in synchronous (i.e. regular) Python!

## [0.0.10] - 2017-06-20
### Added
- Lots of tests

### Fixed
- Fix asyncio import for Python 3.8

## [0.0.2] and [0.0.1]
- Initial releases.

[Unreleased]: https://github.com/kubos/majortom_gateway_package/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/kubos/majortom_gateway_package/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/kubos/majortom_gateway_package/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/kubos/majortom_gateway_package/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/kubos/majortom_gateway_package/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/kubos/majortom_gateway_package/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kubos/majortom_gateway_package/compare/v0.0.10...v0.1.0
[0.0.10]: https://github.com/kubos/majortom_gateway_package/compare/0.0.2...v0.0.10
[0.0.2]: https://github.com/kubos/majortom_gateway_package/compare/0.0.1...0.0.2
[0.0.1]: https://github.com/kubos/majortom_gateway_package/releases/tag/0.0.1
