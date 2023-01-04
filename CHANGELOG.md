# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/kubos/majortom_gateway_package/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/kubos/majortom_gateway_package/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kubos/majortom_gateway_package/compare/v0.0.10...v0.1.0
[0.0.10]: https://github.com/kubos/majortom_gateway_package/compare/0.0.2...v0.0.10
[0.0.2]: https://github.com/kubos/majortom_gateway_package/compare/0.0.1...0.0.2
[0.0.1]: https://github.com/kubos/majortom_gateway_package/releases/tag/0.0.1