# Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is [SemVer](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Published to PyPI. Install is now `uvx crux-mcp` rather than a git URL.

## [0.1.0] - 2026-08-12

First release.

### Added

- `crux_record` — current p75 Core Web Vitals for an origin or a single URL, with a
  good / needs-improvement / poor assessment per metric and an overall
  `core_web_vitals_pass`.
- `crux_history` — up to 25 weekly data points, already paired with their week-ending
  dates so the output charts without further work.
- `crux_compare` — several origins side by side. Origins with no CrUX record are
  reported explicitly rather than dropped, so a missing competitor never reads as a win.
- MCP tool annotations on all three (`readOnlyHint`, `idempotentHint`, `openWorldHint`)
  and human-readable tool titles.
- `server.json` for the MCP Registry.
- Offline test suite covering threshold boundaries, form-factor handling, the
  string-vs-numeric p75 case (CLS arrives as a string) and both summarisers.

### Notes

- CrUX authenticates with an **API key only**. A service-account bearer token is
  rejected with a bare `400 INVALID_ARGUMENT` — byte-identical to the error for a
  malformed body, which makes it easy to misdiagnose. Documented in the README.
- `404` from CrUX means "not enough traffic for a record", not a failure. Translated
  into that, with the suggestion to retry against the origin.
- `ALL` is not a form factor; it means "do not filter". Translated by omitting the field.

[Unreleased]: https://github.com/miguelrisero/crux-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/miguelrisero/crux-mcp/releases/tag/v0.1.0
