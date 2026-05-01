from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, get_args, get_origin


AnyHttpUrl = str


@dataclass
class _FieldInfo:
    default: Any = ...
    default_factory: Any = None
    validation_alias: str | None = None

    def get_default(self) -> Any:
        if self.default_factory is not None:
            return self.default_factory()
        if self.default is ...:
            return ...
        return deepcopy(self.default)


def Field(
    default: Any = ...,
    *,
    default_factory: Any = None,
    validation_alias: str | None = None,
    **_: Any,
) -> _FieldInfo:
    return _FieldInfo(
        default=default,
        default_factory=default_factory,
        validation_alias=validation_alias,
    )


class BaseModel:
    model_fields: dict[str, _FieldInfo] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        annotations: dict[str, Any] = {}
        for base in reversed(cls.__mro__[1:]):
            annotations.update(getattr(base, "__annotations__", {}))
        annotations.update(getattr(cls, "__annotations__", {}))

        fields: dict[str, _FieldInfo] = {}
        for base in reversed(cls.__mro__[1:]):
            fields.update(getattr(base, "model_fields", {}))

        for name in annotations:
            if name == "model_fields":
                continue
            raw_default = getattr(cls, name, ...)
            if isinstance(raw_default, _FieldInfo):
                info = raw_default
            else:
                info = _FieldInfo(default=raw_default)
            fields[name] = info
        cls.model_fields = fields

    def __init__(self, **data: Any) -> None:
        annotations = self._model_annotations()
        for name, info in self.model_fields.items():
            if name in data:
                value = data[name]
            else:
                value = info.get_default()
                if value is ...:
                    raise TypeError(f"Missing required field: {name}")
            annotation = annotations.get(name, Any)
            setattr(self, name, _coerce_value(value, annotation))

    @classmethod
    def _model_annotations(cls) -> dict[str, Any]:
        annotations: dict[str, Any] = {}
        for base in reversed(cls.__mro__):
            annotations.update(getattr(base, "__annotations__", {}))
        return annotations

    def model_dump(self, mode: str | None = None) -> dict[str, Any]:
        return {
            name: _serialize_value(getattr(self, name), mode=mode)
            for name in self.model_fields
        }


def _coerce_value(value: Any, annotation: Any) -> Any:
    if value is None:
        return None

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is list and args:
        inner = args[0]
        return [_coerce_value(item, inner) for item in value]

    if origin is dict and len(args) == 2:
        key_type, value_type = args
        return {
            _coerce_value(key, key_type): _coerce_value(item, value_type)
            for key, item in value.items()
        }

    if origin is tuple and args:
        inner = args[0]
        return tuple(_coerce_value(item, inner) for item in value)

    if origin is not None and type(None) in args:
        non_none = next((arg for arg in args if arg is not type(None)), Any)
        return _coerce_value(value, non_none)

    if isinstance(annotation, type):
        if issubclass(annotation, BaseModel):
            if isinstance(value, annotation):
                return value
            if isinstance(value, dict):
                return annotation(**value)
        if issubclass(annotation, Enum):
            if isinstance(value, annotation):
                return value
            return annotation(value)
        if annotation is Path:
            return Path(value)
        if annotation is datetime and isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        if annotation is date and isinstance(value, str):
            return date.fromisoformat(value)
        if annotation in {str, int, float, bool} and not isinstance(value, annotation):
            return annotation(value)

    return value


def _serialize_value(value: Any, mode: str | None = None) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode=mode)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_value(item, mode=mode) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item, mode=mode) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item, mode=mode) for key, item in value.items()}
    return value
