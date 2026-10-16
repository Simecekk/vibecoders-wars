"""Area map served on `/` (maintainer-owned).

Renders the hex map of all areas from `data/territories.json`: one hexagon per area,
placed by its axial `map.q`/`map.r` coordinates, plus a leaderboard ranking players by
how many areas they have claimed. The file is read on every request, so the page
follows the game state without restarting the app.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from html import escape
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "territories.json"

HEX_SIZE = 100  # center-to-corner radius of a pointy-top hexagon, in SVG units
GAP = 4

router = APIRouter()


def load_state(path: Path = STATE_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _center(q: int, r: int) -> tuple[float, float]:
    """Axial coordinates -> pixel center (pointy-top layout)."""
    return HEX_SIZE * math.sqrt(3) * (q + r / 2), HEX_SIZE * 1.5 * r


def _corners(cx: float, cy: float, size: float) -> str:
    points = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        points.append(f"{cx + size * math.cos(angle):.1f},{cy + size * math.sin(angle):.1f}")
    return " ".join(points)


def _subtitle(territory: dict, locked: bool) -> str:
    if locked:
        return f"vlna {territory['wave']}"
    points = f"{territory['tier']} · {territory['basePoints']} b."
    status = territory["status"]
    if status == "claimed" and territory.get("owner"):
        return f"@{territory['owner']} · {points}"
    if status == "in_review":
        return f"hodnotí se · {points}"
    return f"volno · {points}"


def _tile(territory: dict, locked_waves: set[int]) -> str:
    locked = territory["status"] == "locked" or territory["wave"] in locked_waves
    cx, cy = _center(territory["map"]["q"], territory["map"]["r"])
    css = "locked" if locked else territory["status"].replace("_", "-")
    name = escape(territory["name"])
    name_class = "name long" if len(territory["name"]) > 18 else "name"
    lock = f'<text class="lock" x="{cx:.1f}" y="{cy - 40:.1f}">🔒</text>' if locked else ""
    return (
        f'<g class="tile {css}" data-area="{escape(territory["id"])}">'
        f"<title>{name} ({escape(territory['id'])})</title>"
        f'<polygon points="{_corners(cx, cy, HEX_SIZE - GAP)}"/>'
        f"{lock}"
        f'<text class="{name_class}" x="{cx:.1f}" y="{cy + 2:.1f}">{name}</text>'
        f'<text class="sub" x="{cx:.1f}" y="{cy + 30:.1f}">{escape(_subtitle(territory, locked))}</text>'
        "</g>"
    )


def leaderboard(state: dict) -> list[tuple[str, int]]:
    """(login, claimed areas) for every area owner, most areas first, ties by login."""
    counts = Counter(t["owner"] for t in state["territories"] if t["status"] == "claimed" and t.get("owner"))
    return sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))


def _leaderboard_html(state: dict) -> str:
    rows = leaderboard(state)
    if not rows:
        return '<p class="empty">Zatím nikdo nezabral žádné území.</p>'
    items = "".join(
        f'<li><span class="rank">{rank}.</span><span class="login">@{escape(login)}</span><span class="count">{count}</span></li>'
        for rank, (login, count) in enumerate(rows, start=1)
    )
    return f"<ol>{items}</ol>"


def render_map(state: dict) -> str:
    territories = state["territories"]
    locked_waves = {w["number"] for w in state.get("waves", []) if w["status"] == "locked"}
    centers = [_center(t["map"]["q"], t["map"]["r"]) for t in territories] or [(0.0, 0.0)]
    half_w = HEX_SIZE * math.sqrt(3) / 2
    min_x = min(x for x, _ in centers) - half_w - 10
    max_x = max(x for x, _ in centers) + half_w + 10
    min_y = min(y for _, y in centers) - HEX_SIZE - 10
    max_y = max(y for _, y in centers) + HEX_SIZE + 10
    tiles = "".join(_tile(t, locked_waves) for t in territories)
    view_box = f"{min_x:.1f} {min_y:.1f} {max_x - min_x:.1f} {max_y - min_y:.1f}"
    return PAGE.format(view_box=view_box, tiles=tiles, wave=state.get("currentWave", 1), leaderboard=_leaderboard_html(state))


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def area_map() -> HTMLResponse:
    return HTMLResponse(render_map(load_state()))


PAGE = """<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Války Vibecoders – mapa</title>
<style>
  body {{ margin: 0; min-height: 100vh; display: flex; flex-direction: column; align-items: center;
         gap: 16px; padding: 24px; box-sizing: border-box;
         background: radial-gradient(ellipse at top, #1d1a2e, #0b0b0f 70%); color: #e5e7eb;
         font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }}
  h1 {{ margin: 0; font-size: 1.4rem; font-weight: 600; }}
  .meta {{ color: #9ca3af; font-size: .9rem; }}
  .meta a {{ color: #93c5fd; }}
  svg {{ width: 100%; max-width: 960px; height: auto; }}
  .tile polygon {{ stroke-width: 4; stroke-linejoin: round; }}
  .tile text {{ text-anchor: middle; dominant-baseline: middle; fill: #111827; }}
  .tile .name {{ font-size: 17px; font-weight: 700; }}
  .tile .name.long {{ font-size: 12px; }}
  .tile .sub {{ font-size: 14px; }}
  .tile .lock {{ font-size: 24px; }}
  .tile.locked polygon {{ fill: #d1d5db; stroke: #9ca3af; }}
  .tile.free polygon {{ fill: #e8eefc; stroke: #2563eb; }}
  .tile.in-review polygon {{ fill: #fef3c7; stroke: #d97706; }}
  .tile.claimed polygon {{ fill: #dcfce7; stroke: #16a34a; }}
  .board {{ width: 100%; max-width: 420px; background: #16151f; border: 1px solid #2a2838; border-radius: 12px;
           padding: 16px 20px; box-sizing: border-box; }}
  .board h2 {{ margin: 0 0 10px; font-size: 1.05rem; }}
  .board ol {{ list-style: none; margin: 0; padding: 0; }}
  .board li {{ display: flex; gap: 10px; padding: 6px 0; border-top: 1px solid #2a2838; }}
  .board li:first-child {{ border-top: 0; }}
  .board .rank {{ color: #9ca3af; width: 2ch; text-align: right; }}
  .board .login {{ flex: 1; }}
  .board .count {{ font-weight: 700; font-variant-numeric: tabular-nums; }}
  .board .empty {{ margin: 0; color: #9ca3af; }}
</style>
</head>
<body>
<h1>Války Vibecoders</h1>
<div class="meta">Aktuální vlna: {wave} · <a href="/docs">API dokumentace</a></div>
<svg viewBox="{view_box}" role="img" aria-label="Mapa oblastí">{tiles}</svg>
<section class="board"><h2>Žebříček · zabraná území</h2>{leaderboard}</section>
</body>
</html>
"""
