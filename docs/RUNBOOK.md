# SuperAjan12 Runbook

## Purpose

This runbook explains how to operate SuperAjan12 in safe paper/shadow mode.

## Modes

### paper

Default mode. Reads public data, scores markets, creates paper ideas and paper positions. No real orders.

### shadow

Future mode for continuous decision logging against live market data without sending orders.

### live

Not implemented. Live execution is intentionally blocked by safety gates and dry-run-only connector.

## Daily paper workflow

```bash
superajan12 verify-endpoints
superajan12 reference-check --symbols BTC,ETH,SOL
superajan12 scan --limit 50
superajan12 report
```

## Constrained runtime workflow

If the environment does not have external Python packages, Node registry access, or Rust tooling ready yet, use the local compatibility path first:

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m superajan12.backend_server --host 127.0.0.1 --port 8000
```

Expected behavior:

- tests still run through the local compatibility layer
- backend health endpoints still answer locally
- desktop packaging remains blocked until npm and Rust tooling are available

## Shadow workflow

After paper positions exist:

```bash
superajan12 shadow-mark --position-id 1 --market-id m1 --entry-price 0.40 --size-shares 25 --side YES --risk-usdc 10 --latest-price 0.50
superajan12 shadow-report
```

## Model workflow

```bash
superajan12 model-register --name probability --version 0.1.0 --status candidate --notes "baseline"
superajan12 model-list --limit 20
```

Promotion policy:

1. candidate: new model idea.
2. shadow: model is tested without live orders.
3. approved: model is eligible for future live use.
4. retired: model is disabled.

Only approved models may be considered for live execution later.

## Strategy workflow

```bash
superajan12 strategy-score --name baseline --pnl 1.2,-0.5,0.8 --save
superajan12 strategy-list --limit 10
```

A strategy is not trusted from one good result. It needs sufficient samples across different market conditions.

## Safety checks

```bash
superajan12 reconcile --local 0 --external 0
superajan12 capital-check --requested-risk 5 --open-risk 10 --daily-pnl -1
superajan12 execution-check --mode paper
```

Expected behavior:

- paper mode execution-check should fail for live execution.
- live mode should only pass if secrets and manual approval are simulated.
- prepare-order remains dry-run.

## Dry-run live preparation

```bash
superajan12 execution-check --mode live --secrets-ready --approve
superajan12 prepare-order --market-id m1 --side YES --price 0.50 --size 10 --force-guard
```

This does not send orders. It only prepares a dry-run order object.

## Incident response

If any of the following happen, stop scanning and inspect logs:

- Endpoint verification fails repeatedly.
- Reference prices diverge significantly.
- Scanner produces too many rejected markets unexpectedly.
- SQLite write failures occur.
- Audit log is not written.
- Reconciliation mismatch appears.

Immediate actions:

1. Stop process.
2. Preserve `data/superajan12.sqlite3` and `data/audit/events.jsonl`.
3. Run endpoint verification.
4. Check `.env` settings.
5. Run tests.
6. Resume only after root cause is understood.

## Logs and data

Local runtime files:

```text
data/superajan12.sqlite3
data/audit/events.jsonl
```

These are ignored by git.

## Never do this

- Do not commit secrets.
- Do not add live order sending without review.
- Do not bypass execution guard.
- Do not promote a model directly to approved without shadow results.
- Do not use social hype or wallet rumors as standalone edge.
