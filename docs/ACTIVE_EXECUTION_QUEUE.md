# SuperAjan12 Active Execution Queue

Status: all requested workstreams have been started.

This file is the live queue for the 14-item execution wave. "Started" here means:

- a concrete artifact or code path was touched
- current blocker is identified where one exists
- next technical move is defined

## 1. Tauri native build chain

- Status: started
- Evidence:
  - `apps/desktop/src-tauri/src/main.rs`
  - `apps/desktop/src-tauri/Cargo.toml`
  - `apps/desktop/src-tauri/tauri.conf.json`
- Current state:
  - sidecar startup, health-check validation, and shutdown path are implemented
  - native build is blocked in this container because `rustc/cargo` are not installed
- Next move:
  - run `cargo check`
  - run `tauri build`
  - fix native compile/package issues in a Rust-capable environment
- New automation:
  - GitHub Actions `desktop-tauri-check` job now attempts `cargo check` in a Rust-capable runner

## 2. Desktop packaging with sidecar

- Status: started
- Evidence:
  - `apps/desktop/src-tauri/tauri.conf.json`
  - `docs/PRODUCTION_CHECKLIST.md`
- Current state:
  - packaging target exists
  - sidecar runtime path and backend startup contract are defined
- Next move:
  - wire sidecar packaging/bundling for release build
  - validate packaged app launches backend on first boot

## 3. Frontend dependency install + build

- Status: started
- Evidence:
  - `apps/desktop/package.json`
  - `apps/desktop/src/App.tsx`
  - `apps/desktop/src/api.ts`
  - `apps/desktop/src/styles.css`
- Current state:
  - desktop UI is now a multi-view command center
  - build/runtime validation is pending full npm install/build pass
- Next move:
  - run `npm install`
  - run `npm run build`
  - fix TypeScript/Vite issues if any appear
- New automation:
  - GitHub Actions `desktop-web` job now installs desktop dependencies and runs `npm run build`

## 4. Real FastAPI/Uvicorn runtime smoke test

- Status: started
- Evidence:
  - `src/superajan12/backend_server.py`
  - `src/uvicorn.py`
  - `src/fastapi/`
- Current state:
  - backend live smoke tests were run in this container
  - `/health`, `/risk/status`, `/system/health`, safety transitions were verified
  - fallback runtime exists for this constrained environment
- Next move:
  - run same smoke flow against real FastAPI/Uvicorn dependency stack
  - validate websocket stream in production-grade server runtime

## 5. Connector hardening

- Status: started
- Evidence:
  - `src/superajan12/health.py`
  - `src/superajan12/connectors/polymarket.py`
  - `src/superajan12/connectors/binance.py`
  - `src/superajan12/connectors/okx.py`
  - `src/superajan12/connectors/coinbase.py`
  - `src/superajan12/connectors/kalshi.py`
- Current state:
  - health model, source status, retries, source snapshot surface exist
  - deeper timeout, stale-data, rate-limit, circuit-breaker work remains
- Next move:
  - add per-connector stale/failure counters
  - add circuit-breaker state
  - surface rate-limit and degradation details into `/system/health`

## 6. Research provider adapters

- Status: started
- Evidence:
  - `src/superajan12/backend_api.py`
  - `docs/RESEARCH_REPORT.md`
  - `docs/source-deep-dives/ONCHAIN_WALLET_INTELLIGENCE.md`
- Current state:
  - provider readiness and not-configured states exist in API/UI
  - real ingestion adapters are not implemented yet
- Next move:
  - create source registry structure
  - add adapter contracts for research/news/social providers
  - persist research findings with audit metadata

## 7. Wallet intelligence providers

- Status: started
- Evidence:
  - `src/superajan12/agents/wallet.py`
  - `src/superajan12/backend_api.py`
  - desktop Wallet view in `apps/desktop/src/App.tsx`
- Current state:
  - provider-gated wallet surface exists
  - real provider-backed wallet flow feed is still missing
- Next move:
  - define wallet event schema
  - connect first provider or explicit mock-disabled adapter
  - log provider freshness and confidence

## 8. Market intelligence panels

- Status: started
- Evidence:
  - desktop Markets view in `apps/desktop/src/App.tsx`
  - `src/superajan12/backend_api.py`
  - `src/superajan12/health.py`
- Current state:
  - top opportunities and source health are surfaced
  - deeper panels for funding/OI/volatility/cross-market map remain
- Next move:
  - expand `/markets` payload
  - add futures/reference detail panels
  - add freshness metadata to every market row

## 9. Strategy lifecycle and model promotion

- Status: materially advanced
- Evidence:
  - `src/superajan12/model_registry.py`
  - `src/superajan12/storage.py`
  - `src/superajan12/backend_api.py`
  - `src/superajan12/cli.py`
  - `apps/desktop/src/App.tsx`
  - `tests/test_model_registry.py`
  - `tests/test_storage_model_history.py`
  - `tests/test_backend_api.py`
- Current state:
  - candidate -> shadow -> approved -> retired transition policy exists
  - promotion readiness checks are computed from latest strategy scores
  - model status history is persisted and exposed in backend/UI
  - desktop Strategy panel now shows policy checks, recent transitions and next-gate summary
  - CLI can inspect stored policy state with `model-policy`
- Next move:
  - add explicit operator-driven promotion mutation/command path instead of registration-only transitions
  - tie promotion checks to sample-size readiness from micro-live checklist
  - add audit event classes for promotion approvals and rejections

## 10. Risk model expansion

- Status: started
- Evidence:
  - `src/superajan12/capital_limits.py`
  - `src/superajan12/safety.py`
  - `src/superajan12/execution_guard.py`
  - desktop Risk view in `apps/desktop/src/App.tsx`
- Current state:
  - capital, safety, kill-switch and execution gating are active
  - leverage, funding, liquidation distance, correlation are still missing
- Next move:
  - extend risk payload model
  - add correlation/funding placeholders first
  - turn missing signals into explicit degraded risk states

## 11. Audit and observability

- Status: started
- Evidence:
  - `src/superajan12/audit.py`
  - `src/superajan12/events.py`
  - `/audit/events`
  - `/system/health`
  - desktop Audit and Health views
- Current state:
  - event history, audit log, runtime health and live feed exist
  - structured incident classes and searchable observability are not complete
- Next move:
  - enrich audit taxonomy
  - add source failure event classes
  - add filter/search/grouping plan for audit stream

## 12. Production packaging, runbook, deployment prep

- Status: started
- Evidence:
  - `docs/RUNBOOK.md`
  - `docs/PRODUCTION_CHECKLIST.md`
  - `docs/STATUS.md`
- Current state:
  - runbook and checklist exist
  - packaging/deployment execution still needs a release environment
- Next move:
  - create release checklist for desktop package
  - add operator startup/shutdown/incident steps for desktop runtime
  - split local-dev vs packaged-app run paths

## 13. Micro-live preparation checklist

- Status: started
- Evidence:
  - `src/superajan12/backend_api.py` `/execution/status`
  - `src/superajan12/approval.py`
  - `src/superajan12/reconciliation.py`
  - `src/superajan12/secrets.py`
- Current state:
  - execution status surface now shows approval, secrets, reconciliation, guard state
  - exit criteria are still intentionally unmet
- Next move:
  - track real checklist completion in persistent store
  - add operator acknowledgment flow
  - add sample-size readiness counters

## 14. Live execution adapter

- Status: started as gated design track only
- Evidence:
  - `src/superajan12/live_connector.py`
  - `src/superajan12/execution_guard.py`
  - `src/superajan12/backend_api.py` execution preview
- Current state:
  - dry-run-only order preparation exists
  - real live order submission is intentionally not implemented
- Hard rule:
  - no real order adapter work proceeds past dry-run until prior gates are complete
- Next move:
  - keep this track at design/review level only
  - do not add submission code before phases 1-13 are satisfied

## Current queue summary

- Active and code-connected now: 1, 2, 3, 4, 5, 8, 9, 10, 11, 12, 13, 14
- Active with provider/integration dependency: 6, 7
- Environment-blocked but started: 1, 2, 3
