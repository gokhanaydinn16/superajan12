from __future__ import annotations

import argparse
import asyncio

from rich.console import Console
from rich.table import Table

from superajan12.agents.reference import CryptoReferenceAgent
from superajan12.agents.risk import RiskEngine
from superajan12.agents.scanner import MarketScannerAgent
from superajan12.audit import AuditLogger
from superajan12.config import get_settings
from superajan12.connectors.binance import BinanceFuturesClient
from superajan12.connectors.coinbase import CoinbasePublicClient
from superajan12.connectors.okx import OKXPublicClient
from superajan12.connectors.polymarket import PolymarketClient
from superajan12.endpoint_check import verify_polymarket_public_endpoints
from superajan12.reporting import Reporter
from superajan12.storage import SQLiteStore

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


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "scan":
        asyncio.run(run_scan(limit=args.limit, save=not args.no_save))
    elif args.command == "reference-check":
        asyncio.run(run_reference_check(symbols=args.symbols))
    elif args.command == "init-db":
        init_db()
    elif args.command == "verify-endpoints":
        asyncio.run(run_verify_endpoints())
    elif args.command == "report":
        report(top=args.top)


if __name__ == "__main__":
    main()
