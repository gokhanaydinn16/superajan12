# SuperAjan12 Release Guide

## Purpose

This document defines how SuperAjan12 is versioned, packaged, and released.

## Version policy

SuperAjan12 uses one aligned semantic version across these surfaces:

- Python package in `pyproject.toml`
- Desktop web shell in `apps/desktop/package.json`
- Tauri desktop shell in `apps/desktop/src-tauri/tauri.conf.json`
- Desktop Cargo package in `apps/desktop/src-tauri/Cargo.toml`
- Git tag in the form `vX.Y.Z`

Version bumps should be applied to all four surfaces in the same change.

## Release source of truth

`CHANGELOG.md` is the release-notes source of truth.

Required release-entry rules:

1. Add a new heading for the target version before tagging.
2. Summarize changes under clear sections such as `Added`, `Changed`, `Fixed`, and `Notes`.
3. Keep the notes user-facing and operationally meaningful.

## CI expectations

The repository keeps separate validation lanes for:

- installed dependency mode
- repository runtime-compat mode
- desktop web build
- desktop Tauri cargo check

A release should not be cut while any required lane is red.

## Desktop packaging expectation

Desktop bundle generation is intentionally disabled today.

Current policy:

- CI may build the desktop web app and run Tauri cargo checks.
- CI does not promise signed or shippable desktop bundles yet.
- Release candidates may include Python artifacts and desktop web artifacts.
- Full desktop bundling can be enabled only after stable icon assets and release-grade packaging inputs are committed.

## Release workflow

Primary path:

1. Update versions across Python and desktop surfaces.
2. Add the new release section to `CHANGELOG.md`.
3. Ensure CI is green.
4. Create tag `vX.Y.Z` and push it, or run the manual workflow with `release_version`.
5. Review generated GitHub release artifacts.

The release workflow currently produces:

- Python sdist and wheel
- desktop web `dist/` artifact

## Manual release checklist

- Version is aligned everywhere.
- `CHANGELOG.md` contains the release notes.
- `README.md`, `docs/STATUS.md`, and `docs/HANDOFF.md` reflect any changed expectations.
- CI is green on the release commit.
- Desktop bundling expectation is still accurate.
- Tag matches the aligned version.

## Non-goals for the current release path

- automatic PyPI publish
- automatic signed desktop bundles
- turning on live trading
