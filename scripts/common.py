"""Shared helpers for the Vibecoders Wars scripts."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

State = dict[str, Any]

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "data" / "territories.json"
SCHEMA_PATH = ROOT / "schema" / "schema.json"

REPO = "Simecekk/vibecoders-wars"
MAINTAINER = "Simecekk"
TIER_POINTS: dict[str, int] = {"S": 10, "M": 25, "L": 50}
TITLE_RE = re.compile(r"^\[([a-z0-9-]+)\]")

LABEL_INVALID = "vv:invalid"
LABEL_LOST = "vv:lost"
LABEL_BLOCKED = "vv:blocked"
LABEL_FIX = "vv:fix"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def dumps(state: State) -> str:
    return json.dumps(state, ensure_ascii=False, indent=2) + "\n"


def dump_state(state: State, path: Path) -> None:
    path.write_text(dumps(state), encoding="utf-8")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fmt_ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def area_from_title(title: str) -> str | None:
    m = TITLE_RE.match(title or "")
    return m.group(1) if m else None


def territory_by_id(state: State) -> dict[str, dict[str, Any]]:
    return {t["id"]: t for t in state["territories"]}


def wave_by_number(state: State) -> dict[int, dict[str, Any]]:
    return {w["number"]: w for w in state["waves"]}
