from __future__ import annotations

from typing import Any

from superajan12.agents.reference import ReferenceCheck


def serialize_reference_check(check: ReferenceCheck) -> dict[str, Any]:
    return {
        "symbol": check.symbol,
        "ok": check.ok,
        "median_price": check.median_price,
        "max_deviation_bps": check.max_deviation_bps,
        "sources": [
            {
                "source": source.source,
                "symbol": source.symbol,
                "price": source.price,
                "raw": source.raw,
            }
            for source in check.sources
        ],
        "reasons": list(check.reasons),
    }


def summarize_reference_checks(checks: list[ReferenceCheck]) -> dict[str, Any]:
    max_deviation = max((check.max_deviation_bps for check in checks if check.max_deviation_bps is not None), default=None)
    return {
        "total": len(checks),
        "ok_count": sum(1 for check in checks if check.ok),
        "failing_symbols": [check.symbol for check in checks if not check.ok],
        "max_deviation_bps": max_deviation,
    }
