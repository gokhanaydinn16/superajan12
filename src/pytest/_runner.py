from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
import sys
import traceback
from pathlib import Path
from tempfile import TemporaryDirectory


def main() -> int:
    root = Path.cwd() / "tests"
    quiet = "-q" in sys.argv[1:]
    failures: list[tuple[str, BaseException]] = []
    count = 0

    for path in sorted(root.glob("test_*.py")):
        module = _load_module(path)
        for name in sorted(dir(module)):
            if not name.startswith("test_"):
                continue
            candidate = getattr(module, name)
            if not callable(candidate):
                continue
            count += 1
            fixtures = _build_fixtures(candidate)
            try:
                if inspect.iscoroutinefunction(candidate):
                    asyncio.run(candidate(**fixtures))
                else:
                    candidate(**fixtures)
            except BaseException as exc:
                failures.append((f"{path.name}::{name}", exc))
                if not quiet:
                    traceback.print_exc()
            finally:
                monkeypatch = fixtures.get("monkeypatch")
                if isinstance(monkeypatch, _MonkeyPatch):
                    monkeypatch.undo()

    if failures:
        for label, exc in failures:
            print(f"FAILED {label}: {exc}")
        print(f"{len(failures)} failed, {count - len(failures)} passed")
        return 1

    print(f"{count} passed")
    return 0


def _load_module(path: Path):
    module_name = f"tests.{path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build_fixtures(func) -> dict[str, object]:
    fixtures: dict[str, object] = {}
    for name in inspect.signature(func).parameters:
        if name == "tmp_path":
            tempdir = TemporaryDirectory()
            fixtures[name] = Path(tempdir.name)
            _TEMP_DIRS.append(tempdir)
        elif name == "monkeypatch":
            fixtures[name] = _MonkeyPatch()
    return fixtures


class _MonkeyPatch:
    def __init__(self) -> None:
        self._env_changes: list[tuple[str, str | None, bool]] = []

    def setenv(self, name: str, value: str) -> None:
        existed = name in os.environ
        previous = os.environ.get(name)
        self._env_changes.append((name, previous, existed))
        os.environ[name] = value

    def undo(self) -> None:
        while self._env_changes:
            name, previous, existed = self._env_changes.pop()
            if existed:
                assert previous is not None
                os.environ[name] = previous
            else:
                os.environ.pop(name, None)


_TEMP_DIRS: list[TemporaryDirectory] = []
