# SuperAjan12 Master Roadmap

Status: Master Plan v1

This roadmap is the persistent project memory for the serious build direction. The system target is not a simple web dashboard or a simple bot. The target is a desktop command-center application that operates like a research/trading firm using real data, paper/shadow validation, strict risk gates, and only later controlled live capability.

## Phase 0 - Research foundation

Goal: avoid blind coding and make sure the system is designed from real-world data, platform constraints and operational risks.

Deliverables:

- [x] Research report v1.
- [x] Platform/API source map.
- [x] Core product principles.
- [x] Desktop-first technical direction.
- [ ] Source-by-source deep dive documents.
- [ ] API limit and cost matrix.
- [ ] Legal/platform access checklist by venue.

Exit criteria:

- Research report exists.
- MVP scope is clear.
- No fake production data policy is documented.

## Phase 1 - Desktop Command Center architecture

Goal: replace the simple local web dashboard with a serious desktop app architecture.

Target architecture:

```text
Tauri Desktop App
-> Python backend sidecar
-> Local API + local event stream
-> Real connector workers
-> SQLite first, optional PostgreSQL/TimescaleDB later
-> Audit log
```

Deliverables:

- [ ] `apps/desktop/` Tauri shell.
- [ ] Python sidecar launch plan.
- [ ] Local API contract.
- [ ] Desktop navigation: Command Center, Research Center, Market Intelligence, Wallet Intelligence, Strategy Lab, Risk Center, Paper/Shadow, Audit Log, System Health.
- [ ] No fake data UI states: no data, offline, stale, not configured.

Exit criteria:

- Desktop app opens as a standalone local application.
- Backend sidecar starts/stops with app.
- UI does not freeze when backend source fails.

## Phase 2 - Real data connector hardening

Goal: make data ingestion serious, observable and reliable.

Deliverables:

- [ ] Polymarket Gamma/Data/CLOB read connector hardening.
- [ ] Kalshi public market connector hardening.
- [ ] Binance futures market data connector hardening.
- [ ] OKX public market data connector hardening.
- [ ] Coinbase spot/reference connector hardening.
- [ ] Connector health model.
- [ ] Stale data detection.
- [ ] Retry/timeout/circuit breaker policy.
- [ ] Rate-limit tracking.
- [ ] Source status UI.

Exit criteria:

- All configured real sources show online/offline/stale state.
- Failures do not crash UI.
- No production mock rows.

## Phase 3 - Research Center

Goal: build a research/intelligence workflow, not direct trading from raw headlines.

Deliverables:

- [ ] Source registry.
- [ ] Research task queue.
- [ ] Event detection model.
- [ ] Source credibility scoring.
- [ ] News deduplication.
- [ ] Timestamp normalization.
- [ ] Event-to-market mapping.
- [ ] Research notes and audit trail.

Initial source policy:

- Official sources first.
- Social media is discovery only.
- News requires cross-source confirmation.
- Unverified event can only create WATCH/research tasks.

Exit criteria:

- Research Center shows real configured sources or explicit not-configured state.
- Research findings are logged with source and timestamp.

## Phase 4 - Market Intelligence

Goal: build a live market operating view across prediction markets and futures.

Deliverables:

- [ ] Multi-venue market board.
- [ ] Funding, OI, spread, orderbook, volatility panels.
- [ ] Cross-market comparison between Polymarket/Kalshi and futures venues.
- [ ] Event probability vs futures movement view.
- [ ] Opportunity map v1.

Exit criteria:

- Market Intelligence uses live source data.
- Each number has source and freshness metadata.

## Phase 5 - Wallet / On-chain Intelligence

Goal: add smart-wallet data only if real source is configured.

Deliverables:

- [ ] Provider decision: Nansen, Dune, Glassnode, Arkham or custom indexer.
- [ ] API key/not-configured states.
- [ ] Wallet flow feed.
- [ ] Whale/smart-money alert panel.
- [ ] Research-only signal policy.

Exit criteria:

- No fake wallet movements.
- Wallet signal cannot directly trigger live execution.

## Phase 6 - Strategy Lab

Goal: make strategies measurable, versioned and safely promoted.

Deliverables:

- [ ] Strategy idea registry.
- [ ] Paper test runner.
- [ ] Shadow test runner.
- [ ] Strategy score dashboard.
- [ ] Model version registry UI.
- [ ] Promotion policy: candidate -> shadow -> approved -> retired.
- [ ] Reject/retire bad strategies.

Exit criteria:

- Strategies are measured from paper/shadow outcomes.
- No strategy can self-promote to live.

## Phase 7 - Risk Command Center

Goal: make capital protection the strongest part of the system.

Deliverables:

- [ ] Max daily loss.
- [ ] Max single trade risk.
- [ ] Max total open risk.
- [ ] Max leverage.
- [ ] Liquidation distance model.
- [ ] Funding risk model.
- [ ] Correlation and asset exposure model.
- [ ] Safe mode.
- [ ] Kill switch.
- [ ] Reconciliation block.
- [ ] Risk explanation UI.

Exit criteria:

- Risk Engine can block every action.
- UI shows why an action was blocked.

## Phase 8 - Paper and Shadow operation

Goal: prove system quality before any real capital.

Deliverables:

- [ ] Paper position engine hardening.
- [ ] Automated shadow marking from latest prices.
- [ ] Shadow PnL dashboard.
- [ ] Strategy score from outcomes.
- [ ] Category-level performance.
- [ ] Source-failure impact tracking.

Exit criteria before micro-live discussion:

- 500+ scanned markets.
- 100+ paper positions.
- Meaningful shadow outcomes.
- Positive strategy score across multiple periods.
- Endpoint failures understood.

## Phase 9 - Controlled micro-live preparation

Goal: prepare but not rush real-money operation.

Deliverables:

- [ ] Secret manager decision.
- [ ] Venue access and eligibility review.
- [ ] API key scope policy.
- [ ] Manual approval gate UI.
- [ ] Execution guard integration.
- [ ] Capital limit enforcement.
- [ ] Dry-run order pipeline.
- [ ] Real reconciliation design.

Exit criteria:

- Production checklist complete.
- Approved model exists.
- Manual approval process tested.
- Reconciliation tested.
- Live adapter reviewed separately.

## Phase 10 - Live execution adapter, later only

Goal: only after evidence and checklist completion.

Deliverables:

- [ ] Venue-specific order adapter.
- [ ] Reduce-only and cancel-all controls.
- [ ] Partial-fill handling.
- [ ] Order stale cleanup.
- [ ] Post-trade reconciliation.
- [ ] Emergency kill switch.

Hard rule:

No live order sending until previous phases are complete and manually approved.

## Immediate next build order

1. Keep `docs/RESEARCH_REPORT.md` as source of truth.
2. Create source deep-dive docs for Polymarket, Kalshi, Binance, OKX, Coinbase, Nansen/Dune/Glassnode.
3. Create desktop app architecture document.
4. Start `apps/desktop/` Tauri shell.
5. Convert current FastAPI dashboard into backend sidecar API.
6. Build serious desktop UI navigation and no-fake-data states.
7. Harden connectors and health model.
8. Build Research Center v1.
9. Build Market Intelligence v1.
10. Build Strategy/Risk/Paper-Shadow dashboards.

## Current warning

The existing simple web dashboard is a prototype only. It is not the final product. It should either be retired or used as a backend/API test view after the desktop app begins.
