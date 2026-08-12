"""crux-mcp — Chrome UX Report (real-user Core Web Vitals) as an MCP server."""

from .client import (
    CORE_WEB_VITALS,
    THRESHOLDS,
    CruxClient,
    CruxError,
    Target,
    assess,
    summarise_history,
    summarise_record,
)

__version__ = "0.1.0"

__all__ = [
    "CORE_WEB_VITALS",
    "THRESHOLDS",
    "CruxClient",
    "CruxError",
    "Target",
    "assess",
    "summarise_history",
    "summarise_record",
    "__version__",
]
