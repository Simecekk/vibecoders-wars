"""Validate the game state `data/territories.json` against schema v2 plus the rules
the schema cannot express (unique ids and map coordinates, paths, waves, scores).

Usage: python -m scripts.validate_state [path]   (exit 0 = OK, 1 = errors)
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from scripts.common import SCHEMA_PATH, STATE_PATH, State, load_json, territory_by_id, wave_by_number


def schema_errors(state: Any, schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    out = []
    for err in sorted(validator.iter_errors(state), key=lambda e: list(map(str, e.absolute_path))):
        where = "/".join(str(p) for p in err.absolute_path) or "(root)"
        out.append(f"schema: {where}: {err.message}")
    return out


def semantic_errors(state: State) -> list[str]:
    errors: list[str] = []
    territories = state["territories"]
    tmap = territory_by_id(state)
    waves = wave_by_number(state)

    for tid, n in Counter(t["id"] for t in territories).items():
        if n > 1:
            errors.append(f"duplicate territory id '{tid}' ({n}x)")
    for (q, r), n in Counter((t["map"]["q"], t["map"]["r"]) for t in territories).items():
        if n > 1:
            errors.append(f"duplicate map coordinates q={q}, r={r}")

    for t in territories:
        for key, prefix in (("codePath", "app"), ("testsPath", "tests")):
            if t[key] != f"{prefix}/areas/{t['id']}/":
                errors.append(f"territory '{t['id']}': {key} must be '{prefix}/areas/{t['id']}/'")
        wave = waves.get(t["wave"])
        if wave is None:
            errors.append(f"territory '{t['id']}': wave {t['wave']} does not exist")
            continue
        if t["id"] not in wave["territoryIds"]:
            errors.append(f"territory '{t['id']}' is missing from territoryIds of wave {t['wave']}")
        if (t["status"] == "locked") != (wave["status"] == "locked"):
            errors.append(f"territory '{t['id']}' is {t['status']} but wave {t['wave']} is {wave['status']}")
        if t["status"] == "claimed" and t["owner"] not in {p["login"] for p in state["players"]}:
            errors.append(f"territory '{t['id']}': owner '{t['owner']}' is not a player")
        if t["status"] != "claimed" and t["owner"] is not None:
            errors.append(f"territory '{t['id']}' is {t['status']} but has an owner")

    for w in state["waves"]:
        for tid in w["territoryIds"]:
            if tid not in tmap:
                errors.append(f"wave {w['number']}: unknown territory '{tid}'")
    open_waves = [w["number"] for w in state["waves"] if w["status"] == "open"]
    if len(open_waves) > 1:
        errors.append(f"more than one open wave: {open_waves}")
    if open_waves and state["currentWave"] != open_waves[0]:
        errors.append(f"currentWave {state['currentWave']} != open wave {open_waves[0]}")

    for lid, n in Counter(e["id"] for e in state["pointsLedger"]).items():
        if n > 1:
            errors.append(f"duplicate ledger id '{lid}'")
    totals: Counter[str] = Counter()
    for e in state["pointsLedger"]:
        totals[e["player"]] += e["points"]
    logins = {p["login"] for p in state["players"]}
    for p in state["players"]:
        if "score" in p and p["score"] != totals[p["login"]]:
            errors.append(f"player '{p['login']}': score {p['score']} != ledger total {totals[p['login']]}")
    for player in totals:
        if player not in logins:
            errors.append(f"ledger references unknown player '{player}'")
    return errors


def validate(state: Any, schema: dict[str, Any] | None = None) -> list[str]:
    errors = schema_errors(state, schema if schema is not None else load_json(SCHEMA_PATH))
    return errors or semantic_errors(state)  # semantics on a broken structure make no sense


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", default=str(STATE_PATH))
    args = ap.parse_args(argv)
    errors = validate(load_json(Path(args.path)))
    for e in errors:
        print(f"ERROR: {e}", file=sys.stderr)
    if not errors:
        print(f"OK: {args.path} is valid")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
