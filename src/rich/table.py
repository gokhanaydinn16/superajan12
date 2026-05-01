from __future__ import annotations


class Table:
    def __init__(self, title: str | None = None) -> None:
        self.title = title
        self.columns: list[str] = []
        self.rows: list[tuple[str, ...]] = []

    def add_column(self, name: str, **kwargs) -> None:
        self.columns.append(name)

    def add_row(self, *values: str) -> None:
        self.rows.append(tuple(values))

    def __str__(self) -> str:
        lines = [self.title] if self.title else []
        if self.columns:
            lines.append(" | ".join(self.columns))
        for row in self.rows:
            lines.append(" | ".join(row))
        return "\n".join(lines)
