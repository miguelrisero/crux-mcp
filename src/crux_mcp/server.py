"""MCP server exposing the Chrome UX Report as tools."""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from .client import (
    CORE_WEB_VITALS,
    CruxClient,
    CruxError,
    Target,
    summarise_history,
    summarise_record,
)

app = MCPServer(
    "crux",
    instructions=(
        "Real-user Core Web Vitals from Google's Chrome UX Report. Use this for "
        "'how does this page perform for actual visitors', not for lab metrics. "
        "Field data is what Google uses for the page experience signal. CrUX only "
        "covers destinations with enough traffic, so prefer origin-level queries "
        "when a specific url returns no data."
    ),
)

_client = CruxClient()

# Every tool is a read-only query against a public Google dataset. Nothing mutates,
# repeats are safe, and all of them reach the open internet.
READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=True,
)



def _ok(payload: dict) -> str:
    return json.dumps(payload, indent=2)


def _err(exc: CruxError) -> str:
    return json.dumps({"error": str(exc)}, indent=2)


@app.tool(annotations=READ_ONLY, title="CrUX: current Core Web Vitals")
def crux_record(
    origin: str = "",
    url: str = "",
    form_factor: str = "PHONE",
    raw: bool = False,
) -> str:
    """Current p75 Core Web Vitals for an origin or a single URL.

    Pass EITHER origin (e.g. https://www.betterpic.io — covers the whole site) OR
    url (one page). form_factor is PHONE, DESKTOP, TABLET or ALL. Returns each
    metric's p75 with a good / needs-improvement / poor assessment, plus an overall
    core_web_vitals_pass. Set raw=true for the untouched API response.
    """
    try:
        data = _client.record(Target(origin=origin or None, url=url or None), form_factor)
    except CruxError as exc:
        return _err(exc)
    return _ok(data if raw else summarise_record(data))


@app.tool(annotations=READ_ONLY, title="CrUX: weekly trend")
def crux_history(
    origin: str = "",
    url: str = "",
    form_factor: str = "PHONE",
    metric: str = "",
) -> str:
    """Weekly Core Web Vitals trend, up to 25 points, for charting or regression checks.

    Same origin / url / form_factor rules as crux_record. Pass metric to return just
    one series, e.g. largest_contentful_paint, interaction_to_next_paint,
    cumulative_layout_shift, first_contentful_paint, experimental_time_to_first_byte.
    """
    try:
        data = _client.history(Target(origin=origin or None, url=url or None), form_factor)
    except CruxError as exc:
        return _err(exc)

    summary = summarise_history(data)
    if metric:
        series = summary["metrics"].get(metric)
        if series is None:
            available = ", ".join(sorted(summary["metrics"])) or "none"
            return _ok({"error": f"no series named {metric}", "available": available})
        return _ok({"weeks": summary["weeks"], metric: series})
    return _ok(summary)


@app.tool(annotations=READ_ONLY, title="CrUX: compare origins")
def crux_compare(
    origins: str,
    form_factor: str = "PHONE",
) -> str:
    """Compare Core Web Vitals across several origins — yours against competitors.

    origins is a comma-separated list, e.g.
    "https://www.betterpic.io,https://www.aragon.ai,https://www.headshotpro.com".
    Returns one row per origin with the three Core Web Vitals and whether it passes.
    Origins with no CrUX record are reported rather than dropped silently.
    """
    rows = []
    for raw_origin in [o.strip() for o in origins.split(",") if o.strip()]:
        try:
            data = _client.record(Target(origin=raw_origin), form_factor)
        except CruxError as exc:
            rows.append({"origin": raw_origin, "error": str(exc)})
            continue
        summary = summarise_record(data)
        rows.append(
            {
                "origin": raw_origin,
                "core_web_vitals_pass": summary["core_web_vitals_pass"],
                **{
                    name: summary["metrics"].get(name, {}).get("p75")
                    for name in CORE_WEB_VITALS
                },
            }
        )
    return _ok({"form_factor": form_factor, "results": rows})


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
