# SuperAjan12 Handoff

## Project state

SuperAjan12 is ready for paper/shadow operation. It is not a live trading bot and does not submit real orders. The backend and tests can run through a constrained-runtime compatibility path when external package installation is unavailable, and the repository now has a documented release path for Python and desktop-web artifacts.

## Completed layers

1. Public market data connectors.
2. Polymarket scanner.
3. Risk engine.
4. Resolution agent.
5. Probability baseline.
6. Liquidity agent.
7. Manipulation risk agent.
8. News reliability agent.
9. Social signal agent.
10. Smart wallet placeholder.
11. Crypto reference checks.
12. Cross-market matching.
13. Paper positions.
14. Shadow mark-to-market.
15. Strategy scoring.
16. Model version registry.
17. SQLite persistence.
18. JSONL audit log.
19. Reconciliation scaffold.
20. Manual approval gate.
21. Secret manager scaffold.
22. Capital limit engine.
23. Execution guard.
24. Dry-run live connector.
25. CLI operations.
26. Tests, CI and runtime-compat validation.
27. Runbook and production checklist.
28. Desktop/backend constrained-runtime fallback path.
29. Release workflow, changelog, and versioning policy.

## Main commands

```bash
superajan12 init-db
superajan12 verify-endpoints
superajan12 reference-check --symbols BTC,ETH,SOL
superajan12 scan --limit 25
superajan12 report
superajan12 shadow-report
superajan12 strategy-score --name baseline --pnl 1.2,-0.5,0.8 --save
superajan12 strategy-list --limit 10
superajan12 model-register --name probability --version 0.2.0 --status candidate --notes baseline
superajan12 model-list --limit 20
superajan12 reconcile --local 0 --external 0
superajan12 capital-check --requested-risk 5 --open-risk 10 --daily-pnl -1
superajan12 execution-check --mode paper
```

Fallback validation commands when package/toolchain setup is blocked:

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m superajan12.backend_server --host 127.0.0.1 --port 8000
```

## Safety position

The project intentionally stops before real order submission. The dry-run live connector only prepares order-shaped data after an execution guard decision. It does not call a trading endpoint.

## Before any live work

Follow `docs/PRODUCTION_CHECKLIST.md`, `docs/RUNBOOK.md`, and `docs/RELEASE.md`.

Minimum required evidence before live adapter development:

- 500+ scanned markets.
- 100+ paper positions.
- Shadow outcome history.
- Positive strategy scores across multiple market periods.
- Approved model version.
- Stable endpoint verification.
- Stable reference price verification.
- Reconciliation design against the actual venue.
- Manual approval process.
- Secrets stored outside git.

## Next engineering tasks

1. Run the system locally and collect paper/shadow data.
2. Replace top-level compatibility shims with an explicit compat namespace.
3. Restore desktop packaging in an environment with npm registry access and Rust tooling.
4. Inspect real Polymarket token id behavior across many markets.
5. Add automated shadow marking from latest market price.
6. Add category-level performance reports.
7. Add model promotion policy enforcement in CLI.
8. Add real on-chain data connector only after source selection.
9. Add real social data connector only after rate limits and source quality are defined.
10. Keep live order sending disabled until production checklist is complete.

## Handoff conclusion

The paper/shadow core is ready for local validation and controlled release artifact generation. Desktop bundling and explicit compat-namespace migration are the main remaining structural follow-ups.
