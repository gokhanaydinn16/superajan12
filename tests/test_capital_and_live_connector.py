import pytest

from superajan12.capital_limits import CapitalLimitEngine
from superajan12.execution_guard import ExecutionDecision
from superajan12.live_connector import LiveExecutionConnector


def test_capital_limit_engine_allows_small_risk() -> None:
    engine = CapitalLimitEngine(
        max_single_trade_usdc=10,
        max_total_open_risk_usdc=50,
        max_daily_loss_usdc=20,
    )

    decision = engine.check(
        requested_risk_usdc=5,
        current_open_risk_usdc=10,
        current_daily_pnl_usdc=-1,
    )

    assert decision.allowed is True


def test_capital_limit_engine_blocks_large_single_trade() -> None:
    engine = CapitalLimitEngine(
        max_single_trade_usdc=10,
        max_total_open_risk_usdc=50,
        max_daily_loss_usdc=20,
    )

    decision = engine.check(
        requested_risk_usdc=25,
        current_open_risk_usdc=10,
        current_daily_pnl_usdc=-1,
    )

    assert decision.allowed is False
    assert any("single-trade" in reason for reason in decision.reasons)


def test_live_connector_blocks_when_guard_rejects() -> None:
    connector = LiveExecutionConnector()
    guard = ExecutionDecision(
        allowed=False,
        reasons=("blocked",),
        vetoes=("blocked",),
        stale_data_locked=False,
        hard_position_cap_hit=False,
        cancel_on_disconnect_required=True,
    )

    with pytest.raises(RuntimeError):
        connector.prepare_order(guard, market_id="m1", side="YES", price=0.5, size=10)


def test_live_connector_prepares_dry_run_order_when_guard_allows() -> None:
    connector = LiveExecutionConnector()
    guard = ExecutionDecision(
        allowed=True,
        reasons=("all gates passed",),
        vetoes=(),
        stale_data_locked=False,
        hard_position_cap_hit=False,
        cancel_on_disconnect_required=True,
    )

    order = connector.prepare_order(guard, market_id="m1", side="YES", price=0.5, size=10)

    assert order.dry_run is True
    assert order.market_id == "m1"
