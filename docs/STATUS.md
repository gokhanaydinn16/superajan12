# SuperAjan12 Current Status

## Summary

SuperAjan12 is currently a safe paper/shadow trading core for Polymarket-centered prediction market research plus a desktop command-center surface. It does not send live orders. The system has market scanning, risk checks, quality agents, paper positions, shadow mark-to-market, strategy scoring, model version tracking, live-execution safety gates, and a local backend API that can be consumed by the desktop shell.

## What is complete

- Polymarket public market scanner.
- Polymarket CLOB orderbook, midpoint and spread fallback.
- SQLite persistence.
- JSONL audit log.
- Risk Engine v1.
- Resolution Agent v1.
- Probability baseline model.
- Liquidity Agent v2.
- Manipulation Risk Agent v1.
- News Reliability Agent v1.
- Social Signal Agent v1.
- Smart Wallet placeholder Agent v1.
- Binance, OKX, Coinbase crypto reference checks.
- Kalshi public connector.
- Cross-market matching v1.
- Paper portfolio and paper positions.
- Shadow mark-to-market evaluator.
- Strategy scorer.
- Model registry.
- Reconciliation scaffold.
- Secret manager scaffold.
- Manual approval gate.
- Capital limits.
- Execution guard.
- Dry-run live connector only.
- Desktop command center navigation shell.
- Desktop sidecar backend startup with health-check validation and fallback to external backend mode.
- Local backend endpoints for execution status, system health and event history.
- Local constrained-runtime compatibility path for backend and tests.
- CLI commands for scan, report, endpoint verification, reference checks, shadow, strategy, model, reconciliation, capital and execution checks.
- CI workflow, tests and runtime-compat validation job.

## What is intentionally not complete

- No live order sending.
- No real wallet/private key integration.
- No exchange account access.
- No autonomous code modification.
- No production deployment automation.
- No direct social media scraping.
- No direct Dune/Arkham/Nansen integration yet.

## Why live trading is still disabled

The system must prove itself in paper and shadow mode before handling capital. Live trading requires:

1. Endpoint verification in the user's runtime environment.
2. Sufficient paper/shadow sample size.
3. Positive strategy scores with acceptable drawdown.
4. Manual approval of model versions.
5. Secret handling outside git.
6. Reconciliation against the real exchange state.
7. Kill-switch and safe-mode integration in the actual process supervisor.
8. Legal/access review for the user's jurisdiction and platform eligibility.

## Ready-to-run command sequence

```bash
git pull
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
cp .env.example .env
superajan12 init-db
superajan12 verify-endpoints
superajan12 reference-check --symbols BTC,ETH,SOL
superajan12 scan --limit 25
superajan12 report
superajan12 shadow-report
pytest -q
ruff check src tests
```

## Constrained runtime path

If the runtime cannot currently install Python packages or does not yet have npm/Rust tooling ready, use:

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m superajan12.backend_server --host 127.0.0.1 --port 8000
```

This validates the backend and test surface through the repository's local compatibility layer while desktop packaging remains blocked.

## Exit criteria before live adapter work

- At least 500 scanned markets recorded.
- At least 100 paper positions recorded.
- Shadow outcomes recorded for a meaningful sample.
- Strategy score is positive across multiple periods.
- No unresolved endpoint failures.
- No recurring reconciliation mismatch.
- No high-severity audit incidents.
- Approved model version exists.
- Manual approval process is documented and tested.

## Current recommendation

Continue running paper/shadow mode. Keep live order sending disabled. Desktop packaging should resume only in an environment with npm registry access and a Rust toolchain.
