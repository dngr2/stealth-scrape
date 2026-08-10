"""Write results to CSV / JSON / JSONL."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    """Stable column order: first-seen order across all rows."""
    cols: list[str] = []
    for row in rows:
        for k in row:
            if k not in cols:
                cols.append(k)
    return cols


def to_csv(rows: list[dict[str, Any]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = _columns(rows)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def to_json(rows: Iterable[dict[str, Any]], path: str | Path, indent: int = 2) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(list(rows), indent=indent, ensure_ascii=False), encoding="utf-8"
    )
    return path


def to_jsonl(rows: Iterable[dict[str, Any]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


WRITERS = {"csv": to_csv, "json": to_json, "jsonl": to_jsonl}


def write(rows: list[dict[str, Any]], path: str | Path, fmt: str = "") -> Path:
    """Write in `fmt`, or infer it from the file extension."""
    fmt = (fmt or Path(path).suffix.lstrip(".") or "csv").lower()
    if fmt not in WRITERS:
        raise ValueError(f"unknown format {fmt!r}; expected one of {sorted(WRITERS)}")
    return WRITERS[fmt](rows, path)
