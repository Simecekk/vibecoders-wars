"""Daily evaluation (cron at 20:00 Europe/Prague).

Usage:
  python -m scripts.evaluate                    # full run: fixes, then voting
  python -m scripts.evaluate --check-hour       # exit 0 only if it is 20:xx in Prague (used by the workflow)
  python -m scripts.evaluate --penalty LOGIN AREA --note "why"   # maintainer veto for cheating

Steps (all idempotent, state is validated before it is written):
1. `vv:fix` PRs: merge when CI is green and the area owner or the maintainer approved.
   Ownership does not change; the fix author gets +1 participation (once per area).
2. Voting PRs: validity limits, votes (👍 = 1, approve = 2), winner per area,
   merge + claim, `vv:lost` + close for the others, participation, `first-pr` badge,
   area status, waves.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from scripts.common import (
    LABEL_BLOCKED,
    LABEL_FIX,
    LABEL_INVALID,
    LABEL_LOST,
    MAINTAINER,
    REPO,
    STATE_PATH,
    State,
    area_from_title,
    dump_state,
    fmt_ts,
    is_fix_title,
    load_json,
    parse_ts,
    territory_by_id,
    wave_by_number,
)

PRAGUE = ZoneInfo("Europe/Prague")
MIN_ACCOUNT_AGE = timedelta(days=30)


class GitHub(Protocol):
    def open_pulls(self) -> list[dict[str, Any]]: ...
    def ci_status(self, sha: str) -> str: ...  # pending | success | failure
    def reactions(self, number: int) -> list[dict[str, Any]]: ...
    def reviews(self, number: int) -> list[dict[str, Any]]: ...
    def user(self, login: str) -> dict[str, Any]: ...
    def merge(self, number: int, title: str) -> None: ...
    def add_labels(self, number: int, labels: list[str]) -> None: ...
    def comment(self, number: int, body: str) -> None: ...
    def close(self, number: int) -> None: ...
    def request_reviewer(self, number: int, login: str) -> None: ...


@dataclass
class Pr:
    number: int
    title: str
    author: str
    author_type: str
    created_at: str
    head_sha: str
    url: str
    labels: list[str]
    area: str | None
    ci: str = "pending"
    validity: str = "valid"
    reasons: list[str] | None = None

    @property
    def is_fix(self) -> bool:
        return is_fix_title(self.title)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Pr:
        return cls(
            number=raw["number"],
            title=raw["title"],
            author=raw["user"]["login"],
            author_type=raw["user"].get("type", "User"),
            created_at=raw["created_at"],
            head_sha=raw["head"]["sha"],
            url=raw["html_url"],
            labels=[lb["name"] for lb in raw["labels"]],
            area=area_from_title(raw["title"]),
        )


def is_evaluation_hour(now: datetime) -> bool:
    return now.astimezone(PRAGUE).hour == 20


# --------------------------------------------------------------------------- state helpers


def _player(state: State, gh: GitHub, login: str, now: str) -> dict[str, Any]:
    for p in state["players"]:
        if p["login"] == login:
            return p
    u = gh.user(login)
    p = {
        "login": login,
        "githubId": u["id"],
        "avatarUrl": u["avatar_url"],
        "status": "active",
        "joinedAt": now,
        "score": 0,
        "badges": [],
    }
    state["players"].append(p)
    return p


def _ledger(state: State, entry: dict[str, Any]) -> bool:
    """Append a ledger entry unless one with the same id exists. Returns True if added."""
    if any(e["id"] == entry["id"] for e in state["pointsLedger"]):
        return False
    state["pointsLedger"].append(entry)
    return True


def _participation(state: State, gh: GitHub, login: str, area: str, pr: int, now: str, note: str | None = None) -> None:
    _player(state, gh, login, now)
    entry = {
        "id": f"participation:{login}:{area}",
        "player": login,
        "points": 1,
        "reason": "participation",
        "territoryId": area,
        "pr": pr,
        "at": now,
    }
    if note:
        entry["note"] = note
    _ledger(state, entry)


def _first_pr_badge(state: State, gh: GitHub, pr: Pr, now: str) -> None:
    p = _player(state, gh, pr.author, now)
    if not any(b["id"] == "first-pr" for b in p["badges"]):
        p["badges"].append({"id": "first-pr", "awardedAt": now, "pr": pr.number})


def _record_pr(game: State, pr: Pr, **extra: Any) -> dict[str, Any]:
    rec = next((r for r in game["pullRequests"] if r["number"] == pr.number), None)
    if rec is None:
        rec = {"number": pr.number}
        game["pullRequests"].append(rec)
    rec.update(
        {
            "url": pr.url,
            "title": pr.title,
            "author": pr.author,
            "territoryId": pr.area,
            "state": "open",
            "createdAt": pr.created_at,
            "headSha": pr.head_sha,
            "ciStatus": pr.ci,
            "validity": pr.validity,
            "labels": sorted(set(pr.labels)),
        }
    )
    if pr.reasons:
        rec["invalidReasons"] = pr.reasons
    rec.update(extra)
    return rec


def _recompute_scores(state: State) -> None:
    for p in state["players"]:
        p["score"] = sum(e["points"] for e in state["pointsLedger"] if e["player"] == p["login"])


def _label(gh: GitHub, pr: Pr, label: str) -> None:
    if label not in pr.labels:
        gh.add_labels(pr.number, [label])
        pr.labels.append(label)


# --------------------------------------------------------------------------- votes


def _account_old_enough(gh: GitHub, login: str, at: datetime, cache: dict[str, bool]) -> bool:
    if login not in cache:
        cache[login] = parse_ts(gh.user(login)["created_at"]) < at - MIN_ACCOUNT_AGE
    return cache[login]


def collect_votes(gh: GitHub, prs: list[Pr], now: datetime, age_cache: dict[str, bool]) -> dict[int, list[dict[str, Any]]]:
    """Votes for candidate PRs of ONE area, with counted/reason per vote."""
    raw: list[tuple[datetime, int, str, str, str]] = []  # (at, pr, voter, voter_type, vote type)
    for pr in prs:
        for r in gh.reactions(pr.number):
            if r.get("content", "+1") == "+1" and parse_ts(r["created_at"]) <= now:
                raw.append((parse_ts(r["created_at"]), pr.number, r["user"]["login"], r["user"].get("type", "User"), "thumbs_up"))
        latest: dict[str, dict[str, Any]] = {}
        for rv in sorted(gh.reviews(pr.number), key=lambda x: x["submitted_at"]):
            if parse_ts(rv["submitted_at"]) <= now and rv["state"] in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
                latest[rv["user"]["login"]] = rv
        for login, rv in latest.items():
            if rv["state"] == "APPROVED":
                raw.append((parse_ts(rv["submitted_at"]), pr.number, login, rv["user"].get("type", "User"), "approval"))

    authors = {pr.number: pr.author for pr in prs}
    first_pr_of_voter: dict[str, int] = {}
    votes: dict[int, list[dict[str, Any]]] = {pr.number: [] for pr in prs}
    for at, number, voter, vtype, kind in sorted(raw, key=lambda v: (v[0], v[1])):
        if voter == authors[number]:
            reason = "is_author"
        elif vtype == "Bot" or voter.endswith("[bot]"):
            continue  # not counted; not stored either, schema v2 `login` does not allow "[bot]" logins
        elif voter == MAINTAINER:
            reason = "is_maintainer"
        elif not _account_old_enough(gh, voter, now, age_cache):
            reason = "account_too_young"
        elif first_pr_of_voter.setdefault(voter, number) != number:
            reason = "already_voted_in_area"
        else:
            reason = "ok"
        votes[number].append({"voter": voter, "type": kind, "at": fmt_ts(at), "counted": reason == "ok", "reason": reason})
    return votes


def score(votes: list[dict[str, Any]]) -> tuple[int, int, int]:
    up = sum(1 for v in votes if v["counted"] and v["type"] == "thumbs_up")
    ap = sum(1 for v in votes if v["counted"] and v["type"] == "approval")
    return up, ap, up + 2 * ap


# --------------------------------------------------------------------------- comments (bot texts)

LOST_TEXT = (
    "Thanks for playing! 🙌 Another PR won area `{area}` tonight, so this one is closed. "
    "You still get **+1 participation point** for a valid PR with green CI. Try another area!"
)
LOST_OTHER_TEXT = (
    "Congrats, you won area `{won}`! 🎉 You can own only one area per wave, so this PR for "
    "`{area}` is closed. Your +1 participation point stays."
)
INVALID_TEXT = "This PR does not follow the game rules, so it is not counted: {reasons}. See CONTRIBUTING.md."
MERGE_FAILED_TEXT = (
    "This PR won area `{area}`, but merging failed (probably a conflict). "
    "Please update your branch; the area stays in review until the next evaluation."
)
FIX_MERGED_TEXT = "Fix merged, thank you! 🛠️ Area `{area}` keeps its owner. You get +1 participation point."


# --------------------------------------------------------------------------- step 1: fixes


def process_fixes(state: State, gh: GitHub, prs: list[Pr], now: datetime) -> None:
    tmap = territory_by_id(state)
    ts = fmt_ts(now)
    for pr in prs:
        if not pr.is_fix or LABEL_BLOCKED in pr.labels:
            continue
        _label(gh, pr, LABEL_FIX)
        t = tmap.get(pr.area or "")
        if t is None or t["status"] != "claimed":
            continue
        owner = t["owner"]
        if owner and owner != pr.author:
            gh.request_reviewer(pr.number, owner)
        if pr.ci != "success":
            continue
        latest: dict[str, str] = {}
        for rv in sorted(gh.reviews(pr.number), key=lambda x: x["submitted_at"]):
            latest[rv["user"]["login"]] = rv["state"]
        approvers = {login for login, st in latest.items() if st == "APPROVED" and login != pr.author}
        if not approvers & {owner, MAINTAINER}:
            continue
        try:
            gh.merge(pr.number, pr.title)
        except Exception:  # noqa: BLE001 - any API failure means "try again tomorrow"
            gh.comment(pr.number, MERGE_FAILED_TEXT.format(area=pr.area))
            continue
        if pr.author not in (MAINTAINER, owner):
            _participation(state, gh, pr.author, t["id"], pr.number, ts, note="fix")
        gh.comment(pr.number, FIX_MERGED_TEXT.format(area=pr.area))


# --------------------------------------------------------------------------- step 2: validity + voting


def assign_validity(state: State, prs: list[Pr]) -> None:
    """Rules that need state/API (CI checks paths and commits)."""
    tmap, waves = territory_by_id(state), wave_by_number(state)
    owned_waves = {(t["owner"], t["wave"]) for t in state["territories"] if t["status"] == "claimed"}
    per_author: dict[str, list[str]] = {}
    for pr in sorted(prs, key=lambda p: (p.created_at, p.number)):
        reasons: list[str] = []
        t = tmap.get(pr.area or "")
        if LABEL_BLOCKED in pr.labels:
            pr.validity, pr.reasons = "blocked", None
            continue
        if t is None:
            reasons.append("unknown_area")
        elif waves[t["wave"]]["status"] != "open" or t["status"] not in ("free", "in_review"):
            reasons.append("area_not_open")
        if pr.author == MAINTAINER or pr.author_type == "Bot":
            reasons.append("author_is_maintainer")
        if t is not None and (pr.author, t["wave"]) in owned_waves:
            reasons.append("already_owns_in_wave")
        areas = per_author.setdefault(pr.author, [])
        if not reasons:
            if pr.area in areas:
                reasons.append("duplicate_area_pr")
            elif len(areas) >= 2:
                reasons.append("too_many_open_prs")
            else:
                areas.append(pr.area or "")
        pr.validity, pr.reasons = ("invalid", reasons) if reasons else ("valid", None)


class _Counting:
    """Wraps the GitHub client and counts writes that change the game (merge, labels, close)."""

    def __init__(self, gh: GitHub) -> None:
        self._gh, self.writes = gh, 0

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._gh, name)
        if name in ("merge", "add_labels", "close"):

            def counted(*a: Any, **kw: Any) -> Any:
                result = attr(*a, **kw)
                self.writes += 1
                return result

            return counted
        return attr


class DryRun:
    """Reads from GitHub, but only prints the writes (merge, labels, comments, close, reviewers)."""

    WRITES = ("merge", "add_labels", "comment", "close", "request_reviewer")

    def __init__(self, gh: GitHub) -> None:
        self._gh = gh

    def __getattr__(self, name: str) -> Any:
        if name in self.WRITES:
            return lambda *a, **kw: print(f"DRY-RUN: would {name}{a}")
        return getattr(self._gh, name)


def evaluate(state: State, gh: GitHub, now: datetime) -> tuple[State, bool]:
    """Return (new state, changed). When nothing changed (no merge, points, labels or badges),
    the original state is returned untouched, so the workflow writes and commits nothing."""
    original = copy.deepcopy(state)
    gh = _Counting(gh)  # type: ignore[assignment]
    ts = fmt_ts(now)
    prs = [Pr.from_api(raw) for raw in gh.open_pulls()]
    prs = [p for p in prs if p.area is not None]
    for pr in prs:
        pr.ci = gh.ci_status(pr.head_sha)

    process_fixes(state, gh, prs, now)
    voting = [p for p in prs if not p.is_fix]
    assign_validity(state, voting)

    tmap = territory_by_id(state)
    for pr in voting:
        if pr.validity == "invalid" and LABEL_INVALID not in pr.labels:
            _label(gh, pr, LABEL_INVALID)
            gh.comment(pr.number, INVALID_TEXT.format(reasons=", ".join(pr.reasons or [])))
        if pr.validity == "valid" and pr.ci == "success":
            _first_pr_badge(state, gh, pr, ts)

    candidates = [p for p in voting if p.validity == "valid" and p.ci == "success"]
    results: list[dict[str, Any]] = []
    age_cache: dict[str, bool] = {}
    closed: set[int] = set()
    winners: dict[str, Pr] = {}

    for area in sorted({p.area for p in candidates if p.area}):
        area_prs = [p for p in candidates if p.area == area]
        votes = collect_votes(gh, area_prs, now, age_cache)
        scored = []
        for p in area_prs:
            up, ap, total = score(votes[p.number])
            scored.append((p, up, ap, total))
            _record_pr(state, p, votes=votes[p.number], score=total, result="pending")
        best = sorted(scored, key=lambda s: (-s[3], s[0].created_at, s[0].number))[0]
        winner = best[0] if best[3] >= 1 else None
        results.append(
            {
                "territoryId": area,
                "winnerPr": winner.number if winner else None,
                "candidates": [{"pr": p.number, "thumbsUp": up, "approvals": ap, "score": total} for p, up, ap, total in scored],
            }
        )
        if winner is None:
            results[-1]["note"] = "no PR has at least 1 point"
            continue
        try:
            gh.merge(winner.number, winner.title)
        except Exception:  # noqa: BLE001
            gh.comment(winner.number, MERGE_FAILED_TEXT.format(area=area))
            results[-1]["note"] = "merge failed"
            continue
        t = tmap[area]
        _player(state, gh, winner.author, ts)
        t.update(status="claimed", owner=winner.author, winningPr=winner.number, claimedAt=ts)
        _ledger(
            state,
            {
                "id": f"claim:{area}",
                "player": winner.author,
                "points": t["basePoints"],
                "reason": "claim",
                "territoryId": area,
                "pr": winner.number,
                "at": ts,
            },
        )
        _record_pr(state, winner, state="merged", mergedAt=ts, result="won")
        winners[area] = winner
        closed.add(winner.number)

    # losers: other open PRs in won areas + winner's other PRs in the same wave
    for area, winner in winners.items():
        wave = tmap[area]["wave"]
        for p in voting:
            if p.number in closed:
                continue
            same_area = p.area == area
            other_of_winner = p.author == winner.author and p.area in tmap and tmap[p.area]["wave"] == wave
            if not (same_area or other_of_winner):
                continue
            green_valid = p.validity == "valid" and p.ci == "success"
            if green_valid and p.area:
                _participation(state, gh, p.author, p.area, p.number, ts)
            _label(gh, p, LABEL_LOST)
            text = LOST_TEXT.format(area=area) if same_area else LOST_OTHER_TEXT.format(won=area, area=p.area)
            gh.comment(p.number, text)
            gh.close(p.number)
            _record_pr(
                state,
                p,
                state="closed",
                closedAt=ts,
                result="lost",
                lostReason="outscored" if same_area else "won_other_area_in_wave",
            )
            closed.add(p.number)

    # area status free <-> in_review, waves
    open_valid = {p.area for p in voting if p.validity == "valid" and p.number not in closed}
    for t in state["territories"]:
        if t["status"] in ("free", "in_review"):
            t["status"] = "in_review" if t["id"] in open_valid else "free"
    _advance_waves(state, ts)

    badges = sum(len(p["badges"]) for p in state["players"])
    changed = (
        gh.writes > 0
        or len(state["pointsLedger"]) != len(original["pointsLedger"])  # type: ignore[attr-defined]
        or badges != sum(len(p["badges"]) for p in original["players"])
    )
    if not changed:
        return original, False
    if results:
        state["evaluations"].append({"at": ts, "results": results})
    _recompute_scores(state)
    state["updatedAt"] = ts
    return state, True


def _advance_waves(state: State, ts: str) -> None:
    tmap = territory_by_id(state)
    waves = sorted(state["waves"], key=lambda w: w["number"])
    for i, w in enumerate(waves):
        if w["status"] == "open" and all(tmap[t]["status"] == "claimed" for t in w["territoryIds"]):
            w.update(status="completed", completedAt=ts)
            if i + 1 < len(waves):
                nxt = waves[i + 1]
                nxt.update(status="open", openedAt=ts)
                for tid in nxt["territoryIds"]:
                    tmap[tid]["status"] = "free"
                state["currentWave"] = nxt["number"]


def penalty(state: State, login: str, area: str, note: str, now: datetime) -> State:
    """Maintainer veto: take the area away and record negative points."""
    ts = fmt_ts(now)
    t = territory_by_id(state)[area]
    if t["owner"] != login:
        raise SystemExit(f"{login} does not own {area}")
    _ledger(
        state,
        {
            "id": f"penalty_cheating:{login}:{area}:{ts}",
            "player": login,
            "points": -t["basePoints"],
            "reason": "penalty_cheating",
            "territoryId": area,
            "pr": t.get("winningPr"),
            "note": note,
            "at": ts,
        },
    )
    t.update(status="free", owner=None, winningPr=None, claimedAt=None)
    _recompute_scores(state)
    state["updatedAt"] = ts
    return state


# --------------------------------------------------------------------------- real GitHub client


class RestGitHub:  # pragma: no cover - network glue, covered by the dress rehearsal (step 6)
    def __init__(self, repo: str, token: str) -> None:
        self.repo, self.token = repo, token

    def _req(self, method: str, path: str, body: Any = None) -> Any:
        import urllib.request

        url = path if path.startswith("http") else f"https://api.github.com{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req) as resp:
            raw = resp.read()
            link = resp.headers.get("Link", "")
        out = json.loads(raw) if raw else None
        m = re.search(r'<([^>]+)>;\s*rel="next"', link)
        if m and isinstance(out, list):
            out += self._req(method, m.group(1))
        return out

    def open_pulls(self):
        return self._req("GET", f"/repos/{self.repo}/pulls?state=open&per_page=100")

    def ci_status(self, sha):
        runs = self._req("GET", f"/repos/{self.repo}/commits/{sha}/check-runs?per_page=100")["check_runs"]
        runs = [r for r in runs if r["name"] == "ci"]
        if not runs or any(r["status"] != "completed" for r in runs):
            return "pending"
        return "success" if all(r["conclusion"] == "success" for r in runs) else "failure"

    def reactions(self, number):
        return self._req("GET", f"/repos/{self.repo}/issues/{number}/reactions?content=%2B1&per_page=100")

    def reviews(self, number):
        return self._req("GET", f"/repos/{self.repo}/pulls/{number}/reviews?per_page=100")

    def user(self, login):
        return self._req("GET", f"/users/{login}")

    def merge(self, number, title):
        self._req(
            "PUT", f"/repos/{self.repo}/pulls/{number}/merge", {"merge_method": "squash", "commit_title": f"{title} (#{number})"}
        )

    def add_labels(self, number, labels):
        self._req("POST", f"/repos/{self.repo}/issues/{number}/labels", {"labels": labels})

    def comment(self, number, body):
        self._req("POST", f"/repos/{self.repo}/issues/{number}/comments", {"body": body})

    def close(self, number):
        self._req("PATCH", f"/repos/{self.repo}/pulls/{number}", {"state": "closed"})

    def request_reviewer(self, number, login):
        try:
            self._req("POST", f"/repos/{self.repo}/pulls/{number}/requested_reviewers", {"reviewers": [login]})
        except Exception:  # noqa: BLE001 - non-collaborators cannot be requested; not fatal
            pass


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - glue
    from scripts.validate_state import validate

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check-hour", action="store_true")
    ap.add_argument("--penalty", nargs=2, metavar=("LOGIN", "AREA"))
    ap.add_argument("--note", default="cheating")
    ap.add_argument("--dry-run", action="store_true", help="read-only: print GitHub writes, do not write the state")
    args = ap.parse_args(argv)
    now = datetime.now(UTC)
    if args.check_hour:
        return 0 if is_evaluation_hour(now) else 1
    state = load_json(STATE_PATH)
    if args.penalty:
        state = penalty(state, args.penalty[0], args.penalty[1], args.note, now)
    else:
        gh: GitHub = RestGitHub(os.environ.get("GITHUB_REPOSITORY", REPO), os.environ["GH_TOKEN"])
        if args.dry_run:
            gh = DryRun(gh)  # type: ignore[assignment]
        state, changed = evaluate(state, gh, now)
        if args.dry_run:
            print(f"DRY-RUN: changed={changed}, state not written; errors={validate(state)}")
            return 0
        if not changed:
            print("OK: nothing changed, state not written")
            return 0
    errors = validate(state)
    if errors:
        print("\n".join(f"ERROR: {e}" for e in errors), file=sys.stderr)
        return 1
    dump_state(state, STATE_PATH)
    print("OK: state updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
