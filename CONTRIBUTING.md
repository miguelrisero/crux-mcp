# Contributing

Bug reports and PRs welcome. The project is small on purpose, so the bar is mostly "does it stay small and stay correct".

## Setup

```bash
git clone https://github.com/miguelrisero/crux-mcp && cd crux-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Before opening a PR

```bash
pytest          # must pass without an API key
ruff check .
```

CI runs both on Python 3.10 through 3.13.

## House rules

**The test suite stays offline.** No test may need `CRUX_API_KEY` or reach the network. Contributors without a key must be able to run the whole suite, and CI must not depend on a live third-party API. Add fixtures, not live calls.

**Keep the dependency list at one.** HTTP goes through `urllib`, not `requests`. Every dependency an MCP server adds is one the user installs to run it.

**New tools need annotations.** Everything here is read-only against a public dataset, so tools carry `read_only_hint=True`, `destructive_hint=False`, `idempotent_hint=True`, `open_world_hint=True`. If you add a tool that breaks any of those, say so in the PR.

**Summarise, don't relay.** The raw CrUX response is nested histogram buckets. Tools should return the number an agent can act on plus its assessment, with `raw=true` available when someone wants the envelope. A tool that dumps the API response verbatim pushes the parsing cost onto every caller.

**Errors should say what to do.** CrUX returns `404` for "not enough traffic for a record" and a bare `400 INVALID_ARGUMENT` for wrong-auth. Both are easy to misread. Translate them.

## Testing against real data

Once you have a key:

```bash
export CRUX_API_KEY=...
python -c "from crux_mcp.server import crux_record; print(crux_record(origin='https://www.google.com'))"
```

Or run it through the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector uvx --from . crux-mcp
```

## Releasing

Maintainers: bump `version` in `pyproject.toml` and `server.json`, add a `CHANGELOG.md` entry, then tag:

```bash
git tag v0.2.0 && git push origin v0.2.0
```

The release workflow builds and publishes to PyPI via trusted publishing. No token is stored anywhere.
