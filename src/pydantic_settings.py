from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def SettingsConfigDict(**kwargs: Any) -> dict[str, Any]:
    return dict(kwargs)


class BaseSettings(BaseModel):
    model_config: dict[str, Any] = {}

    def __init__(self, **data: Any) -> None:
        model_config = getattr(self.__class__, "model_config", {}) or {}
        merged = {}
        env_values = _read_env_file(model_config.get("env_file"))
        for name, field in self.__class__.model_fields.items():
            if name in data:
                continue
            alias = getattr(field, "validation_alias", None)
            if isinstance(alias, str):
                env_name = alias
            else:
                env_name = None
            if env_name and env_name in os.environ:
                merged[name] = os.environ[env_name]
            elif env_name and env_name in env_values:
                merged[name] = env_values[env_name]
        merged.update(data)
        super().__init__(**merged)


def _read_env_file(path_value: Any) -> dict[str, str]:
    if not path_value:
        return {}
    path = Path(str(path_value))
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
