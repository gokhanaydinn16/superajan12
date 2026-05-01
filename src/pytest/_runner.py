from __future__ import annotations

import asyncio
import importlib.util
import inspect
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
            try:
                if inspect.iscoroutinefunction(candidate):
                    asyncio.run(candidate(**_build_fixtures(candidate)))
                else:
                    candidate(**_build_fixtures(candidate))
            except BaseException as exc:
                failures.append((f"{path.name}::{name}", exc))
                if not quiet:
                    traceback.print_exc()

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
    return fixtures


_TEMP_DIRS: list[TemporaryDirectory] = []
