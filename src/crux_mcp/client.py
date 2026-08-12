"""Thin client for the Chrome UX Report API.

CrUX authenticates with an API key. It does NOT accept OAuth bearer tokens: a
service-account token is rejected with 400 INVALID_ARGUMENT even for a known-good
origin, so these credentials cannot be shared with Search Console or GA4 servers.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

BASE = "https://chromeuxreport.googleapis.com/v1"

FORM_FACTORS = ("PHONE", "DESKTOP", "TABLET", "ALL")

# Core Web Vitals thresholds. good = at or below the first number,
# poor = above the second. https://web.dev/articles/defining-core-web-vitals-thresholds
THRESHOLDS: dict[str, tuple[float, float]] = {
    "largest_contentful_paint": (2500, 4000),
    "interaction_to_next_paint": (200, 500),
    "cumulative_layout_shift": (0.1, 0.25),
    "first_contentful_paint": (1800, 3000),
    "experimental_time_to_first_byte": (800, 1800),
    "round_trip_time": (100, 300),
}

# The three that Google actually uses to assess a page.
CORE_WEB_VITALS = (
    "largest_contentful_paint",
    "interaction_to_next_paint",
    "cumulative_layout_shift",
)


class CruxError(RuntimeError):
    """Raised when the CrUX API cannot answer, with a human-readable reason."""


@dataclass
class Target:
    """Either an origin (whole site) or a single url. Never both."""

    origin: str | None = None
    url: str | None = None

    def payload(self) -> dict:
        if self.url and self.origin:
            raise CruxError("pass either origin or url, not both")
        if self.url:
            return {"url": self.url}
        if self.origin:
            return {"origin": self.origin}
        raise CruxError("pass either origin or url")


def assess(metric: str, p75: float | int | None) -> str:
    """Classify a p75 against the published threshold for that metric."""
    if p75 is None:
        return "unknown"
    bounds = THRESHOLDS.get(metric)
    if not bounds:
        return "unknown"
    good, poor = bounds
    if p75 <= good:
        return "good"
    if p75 <= poor:
        return "needs-improvement"
    return "poor"


class CruxClient:
    def __init__(self, api_key: str | None = None, timeout: int = 30) -> None:
        self.api_key = (api_key or os.environ.get("CRUX_API_KEY") or "").strip()
        self.timeout = timeout

    def _post(self, endpoint: str, body: dict) -> dict:
        if not self.api_key:
            raise CruxError(
                "CRUX_API_KEY is not set. Enable the Chrome UX Report API at "
                "console.cloud.google.com, create an API key under Credentials, "
                "and set CRUX_API_KEY. CrUX does not accept OAuth or service-account "
                "credentials."
            )

        req = urllib.request.Request(
            f"{BASE}/records:{endpoint}?key={self.api_key}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:400]
            if exc.code == 404:
                raise CruxError(
                    "no CrUX data for that target. CrUX only covers destinations with "
                    "enough real-user traffic; individual pages often have no record "
                    "even when the origin does. Try the origin instead of the url."
                ) from exc
            if exc.code == 403:
                raise CruxError(
                    "denied. Check the Chrome UX Report API is enabled on the project "
                    "and that any API-key restriction allows it."
                ) from exc
            if exc.code == 429:
                raise CruxError("rate limited by CrUX. Back off and retry.") from exc
            raise CruxError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise CruxError(f"network error reaching CrUX: {exc.reason}") from exc

    @staticmethod
    def _form_factor(form_factor: str | None) -> dict:
        if not form_factor:
            return {}
        ff = form_factor.upper()
        if ff not in FORM_FACTORS:
            raise CruxError(f"form_factor must be one of {', '.join(FORM_FACTORS)}")
        # ALL means "do not filter", which the API expresses by omitting the field.
        return {} if ff == "ALL" else {"formFactor": ff}

    def record(self, target: Target, form_factor: str | None = "PHONE") -> dict:
        body = {**target.payload(), **self._form_factor(form_factor)}
        return self._post("queryRecord", body)

    def history(self, target: Target, form_factor: str | None = "PHONE") -> dict:
        body = {**target.payload(), **self._form_factor(form_factor)}
        return self._post("queryHistoryRecord", body)


def summarise_record(raw: dict) -> dict:
    """Reduce the CrUX envelope to p75s plus a pass/fail assessment."""
    record = raw.get("record", {})
    metrics = record.get("metrics", {})

    out: dict = {
        "key": record.get("key", {}),
        "collection_period": record.get("collectionPeriod"),
        "metrics": {},
    }
    for name, payload in metrics.items():
        p75 = payload.get("percentiles", {}).get("p75")
        entry = {"p75": p75, "assessment": assess(name, _numeric(p75))}
        fractions = payload.get("histogram")
        if fractions:
            entry["distribution"] = {
                "good": fractions[0].get("density"),
                "needs_improvement": fractions[1].get("density") if len(fractions) > 1 else None,
                "poor": fractions[2].get("density") if len(fractions) > 2 else None,
            }
        out["metrics"][name] = entry

    cwv = [out["metrics"].get(m, {}).get("assessment") for m in CORE_WEB_VITALS]
    present = [c for c in cwv if c and c != "unknown"]
    out["core_web_vitals_pass"] = bool(present) and all(c == "good" for c in present)
    return out


def summarise_history(raw: dict) -> dict:
    """Flatten the history envelope into per-metric weekly series."""
    record = raw.get("record", {})
    periods = record.get("collectionPeriods", [])
    labels = [_period_end(p) for p in periods]

    series: dict = {"weeks": labels, "metrics": {}}
    for name, payload in record.get("metrics", {}).items():
        points = payload.get("percentilesTimeseries", {}).get("p75s", [])
        # strict=False on purpose: a short or padded series should degrade to the
        # points we can pair up, not raise and lose the whole response.
        series["metrics"][name] = [
            {"week_ending": label, "p75": value, "assessment": assess(name, _numeric(value))}
            for label, value in zip(labels, points, strict=False)
        ]
    return series


def _numeric(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _period_end(period: dict) -> str | None:
    last = period.get("lastDate") or {}
    if not last:
        return None
    return f"{last.get('year'):04d}-{last.get('month'):02d}-{last.get('day'):02d}"
