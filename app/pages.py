"""HTML pages served on `/` and `/rules` (maintainer-owned).

`/` shows the hex map of all areas from `data/territories.json` (one hexagon per area,
placed by its axial `map.q`/`map.r` coordinates), the leaderboard and the rules.
`/rules` shows the rules alone. Both files are read on every request, so the pages
follow the game state and RULES.md without restarting the app.
"""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path

import markdown
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "data" / "territories.json"
RULES_FILE = ROOT / "RULES.md"

HEX_SIZE = 100  # center-to-corner radius of a pointy-top hexagon, in SVG units
GAP = 4

OWNED = {"owned", "claimed"}  # "claimed" is the pre-RULES.md name of "owned"
CONTESTED = {"contested", "in_review"}

router = APIRouter()


def load_state(path: Path = STATE_FILE) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_rules(path: Path = RULES_FILE) -> str:
    """The player-facing part of RULES.md (everything before the bot/CI appendix), as HTML."""
    player_rules = path.read_text(encoding="utf-8").split("\n---\n", 1)[0]
    return markdown.markdown(player_rules, extensions=["tables"], tab_length=2)  # RULES.md nests lists by 2 spaces


def _center(q: int, r: int) -> tuple[float, float]:
    """Axial coordinates -> pixel center (pointy-top layout)."""
    return HEX_SIZE * math.sqrt(3) * (q + r / 2), HEX_SIZE * 1.5 * r


def _corners(cx: float, cy: float, size: float) -> str:
    points = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        points.append(f"{cx + size * math.cos(angle):.1f},{cy + size * math.sin(angle):.1f}")
    return " ".join(points)


def _state_of(territory: dict) -> str:
    """owned / contested / free. Every area is open (RULES.md), so old `locked` areas count as free."""
    if territory["status"] in OWNED and territory.get("owner"):
        return "owned"
    if territory["status"] in CONTESTED:
        return "contested"
    return "free"


def _tile(territory: dict) -> str:
    state = _state_of(territory)
    subtitle = f"@{territory['owner']}" if state == "owned" else state
    cx, cy = _center(territory["map"]["q"], territory["map"]["r"])
    name = escape(territory["name"])
    name_class = "name long" if len(territory["name"]) > 18 else "name"
    return (
        f'<g class="tile {state}" data-area="{escape(territory["id"])}">'
        f"<title>{name} ({escape(territory['id'])})</title>"
        f'<polygon points="{_corners(cx, cy, HEX_SIZE - GAP)}"/>'
        f'<text class="{name_class}" x="{cx:.1f}" y="{cy - 6:.1f}">{name}</text>'
        f'<text class="sub" x="{cx:.1f}" y="{cy + 24:.1f}">{escape(subtitle)}</text>'
        "</g>"
    )


def leaderboard(state: dict) -> list[tuple[str, int]]:
    """(login, areas owned) for every owner, most areas first.

    Ties go to the player who reached that count first, approximated by the latest
    `claimedAt` among their areas (earlier ranks higher), then by login.
    """
    areas: dict[str, list[str]] = {}
    for territory in state["territories"]:
        if territory.get("status") != "removed" and _state_of(territory) == "owned":
            areas.setdefault(territory["owner"], []).append(territory.get("claimedAt") or "")
    return [
        (login, len(times))
        for login, times in sorted(areas.items(), key=lambda item: (-len(item[1]), max(item[1]), item[0].lower()))
    ]


def _leaderboard_html(state: dict) -> str:
    rows = leaderboard(state)
    if not rows:
        return '<p class="empty">Nobody owns an area yet.</p>'
    items = "".join(
        f'<li><span class="rank">{rank}.</span><span class="login">@{escape(login)}</span><span class="count">{count}</span></li>'
        for rank, (login, count) in enumerate(rows, start=1)
    )
    return f"<ol>{items}</ol>"


def _map_svg(state: dict) -> str:
    territories = [t for t in state["territories"] if t.get("status") != "removed"]
    centers = [_center(t["map"]["q"], t["map"]["r"]) for t in territories] or [(0.0, 0.0)]
    half_w = HEX_SIZE * math.sqrt(3) / 2
    min_x = min(x for x, _ in centers) - half_w - 10
    max_x = max(x for x, _ in centers) + half_w + 10
    min_y = min(y for _, y in centers) - HEX_SIZE - 10
    max_y = max(y for _, y in centers) + HEX_SIZE + 10
    view_box = f"{min_x:.1f} {min_y:.1f} {max_x - min_x:.1f} {max_y - min_y:.1f}"
    tiles = "".join(_tile(t) for t in territories)
    return f'<svg class="map" viewBox="{view_box}" role="img" aria-label="Area map">{tiles}</svg>'


def render_home(state: dict, rules_html: str) -> str:
    body = (
        _map_svg(state) + '<div class="columns">'
        f'<section class="card board"><h2>Leaderboard · areas owned</h2>{_leaderboard_html(state)}</section>'
        f'<section class="card rules">{rules_html}</section>'
        "</div>"
    )
    return PAGE.format(title="Vibecoders Wars", body=body)


def render_rules(rules_html: str) -> str:
    return PAGE.format(title="Rules · Vibecoders Wars", body=f'<section class="card rules page">{rules_html}</section>')


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def home() -> HTMLResponse:
    return HTMLResponse(render_home(load_state(), load_rules()))


@router.get("/rules", response_class=HTMLResponse, include_in_schema=False)
def rules() -> HTMLResponse:
    return HTMLResponse(render_rules(load_rules()))


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ margin: 0; min-height: 100vh; display: flex; flex-direction: column; align-items: center;
         gap: 20px; padding: 24px 16px; box-sizing: border-box;
         background: radial-gradient(ellipse at top, #1d1a2e, #0b0b0f 70%) fixed; color: #e5e7eb;
         font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height: 1.5; }}
  header {{ display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 8px 20px; }}
  header h1 {{ margin: 0; font-size: 1.4rem; font-weight: 600; }}
  header h1 a {{ color: inherit; text-decoration: none; }}
  nav {{ display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }}
  nav a {{ color: #e5e7eb; text-decoration: none; font-size: .95rem; padding: 6px 14px; border-radius: 999px;
          background: #1f1d2c; border: 1px solid #34314a; }}
  nav a:hover {{ background: #2563eb; border-color: #2563eb; }}
  .map {{ width: 100%; max-width: 960px; height: auto; }}
  .tile polygon {{ stroke-width: 4; stroke-linejoin: round; }}
  .tile text {{ text-anchor: middle; dominant-baseline: middle; fill: #111827; }}
  .tile .name {{ font-size: 17px; font-weight: 700; }}
  .tile .name.long {{ font-size: 12px; }}
  .tile .sub {{ font-size: 14px; }}
  .tile.free polygon {{ fill: #e8eefc; stroke: #2563eb; }}
  .tile.contested polygon {{ fill: #fef3c7; stroke: #d97706; }}
  .tile.owned polygon {{ fill: #dcfce7; stroke: #16a34a; }}
  .columns {{ width: 100%; max-width: 960px; display: flex; flex-wrap: wrap; gap: 20px; align-items: flex-start; }}
  .card {{ background: #16151f; border: 1px solid #2a2838; border-radius: 12px; padding: 16px 20px;
          box-sizing: border-box; min-width: 0; }}
  .board {{ flex: 1 1 260px; }}
  .rules {{ flex: 3 1 420px; }}
  .rules.page {{ width: 100%; max-width: 820px; }}
  .board h2 {{ margin: 0 0 10px; font-size: 1.05rem; }}
  .board ol {{ list-style: none; margin: 0; padding: 0; }}
  .board li {{ display: flex; gap: 10px; padding: 6px 0; border-top: 1px solid #2a2838; }}
  .board li:first-child {{ border-top: 0; }}
  .board .rank {{ color: #9ca3af; width: 2ch; text-align: right; }}
  .board .login {{ flex: 1; }}
  .board .count {{ font-weight: 700; font-variant-numeric: tabular-nums; }}
  .board .empty {{ margin: 0; color: #9ca3af; }}
  .rules h1 {{ font-size: 1.3rem; margin: 0 0 8px; }}
  .rules h2 {{ font-size: 1.05rem; margin: 20px 0 6px; }}
  .rules blockquote {{ margin: 0; color: #9ca3af; }}
  .rules code {{ background: #262436; padding: 1px 5px; border-radius: 4px; font-size: .9em; }}
  .rules a {{ color: #93c5fd; }}
  .rules table {{ border-collapse: collapse; display: block; overflow-x: auto; font-size: .9rem; }}
  .rules th, .rules td {{ border: 1px solid #2a2838; padding: 4px 8px; text-align: left; }}
</style>
</head>
<body>
<header>
  <h1><a href="/">Vibecoders Wars</a></h1>
  <nav><a href="/">Map</a><a href="/rules">Rules</a><a href="/docs">API docs</a><a href="https://github.com/Simecekk/vibecoders-wars">GitHub</a></nav>
</header>
{body}
</body>
</html>
"""
