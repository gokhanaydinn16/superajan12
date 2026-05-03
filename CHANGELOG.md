# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this repository follows semantic versioning for the Python package, desktop shell, and release tags.

## [0.2.0] - 2026-05-03

### Added
- A documented release process with version policy, artifact expectations, and operator checklist.
- A GitHub release workflow that builds Python artifacts and desktop web artifacts on tags or manual dispatch.
- A draft-PR fallback procedure for connector-side ready-for-review failures.
- An explicit changelog file as the release-notes source of truth.

### Changed
- Unified the package, desktop shell, and Tauri app version at `0.2.0`.
- Split CI into two explicit Python lanes: installed dependencies and repository runtime-compat mode.
- Tightened the installed-dependency lane so it fails if repository shim modules leak into the test environment.

### Notes
- Desktop bundle generation remains intentionally disabled in CI until versioned packaging assets and release-grade desktop inputs are committed.

## [0.1.0] - 2026-05-01

### Added
- Shared runtime helpers make CLI, backend, and web scan persistence and audit trails consistent.
- Desktop/Tauri icon fallback and shutdown cleanup work in CI without manual assets.
- Reporting, safety, and storage tests expanded to surface regressions early.

### Fixed
- Dashboard now biases toward the latest scan results, and model registry upserts keep row identity.
- Safety kill-switch and safe-mode handling are deterministic, and scan/audit records are centralized.

### Notes
- CI run `#178` on commit `2104620f6be0e38b16984b79b8b1363f144929e4` completed successfully.
- The release process still needed version bumps, publishing automation, and desktop bundle tooling before this hardening pass.
