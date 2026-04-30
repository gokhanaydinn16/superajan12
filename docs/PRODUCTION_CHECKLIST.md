# SuperAjan12 Production Readiness Checklist

This checklist must be completed before any real-money adapter is added.

## 1. Runtime verification

- [ ] `superajan12 verify-endpoints` passes consistently.
- [ ] `superajan12 reference-check --symbols BTC,ETH,SOL` passes consistently.
- [ ] Scanner runs without unhandled exceptions.
- [ ] SQLite writes are stable.
- [ ] JSONL audit log is written.
- [ ] CI tests pass.
- [ ] Lint passes.

## 2. Data quality

- [ ] At least 500 markets scanned.
- [ ] At least 100 paper positions created.
- [ ] Shadow outcomes exist for a meaningful sample.
- [ ] Rejected/watch/approved distribution is understood.
- [ ] No unexplained orderbook fallback spike.
- [ ] Reference price deviations are monitored.

## 3. Strategy validation

- [ ] Strategy scores are positive across multiple windows.
- [ ] No strategy is promoted from a single lucky period.
- [ ] Drawdown is reviewed manually.
- [ ] Weak market categories are identified.
- [ ] Model version is registered as `shadow` before `approved`.

## 4. Safety controls

- [ ] Kill-switch behavior is tested.
- [ ] Safe-mode behavior is tested.
- [ ] Manual approval gate is tested.
- [ ] Execution guard blocks paper/shadow live actions.
- [ ] Capital limit engine blocks oversized requests.
- [ ] Reconciliation mismatch creates a blocking incident.

## 5. Secrets and access

- [ ] No secrets in git.
- [ ] Secrets are provided by environment or external secret manager.
- [ ] API keys have minimum permissions.
- [ ] Withdrawal permissions are disabled.
- [ ] Key rotation plan exists.

## 6. Legal and platform eligibility

- [ ] Platform access is allowed for the operator and location.
- [ ] No geographic restriction is bypassed.
- [ ] Terms of service are reviewed.
- [ ] Tax/reporting obligations are understood.

## 7. Live adapter gate

Do not add real order submission until all of the following are true:

- [ ] Production checklist complete.
- [ ] Approved model version exists.
- [ ] Manual approval is documented.
- [ ] Reconciliation is implemented against the real venue.
- [ ] A maximum first-test risk is written down.
- [ ] Dry-run order preparation has been tested.

## Current status

Not production ready for real-money trading. Ready for paper/shadow operation and data collection.
