# crux-mcp

[![CI](https://github.com/miguelrisero/crux-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/miguelrisero/crux-mcp/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-server-purple)](https://modelcontextprotocol.io)

An [MCP](https://modelcontextprotocol.io) server for the **Chrome UX Report** — real-user Core Web Vitals for any origin or URL, straight from the dataset Google uses for its page experience signal.

Lab tools like Lighthouse tell you how a page performed *on the machine that ran the test*. CrUX tells you how it performs **for the people actually visiting it**, as the p75 across 28 days of real Chrome traffic. When the two disagree, the field data is the one that counts.

```
> How are our Core Web Vitals doing on mobile?

  largest_contentful_paint   1642 ms   good
  interaction_to_next_paint   145 ms   good
  cumulative_layout_shift      0.01    good
  core_web_vitals_pass: true
```

---

## Why this exists

CrUX is free and public, but awkward to reach from an agent:

- It is **API-key only**. It rejects OAuth and service-account credentials with a bare `400 INVALID_ARGUMENT`, so it cannot reuse the credentials your Search Console or GA4 servers already have. That failure mode gives no hint about the real cause.
- The raw response is a nest of histogram buckets. You want "is LCP good", not `histogram[0].density`.
- The history endpoint returns two parallel arrays that you have to zip yourself before anything can chart it.

This server handles all three, and tells you plainly when CrUX simply has no data for what you asked.

## Install

Requires Python 3.10+. No cloning needed — [`uvx`](https://docs.astral.sh/uv/) runs it on demand.

> Until the first PyPI release, replace `uvx crux-mcp` with
> `uvx --from git+https://github.com/miguelrisero/crux-mcp crux-mcp` in any snippet below.

### Claude Code

```bash
claude mcp add crux --scope user -e CRUX_API_KEY=your_key_here -- uvx crux-mcp
```

Or keep the key out of your MCP config entirely by sourcing it from a shared secrets
file at launch — worth doing if you already keep credentials in one place:

```bash
claude mcp add crux --scope user -- sh -c \
  'set -a; . "$HOME/.secrets/mcp-keys.env"; set +a; exec uvx crux-mcp'
```

### Claude Desktop / Cursor / Windsurf

Add to your MCP config (`claude_desktop_config.json`, `.cursor/mcp.json`, …):

```json
{
  "mcpServers": {
    "crux": {
      "command": "uvx",
      "args": ["crux-mcp"],
      "env": { "CRUX_API_KEY": "your_key_here" }
    }
  }
}
```

### VS Code

```bash
code --add-mcp '{"name":"crux","command":"uvx","args":["crux-mcp"],"env":{"CRUX_API_KEY":"your_key_here"}}'
```

### From a clone

```bash
git clone https://github.com/miguelrisero/crux-mcp && cd crux-mcp
pip install -e .
CRUX_API_KEY=your_key_here crux-mcp
```

## Getting an API key

Two minutes, free, no billing account required.

1. Open the [Google Cloud Console](https://console.cloud.google.com) and pick or create a project.
2. **APIs & Services → Library**, search **Chrome UX Report API**, click **Enable**.
3. **APIs & Services → Credentials → Create credentials → API key**.
4. Copy the key into `CRUX_API_KEY`.

**Restrict the key** while you are there — *Edit API key → API restrictions → Restrict key → Chrome UX Report API*. An API key is a bearer credential: anyone holding it can spend your quota. Restricting it to this one read-only API means a leak is close to harmless.

Quota is generous (roughly 150 queries/minute) and CrUX is read-only public data, so there is nothing to bill and nothing to leak about your users.

Verify it works:

```bash
curl -s "https://chromeuxreport.googleapis.com/v1/records:queryRecord?key=$CRUX_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"origin":"https://www.google.com","formFactor":"PHONE"}' | head -20
```

<details>
<summary>Why not OAuth, like the Search Console MCP?</summary>

CrUX exposes public aggregate data, so it authenticates the *caller* rather than a *user*, and Google implements that with API keys only. Passing a service-account bearer token returns:

```
400  Request contains an invalid argument.
```

with no mention of authentication — the same error you get for a malformed body, which makes it easy to misdiagnose. If you see that 400 on a request you are sure is well-formed, you are almost certainly authenticating the wrong way.
</details>

## Tools

| Tool | What it answers |
|---|---|
| `crux_record` | How does this origin or page perform for real users right now? |
| `crux_history` | Is it getting better or worse? Up to 25 weekly points. |
| `crux_compare` | How do we stack up against competitors? |

All three take `form_factor`: `PHONE` (default), `DESKTOP`, `TABLET` or `ALL`.

Every tool is annotated `readOnlyHint`, `idempotentHint` and `openWorldHint`, so clients
that surface capability hints can show these as safe to call without confirmation.

### `crux_record`

Pass **either** `origin` (whole site) **or** `url` (one page).

```json
{
  "key": { "origin": "https://www.betterpic.io" },
  "collection_period": { "lastDate": { "year": 2026, "month": 8, "day": 10 } },
  "metrics": {
    "largest_contentful_paint": {
      "p75": 1642,
      "assessment": "good",
      "distribution": { "good": 0.81, "needs_improvement": 0.13, "poor": 0.06 }
    },
    "interaction_to_next_paint": { "p75": 145, "assessment": "good" },
    "cumulative_layout_shift": { "p75": "0.01", "assessment": "good" }
  },
  "core_web_vitals_pass": true
}
```

`assessment` uses the [published thresholds](https://web.dev/articles/defining-core-web-vitals-thresholds). `core_web_vitals_pass` is true only when LCP, INP and CLS are all `good`. Pass `raw=true` for the untouched API response.

### `crux_history`

Returns weekly p75s already zipped to their week-ending dates — drop straight into a chart or a Grafana series. Narrow to one metric with `metric="largest_contentful_paint"`.

```json
{
  "weeks": ["2026-07-27", "2026-08-03"],
  "metrics": {
    "largest_contentful_paint": [
      { "week_ending": "2026-07-27", "p75": 2600, "assessment": "needs-improvement" },
      { "week_ending": "2026-08-03", "p75": 2100, "assessment": "good" }
    ]
  }
}
```

### `crux_compare`

```
origins: "https://www.betterpic.io,https://www.aragon.ai,https://www.headshotpro.com"
```

One row per origin with the three Core Web Vitals and a pass flag. Origins with no CrUX record are reported explicitly rather than dropped, so a missing competitor never silently looks like a win.

## Metrics available

`largest_contentful_paint`, `interaction_to_next_paint`, `cumulative_layout_shift`, `first_contentful_paint`, `experimental_time_to_first_byte`, `round_trip_time`, and others Google adds over time. The first three are the Core Web Vitals that feed the page experience signal.

## Known limits — read before trusting a blank result

- **CrUX only covers destinations with enough traffic.** A URL with too few visitors has no record at all. This is the single most common surprise: your homepage will have URL-level data while most blog posts only roll up to the origin. When a `url` query comes back empty, retry with `origin`.
- **Data is a 28-day rolling p75**, updated daily but always trailing. It will not show you the effect of a deploy you shipped this morning.
- **History is weekly and capped at 25 points**, roughly six months.
- **`ALL` is not a form factor**, it means "do not filter". The server translates it by omitting the field, which is what the API expects.

## Try it without an MCP client

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) runs the server
standalone and lets you call each tool by hand — the fastest way to confirm a key works:

```bash
CRUX_API_KEY=your_key npx @modelcontextprotocol/inspector uvx crux-mcp
```

## Development

```bash
git clone https://github.com/miguelrisero/crux-mcp && cd crux-mcp
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest          # no API key needed, the suite is offline
ruff check .
```

The client is deliberately dependency-free beyond `mcp` — plain `urllib`, no `requests`. Tests cover threshold boundaries, form-factor handling, string-vs-numeric p75 (CLS arrives as a string), and the summarisers, all without touching the network.

## Licence

MIT — see [LICENSE](LICENSE).
