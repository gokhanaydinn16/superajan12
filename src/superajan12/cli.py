from __future__ import annotations

import argparse
import asyncio

from rich.console import Console
from rich.table import Table

from superajan12.agents.risk import RiskEngine
from superajan12.agents.scanner import MarketScannerAgent
from superajan12.config import get_settings
from superajan12.connectors.polymarket import PolymarketClient

console = Console()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="superajan12")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan Polymarket markets and create paper ideas")
    scan.add_argument("--limit", type=int, default=25)
    return parser


async def run_scan(limit: int) -> None:
    settings = get_settings()
    client = PolymarketClient(
        gamma_base_url=str(settings.polymarket_gamma_base_url),
        clob_base_url=str(settings.polymarket_clob_base_url),
    )
    risk_engine = RiskEngine(
        max_market_risk_usdc=settings.max_market_risk_usdc,
        max_daily_loss_usdc=settings.max_daily_loss_usdc,
        min_volume_usdc=settings.min_volume_usdc,
        max_spread_bps=settings.max_spread_bps,
        min_liquidity_usdc=settings.min_liquidity_usdc,
    )
    scanner = MarketScannerAgent(polymarket=client, risk_engine=risk_engine)
    scores, ideas = await scanner.scan(limit=limit)

    table = Table(title="SuperAjan12 Polymarket Scan")
    table.add_column("Decision")
    table.add_column("Score", justify="right")
    table.add_column("Spread bps", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Liquidity", justify="right")
    table.add_column("Question")
    table.add_column("Reasons")

    for score in scores[:limit]:
        table.add_row(
            score.decision.value,
            f"{score.score:,.1f}",
            "-" if score.spread_bps is None else f"{score.spread_bps:,.1f}",
            f"{score.volume_usdc:,.0f}",
            f"{score.liquidity_usdc:,.0f}",
            score.question[:80],
            "; ".join(score.reasons[:3]),
        )

    console.print(table)

    if ideas:
        console.print("\n[bold green]Paper trade ideas[/bold green]")
        for idea in ideas:
            console.print(
                f"- {idea.side} | risk={idea.risk_usdc:.2f} USDC | price={idea.reference_price} | {idea.question}"
            )
    else:
        console.print("\n[yellow]Risk motoru hicbir market icin paper trade izni vermedi.[/yellow]")


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "scan":
        asyncio.run(run_scan(limit=args.limit))


if __name__ == "__main__":
    main()
