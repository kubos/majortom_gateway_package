# majortom_gateway_package

Python SDK for building "gateways" — long-running processes that bridge Major Tom's WebSocket Gateway API to a satellite (or simulator). A gateway connects to Major Tom over WebSocket, receives commands / cancels / transit events / blobs, and pushes back metrics, events, command updates, and downlinked files. **Published to PyPI as `majortom-gateway`** (the dist name on PyPI uses a dash; the Python package name is `majortom_gateway`).

## Stack
- Python **3.13+** (hard requirement; `setup.py` `python_requires='>=3.13'`)
- `websockets >= 13.0, < 14.0` — pinned tight, see gotcha below
- `requests` for the HTTPS REST endpoints (file ops)
- `asgiref` for `sync_to_async` (sync-callback dispatch)
- pytest for tests
- CircleCI for CI + PyPI publish

## Entry points
- `majortom_gateway/gateway_api.py` — the `GatewayAPI` class; ~95% of the package
- `majortom_gateway/command.py` — thin `Command` wrapper over the JSON message
- `majortom_gateway/exceptions.py` — exception hierarchy: `GatewayAPIError` → `ValidationError`, `FileTransferError` → `FileDownloadError` / `FileUploadError`
- `majortom_gateway/__init__.py` — public surface (`GatewayAPI`, `Command`, exceptions, `DEFAULT_MAX_QUEUE_SIZE`)
- `test_gateway.py` (repo root) — interactive test gateway used to verify connectivity to a Major Tom instance from the CLI; auto-registers `ping` / `echo` / `test_telemetry` / `test_event` commands

## Layout
- `majortom_gateway/` — the package source (4 files)
- `tests/` — pytest tests (`test_callbacks.py`, `test_gateway_class.py`, `test_reconnection.py`, `test_sync_callbacks.py`)
- `test_gateway.py` — CLI test gateway (separate from the unit-test suite)
- `requirements.txt` / `test_requirements.txt` / `deploy_requirements.txt` — split deps
- `Dockerfile.test` + `dockertest.sh` — containerized test runner
- `.circleci/config.yml` — `orbTest` → `test-deploy` (Test-PyPI) → `deploy` (PyPI)
- `VERSION` — single-line version file consumed by `setup.py`
- `CHANGELOG.md` — Keep-a-Changelog format; the source of release notes

## Cross-repo touch points
- **major-tom** is the only peer — this SDK *is* the gateway-side of major-tom's Gateway API.
  - **WebSocket endpoint** (`gateway_api.py:110–114`): `ws(s)://<host>/gateway_api/v1.0`. Verified on the major-tom side at `config/routes.rb:14–18` (`namespace :gateway_api` → `scope "/v:version"` → `get "/" → "websocket#new"`).
  - **Auth header** (`gateway_api.py:103–105`): `X-Gateway-Token: <token>`. Verified consumed by major-tom at `app/controllers/concerns/gateway_authentication.rb:11` (`request.headers["X-Gateway-Token"]`, with `params["gateway_token"]` as a URL fallback).
  - **HTTPS REST for file ops**: file uploads go to `POST /gateway_api/v1.0/downlinked_files` (verified at `major-tom/config/routes.rb:17`); file downloads pull from a presigned/staged path passed from major-tom.
  - **Message protocol** (verified in `gateway_api.handle_message`, `gateway_api.py:239–295`): inbound messages by `type`: `command`, `cancel`, `transit`, `received_blob`, `error`, `rate_limit`, `hello`. Outbound payload type names are server-defined (e.g. `measurements`, `events`, command updates).
  - **Mission name** is delivered by major-tom in the `hello` message; `self.mission_name` stays `None` until that arrives (`gateway_api.py:290–292`).
- **example-python-gateway** is the canonical consumer / reference impl. README links to it. Changes to the public API here should be validated against that example.
- **major-tom CLAUDE.md** also documents the local-dev test flow (gateway tokens stored in `major-tom/CLAUDE.local.md`, test command `python3 run.py localhost:3001 GATEWAY_TOKEN --http`). That doc is authoritative for the local dev wiring.

## Conventions
- **Conventional Commits**: recent history (`fix:`, `feat:`, `chore:`, `ci:`, `docs:`) follows the spec. Match it when committing here.
- **Versioning**: SemVer per the CHANGELOG header. Bump `VERSION` (single-line file) — `setup.py` reads it. CHANGELOG is the source of release notes; do not skip the `[Unreleased]` section.
- **Backward compatibility is load-bearing**: this is a *published library* with downstream gateways already running. The recent commits `cd9ec8e` (file exceptions also inherit from `RuntimeError`) and `8fb14d2` (restore the old `dict` kwarg on `transmit_command_update` alongside the new `extra_fields`) show the project's preference: when introducing a breaking change, also keep the old surface working for at least one release. Don't ship a clean break without that bridge.
- **Sync and async callbacks both supported**: the `callCallback` helper (`gateway_api.py:215–229`) routes async functions to `asyncio.ensure_future` and sync functions through `sync_to_async(cb, thread_sensitive=False)` — i.e. each sync callback runs on its own thread. Callback authors should write thread-safe code.
- **Validation at construction time**: `GatewayAPI.__init__` rejects invalid params with `ValidationError` *before* any I/O happens (`gateway_api.py:36–82`). Add new parameter validation in the same block, raising `ValidationError`.
- **Tests run in Docker**: `./dockertest.sh` is the canonical path; the venv route works but Docker is the CI parity.

## Gotchas & safety
- **No WebSocket keepalive.** `connect()` passes `ping_interval=None, ping_timeout=None` (`gateway_api.py:139–141`). If the network silently drops, the client doesn't detect it until the next send fails. The receiver loop and reconnect logic only fire on observable WS errors.
- **Local queue silently drops on overflow.** `transmit()` falls back to `self.queued_payloads` when disconnected (`gateway_api.py:303–324`); when `len(queued_payloads) >= max_queue_size` (default `100` per `DEFAULT_MAX_QUEUE_SIZE`), packets are dropped with only a `logger.warning` — no exception, no callback. Operators relying on metric durability while offline must raise `max_queue_size` deliberately.
- **403 error message echoes the gateway token.** `connect_with_retries` catches `InvalidStatusCode` and rewrites `e.args` to include the token: `f"Gateway Token is Invalid: {self.gateway_token} ..."` (`gateway_api.py:200–203`). That message ends up in logs and unhandled-exception traces. Sensitive values may leak — sanitize before logging upstream.
- **Reconnect logs end-of-loop as "unexpected".** When the receiver loop exits normally without `shutdown_intended`, it raises `ConnectionClosed(None, None)` to trigger reconnect (`gateway_api.py:159–161`). Even a clean server-side close shows as "ended unexpectedly, triggering reconnect" — not a bug, but noisy in logs.
- **`websockets` version is pinned tight (`>=13.0,<14.0`).** Per commit `5044cd3`, the package switched from `websockets.connect` to `websockets.asyncio.client.connect` because the former resolves to the legacy API (which doesn't accept `additional_headers`). Bumping to 14.x is *not* a drop-in — it requires re-validating the asyncio-client API surface.
- **Callback exceptions are swallowed.** `_handle_task_result` (`gateway_api.py:231–237`) logs exceptions from callback tasks but does not re-raise. A buggy callback won't crash the gateway; it'll log and keep running — easy to miss in production.
- **Python 3.13 is hard-required** (`setup.py:31`). Earlier 3.x versions are unsupported as of v0.1.5 (per the README migration guide).

## Common tasks
- **Run tests (Docker)**: `./dockertest.sh`
- **Run tests (venv)**: `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt -r test_requirements.txt && pytest tests/ -v`
- **Run interactive test gateway**: `python test_gateway.py <host> <gateway_token> [--http] [--system NAME] [--debug]` (full flag list in README)
- **Bump version**: edit `VERSION`, update `CHANGELOG.md` (move `[Unreleased]` items into a new dated section), commit with `chore: change version to X.Y.Z`
- **Release** (per major-tom CLAUDE.md's notes): triggered via CircleCI on the `release` branch / API. `test-deploy` job goes to Test-PyPI; `deploy` job goes to PyPI. Tokens are CI env vars (`TEST_PYPI_TOKEN`, `PYPI_TOKEN`).

## What this repo is *not*
- **Not a Major Tom server component.** All server-side handling lives in `major-tom`. This is a client SDK only.
- **Not the satellite gateway.** It's the *framework* a gateway uses. The actual satellite-specific gateway logic lives in implementations like `example-python-gateway` (or operator-private gateways).
- **Not a transport-agnostic client.** Tightly coupled to major-tom's WebSocket message protocol and `/gateway_api/v1.0/*` URL shape.
- **Not stable in the absolute sense.** README says "Beta"; the fast-moving compat fixes in 0.1.5 (websockets API migration, exception bases, kwarg renames) confirm that. Pin a specific version in downstream gateways and review the CHANGELOG before bumping.
