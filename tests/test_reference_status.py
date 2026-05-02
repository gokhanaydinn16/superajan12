from superajan12.agents.reference import ReferenceCheck, ReferenceSource
from superajan12.reference_status import serialize_reference_check, summarize_reference_checks


def test_serialize_reference_check_preserves_sources_and_reasons() -> None:
    check = ReferenceCheck(
        symbol="BTC",
        ok=True,
        median_price=100.0,
        max_deviation_bps=12.5,
        sources=(
            ReferenceSource(source="binance", symbol="BTC", price=100.0, raw={"mark_price": 100.0}),
            ReferenceSource(source="okx", symbol="BTC", price=100.1, raw={"last_price": 100.1}),
        ),
        reasons=("reference prices agree",),
    )

    payload = serialize_reference_check(check)

    assert payload["symbol"] == "BTC"
    assert payload["ok"] is True
    assert len(payload["sources"]) == 2
    assert payload["sources"][0]["source"] == "binance"
    assert payload["reasons"] == ["reference prices agree"]


def test_summarize_reference_checks_reports_failures_and_max_deviation() -> None:
    checks = [
        ReferenceCheck(
            symbol="BTC",
            ok=True,
            median_price=100.0,
            max_deviation_bps=10.0,
            sources=(),
            reasons=("ok",),
        ),
        ReferenceCheck(
            symbol="ETH",
            ok=False,
            median_price=50.0,
            max_deviation_bps=85.0,
            sources=(),
            reasons=("deviation too high",),
        ),
    ]

    summary = summarize_reference_checks(checks)

    assert summary["total"] == 2
    assert summary["ok_count"] == 1
    assert summary["failing_symbols"] == ["ETH"]
    assert summary["max_deviation_bps"] == 85.0
