from __future__ import annotations

import argparse

from rich.console import Console
from rich.table import Table

from superajan12.approval import ManualApprovalGate
from superajan12.agents.reference import CryptoReferenceAgent
from superajan12.agents.risk import RiskEngine
from superajan12.agents.scanner import MarketScannerAgent
from superajan12.audit import AuditLogger
from superajan12.capital_limits import CapitalLimitEngine
from superajan12.config import get_settings
from superajan12.connectors.binance import BinanceFuturesClient
from superajan12.connectors.coinbase import CoinbasePublicClient
from superajan12.connectors.okx import OKXPublicClient
from superajan12.connectors.polymarket import PolymarketClient
from superajan12.endpoint_check import verify_polymarket_public_endpoints
from superajan12.execution_guard import ExecutionGuard, ExecutionDecision
from superajan12.live_connector import LiveExecutionConnector
from superajan12.model_registry import ModelRegistry, ModelVersion
from superajan12.reconciliation import ReconciliationAgent
from superajan12.reporting import Reporter
from superajan12.safety import SafetyController
from superajan12.shadow import ShadowEvaluator
from superajan12.storage import SQLiteStore
from superajan12.strategy import StrategyScorer

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="superajan12")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan Polymarket markets and create paper ideas")
    scan.add_argument("--limit", type=int, default=25)
    scan.add_argument("--no-save", action="store_true", help="Do not write SQLite or audit log records")

    reference = subparsers.add_parser("reference-check", help="Cross-check crypto reference prices")
    reference.add_argument("--symbols", default="BTC,ETH,SOL", help="Comma-separated symbols: BTC,ETH,SOL")

    report_parser = subparsers.add_parser("report", help="Show local paper/shadow report")
    report_parser.add_argument("--top", type=int, default=10)

    shadow = subparsers.add_parser("shadow-mark", help="Mark one paper position with latest price")
    shadow.add_argument("--position-id", type=int, required=True)
    shadow.add_argument("--market-id", required=True)
    shadow.add_argument("--entry-price", type=float, required=True)
    shadow.add_argument("--size-shares", type=float, required=True)
    shadow.add_argument("--side", default="YES")
    shadow.add_argument("--risk-usdc", type=float, required=True)
    shadow.add_argument("--latest-price", type=float, required=True)

    subparsers.add_parser("shadow-report", help="Show aggregate shadow outcome report")

    strategy = subparsers.add_parser("strategy-score", help="Score a strategy from comma-separated PnL values")
    strategy.add_argument("--name", required=True)
    strategy.add_argument("--pnl", required=True, help="Comma-separated PnL values, e.g. 1.2,-0.5,0.8")
    strategy.add_argument("--save", action="store_true", help="Save score to SQLite")

    strategy_list = subparsers.add_parser("strategy-list", help="List stored strategy scores")
    strategy_list.add_argument("--limit", type=int, default=10)

    model = subparsers.add_parser("model-register", help="Validate and store a model version")
    model.add_argument("--name", required=True)
    model.add_argument("--version", required=True)
    model.add_argument("--status", required=True, choices=sorted(ModelRegistry.allowed_statuses))
    model.add_argument("--notes", default=None)

    model_list = subparsers.add_parser("model-list", help="List stored model versions")
    model_list.add_argument("--limit", type=int, default=20)

    reconcile = subparsers.add_parser("reconcile", help="Compare local and external open position counts")
    reconcile.add_argument("--local", type=int, required=True)
    reconcile.add_argument("--external", type=int, required=True)

    capital = subparsers.add_parser("capital-check", help="Check hard capital limits")
    capital.add_argument("--requested-risk", type=float, required=True)
    capital.add_argument("--open-risk", type=float, required=True)
    capital.add_argument("--daily-pnl", type=float, required=True)
    capital.add_argument("--max-single", type=float, default=10.0)
    capital.add_argument("--max-open", type=float, default=50.0)
    capital.add_argument("--max-daily-loss", type=float, default=20.0)

    exec_check = subparsers.add_parser("execution-check", help="Check live execution safety gates without sending orders")
    exec_check.add_argument("--mode", choices=["paper", "shadow", "live"], default="paper")
    exec_check.add_argument("--secrets-ready", action="store_true")
    exec_check.add_argument("--approve", action="store_true")

    prepare = subparsers.add_parser("prepare-order", help="Prepare a dry-run order shape only")
    prepare.add_argument("--market-id", required=True)
    prepare.add_argument("--side", default="YES")
    prepare.add_argument("--price", type=float, required=True)
    prepare.add_argument("--size", type=float, required=True)
    prepare.add_argument("--force-guard", action="store_true", help="Use an allowed guard decision for dry-run testing")

    subparsers.add_parser("init-db", help="Create or migrate the local SQLite schema")
    subparsers.add_parser("verify-endpoints", help="Verify public Polymarket endpoints used by scanner")
    return parser


def build_polymarket_client() -> PolymarketClient:
    settings = get_settings()
    return PolymarketClient(
        gamma_base_url=str(settings.polymarket_gamma_base_url),
        clob_base_url=str(settings.polymarket_clob_base_url),
    )


def build_reference_agent() -> CryptoReferenceAgent:
    settings = get_settings()
    return CryptoReferenceAgent(
        binance=BinanceFuturesClient(str(settings.binance_usds_futures_base_url)),
        okx=OKXPublicClient(str(settings.okx_base_url)),
        coinbase=CoinbasePublicClient(str(settings.coinbase_public_base_url)),
        max_deviation_bps=settings.max_reference_price_deviation_bps,
    )


async def run_scan(limit: int, save: bool = True) -> None:
    settings = get_settings()
    client = build_polymarket_client()
    risk_engine = RiskEngine(
        max_market_risk_usdc=settings.max_market_risk_usdc,
        max_daily_loss_usdc=settings.max_daily_loss_usdc,
        min_volume_usdc=settings.min_volume_usdc,
        max_spread_bps=settings.max_spread_bps,
        min_liquidity_usdc=settings.min_liquidity_usdc,
    )
    scanner = MarketScannerAgent(polymarket=client, risk_engine=risk_engine)
    result = await scanner.scan(limit=limit)

    scan_id: int | None = None
    if save:
        store = SQLiteStore(settings.sqlite_path)
        scan_id = store.save_scan(result)
        audit = AuditLogger(settings.audit_log_path)
        audit.record("scan.completed", {"scan_id": scan_id, **result.model_dump(mode="json")})
        for score in result.scores:
            audit.record("market.scored", {"scan_id": scan_id, **score.model_dump(mode="json")})
        for idea in result.ideas:
            audit.record("paper_trade.idea", {"scan_id": scan_id, **idea.model_dump(mode="json")})
        for position in result.paper_positions:
            audit.record("paper_position.opened", {"scan_id": scan_id, **position.model_dump(mode="json")})

    table = Table(title="SuperAjan12 Polymarket Scan")
    table.add_column("Decision")
    table.add_column("Score", justify="right")
    table.add_column("Edge", justify="right")
    table.add_column("ResConf", justify="right")
    table.add_column("Spread bps", justify="right")
    table.add_column("Source")
    table.add_column("Question")
    table.add_column("Reasons")

    for score in result.scores[:limit]:
        table.add_row(
            score.decision.value,
            f"{score.score:,.1f}",
            "-" if score.edge is None else f"{score.edge:.4f}",
            "-" if score.resolution_confidence is None else f"{score.resolution_confidence:.2f}",
            "-" if score.spread_bps is None else f"{score.spread_bps:,.1f}",
            score.orderbook_source or "-",
            score.question[:80],
            "; ".join(score.reasons[:3]),
        )

    console.print(table)

    if scan_id is not None:
        console.print(f"\n[green]Saved scan_id={scan_id}[/green]")
        console.print(f"SQLite: {settings.sqlite_path}")
        console.print(f"Audit log: {settings.audit_log_path}")

    if result.ideas:
        console.print("\n[bold green]Paper trade ideas[/bold green]")
        for idea in result.ideas:
            console.print(
                f"- {idea.side} | risk={idea.risk_usdc:.2f} USDC | "
                f"price={idea.reference_price} | edge={idea.edge} | {idea.question}"
            )
    else:
        console.print("\n[yellow]Risk motoru hicbir market icin paper trade izni vermedi.[/yellow]")

    if result.paper_positions:
        console.print("\n[bold cyan]Paper positions opened[/bold cyan]")
        for position in result.paper_positions:
            console.print(
                f"- {position.side} | entry={position.entry_price:.4f} | "
                f"shares={position.size_shares:.4f} | risk={position.risk_usdc:.2f} | {position.question}"
            )


async def run_reference_check(symbols: str) -> None:
    agent = build_reference_agent()
    checks = []
    requested = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    for symbol in requested:
        if symbol == "BTC":
            checks.append(await agent.check_btc())
        elif symbol == "ETH":
            checks.append(await agent.check_eth())
        elif symbol == "SOL":
            checks.append(await agent.check_sol())
        else:
            console.print(f"[yellow]Unsupported reference symbol skipped:[/yellow] {symbol}")

    table = Table(title="SuperAjan12 Crypto Reference Check")
    table.add_column("Symbol")
    table.add_column("OK")
    table.add_column("Median")
    table.add_column("Max dev bps")
    table.add_column("Sources")
    table.add_column("Reasons")

    for check in checks:
        source_text = ", ".join(
            f"{source.source}:{'-' if source.price is None else f'{source.price:.2f}'}"
            for source in check.sources
        )
        table.add_row(
            check.symbol,
            "yes" if check.ok else "no",
            "-" if check.median_price is None else f"{check.median_price:.2f}",
            "-" if check.max_deviation_bps is None else f"{check.max_deviation_bps:.1f}",
            source_text,
            "; ".join(check.reasons),
        )
    console.print(table)

    if any(not check.ok for check in checks):
        raise SystemExit(1)


async def run_verify_endpoints() -> None:
    result = await verify_polymarket_public_endpoints(build_polymarket_client())
    table = Table(title="SuperAjan12 Endpoint Verification")
    table.add_column("Endpoint")
    table.add_column("OK")
    table.add_column("Detail")

    for check in result.checks:
        table.add_row(check.name, "yes" if check.ok else "no", check.detail)

    console.print(table)
    if not result.ok:
        raise SystemExit(1)


def init_db() -> None:
    settings = get_settings()
    SQLiteStore(settings.sqlite_path)
    console.print(f"[green]SQLite schema ready:[/green] {settings.sqlite_path}")


def report(top: int = 10) -> None:
    settings = get_settings()
    reporter = Reporter(settings.sqlite_path)
    aggregate = reporter.aggregate_summary()

    summary_table = Table(title="SuperAjan12 Aggregate Report")
    summary_table.add_column("Field")
    summary_table.add_column("Value")
    for key, value in aggregate.items():
        summary_table.add_row(str(key), str(value))
    console.print(summary_table)

    latest = reporter.latest_summary()
    if latest:
        latest_table = Table(title="Latest Scan")
        latest_table.add_column("Field")
        latest_table.add_column("Value")
        for key, value in latest.items():
            latest_table.add_row(str(key), str(value))
        console.print(latest_table)

    top_markets = reporter.top_scored_markets(limit=top)
    if top_markets:
        top_table = Table(title="Top Scored Markets")
        for column in ("decision", "score", "edge", "resolution_confidence", "spread_bps", "question"):
            top_table.add_column(column)
        for row in top_markets:
            top_table.add_row(
                str(row.get("decision")),
                f"{row.get('score'):.2f}",
                "-" if row.get("edge") is None else f"{row.get('edge'):.4f}",
                "-" if row.get("resolution_confidence") is None else f"{row.get('resolution_confidence'):.2f}",
                "-" if row.get("spread_bps") is None else f"{row.get('spread_bps'):.1f}",
                str(row.get("question"))[:80],
            )
        console.print(top_table)


def shadow_mark(args: argparse.Namespace) -> None:
    from superajan12.models import PaperPosition

    settings = get_settings()
    position = PaperPosition(
        market_id=args.market_id,
        question=args.market_id,
        side=args.side,
        entry_price=args.entry_price,
        size_shares=args.size_shares,
        risk_usdc=args.risk_usdc,
    )
    outcome = ShadowEvaluator().evaluate_position(position, latest_price=args.latest_price)
    outcome_id = SQLiteStore(settings.sqlite_path).save_shadow_outcome(args.position_id, outcome)
    console.print(f"[green]Saved shadow_outcome_id={outcome_id}[/green]")
    console.print(outcome.model_dump())


def shadow_report() -> None:
    summary = SQLiteStore(get_settings().sqlite_path).shadow_summary()
    table = Table(title="Shadow Outcome Summary")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in summary.items():
        table.add_row(str(key), str(value))
    console.print(table)


def strategy_score(args: argparse.Namespace) -> None:
    pnl_values = [float(value.strip()) for value in args.pnl.split(",") if value.strip()]
    score = StrategyScorer().score(args.name, pnl_values)
    table = Table(title="Strategy Score")
    for field in ("strategy_name", "sample_count", "total_pnl_usdc", "win_rate", "avg_pnl_usdc", "score"):
        table.add_column(field)
    table.add_row(
        score.strategy_name,
        str(score.sample_count),
        f"{score.total_pnl_usdc:.4f}",
        "-" if score.win_rate is None else f"{score.win_rate:.4f}",
        "-" if score.avg_pnl_usdc is None else f"{score.avg_pnl_usdc:.4f}",
        f"{score.score:.4f}",
    )
    console.print(table)
    if args.save:
        score_id = SQLiteStore(get_settings().sqlite_path).save_strategy_score(score)
        console.print(f"[green]Saved strategy_score_id={score_id}[/green]")


def strategy_list(limit: int) -> None:
    rows = SQLiteStore(get_settings().sqlite_path).list_strategy_scores(limit=limit)
    table = Table(title="Stored Strategy Scores")
    for column in ("id", "strategy_name", "sample_count", "total_pnl_usdc", "win_rate", "avg_pnl_usdc", "score", "created_at"):
        table.add_column(column)
    for row in rows:
        table.add_row(*(str(row.get(column)) for column in ("id", "strategy_name", "sample_count", "total_pnl_usdc", "win_rate", "avg_pnl_usdc", "score", "created_at")))
    console.print(table)


def model_register(args: argparse.Namespace) -> None:
    registry = ModelRegistry()
    version = ModelVersion(name=args.name, version=args.version, status=args.status, notes=args.notes)
    registry.validate(version)
    model_id = SQLiteStore(get_settings().sqlite_path).save_model_version(
        name=version.name,
        version=version.version,
        status=version.status,
        notes=version.notes,
    )
    console.print(f"[green]Saved model_version_id={model_id}[/green]")
    console.print(f"can_trade_live={registry.can_trade_live(version)}")


def model_list(limit: int) -> None:
    rows = SQLiteStore(get_settings().sqlite_path).list_model_versions(limit=limit)
    table = Table(title="Model Versions")
    for column in ("id", "name", "version", "status", "notes", "created_at"):
        table.add_column(column)
    for row in rows:
        table.add_row(*(str(row.get(column)) for column in ("id", "name", "version", "status", "notes", "created_at")))
    console.print(table)


def reconcile(args: argparse.Namespace) -> None:
    result = ReconciliationAgent().compare_counts(args.local, args.external)
    console.print({"ok": result.ok, "reasons": result.reasons})
    if not result.ok:
        raise SystemExit(1)


def capital_check(args: argparse.Namespace) -> None:
    decision = CapitalLimitEngine(
        max_single_trade_usdc=args.max_single,
        max_total_open_risk_usdc=args.max_open,
        max_daily_loss_usdc=args.max_daily_loss,
    ).check(
        requested_risk_usdc=args.requested_risk,
        current_open_risk_usdc=args.open_risk,
        current_daily_pnl_usdc=args.daily_pnl,
    )
    console.print(decision)
    if not decision.allowed:
        raise SystemExit(1)


def execution_check(args: argparse.Namespace) -> None:
    approval_gate = ManualApprovalGate()
    ticket = None
    if args.approve:
        ticket = approval_gate.approve(
            approval_gate.request("live_execution", "CLI execution-check"),
            approved_by="cli-operator",
        )
    decision = ExecutionGuard(approval_gate).can_execute(
        mode=args.mode,
        safety_state=SafetyController().state(),
        approval_ticket=ticket,
        secrets_ready=args.secrets_ready,
    )
    console.print({"allowed": decision.allowed, "reasons": decision.reasons})
    if not decision.allowed:
        raise SystemExit(1)


def prepare_order(args: argparse.Namespace) -> None:
    guard = ExecutionDecision(
        allowed=args.force_guard,
        reasons=("forced dry-run guard for local test",) if args.force_guard else ("guard not forced",),
    )
    order = LiveExecutionConnector().prepare_order(
        guard_decision=guard,
        market_id=args.market_id,
        side=args.side,
        price=args.price,
        size=args.size,
    )
    console.print(order)


def main() -> None:
    import asyncio

    args = build_parser().parse_args()
    if args.command == "scan":
        asyncio.run(run_scan(limit=args.limit, save=not args.no_save))
    elif args.command == "reference-check":
        asyncio.run(run_reference_check(symbols=args.symbols))
    elif args.command == "shadow-mark":
        shadow_mark(args)
    elif args.command == "shadow-report":
        shadow_report()
    elif args.command == "strategy-score":
        strategy_score(args)
    elif args.command == "strategy-list":
        strategy_list(limit=args.limit)
    elif args.command == "model-register":
        model_register(args)
    elif args.command == "model-list":
        model_list(limit=args.limit)
    elif args.command == "reconcile":
        reconcile(args)
    elif args.command == "capital-check":
        capital_check(args)
    elif args.command == "execution-check":
        execution_check(args)
    elif args.command == "prepare-order":
        prepare_order(args)
    elif args.command == "init-db":
        init_db()
    elif args.command == "verify-endpoints":
        asyncio.run(run_verify_endpoints())
    elif args.command == "report":
        report(top=args.top)


if __name__ == "__main__":
    main()
