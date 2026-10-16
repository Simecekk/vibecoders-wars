"""PR checks run by CI (paths, commits, title, area status).

Usage in CI:  python scripts/check_pr.py
Reads the `pull_request` event from $GITHUB_EVENT_PATH, the changed files and
commit authors from the GitHub API (read-only GITHUB_TOKEN), and the game state
from data/territories.json. Prints the area id to $GITHUB_OUTPUT as `area=<id>`.

The pure function `check()` holds all the rules so it can be tested offline.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any

from scripts.common import (
    MAINTAINER,
    STATE_PATH,
    area_from_title,
    is_fix_title,
    load_json,
    territory_by_id,
    wave_by_number,
)

CO_AUTHOR_RE = re.compile(r"^co-authored-by:", re.IGNORECASE | re.MULTILINE)


@dataclass
class Commit:
    sha: str
    author_login: str | None  # None = git author email not linked to a GitHub account
    message: str


@dataclass
class PullRequest:
    title: str
    author: str
    labels: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    commits: list[Commit] = field(default_factory=list)


def check(pr: PullRequest, state: dict[str, Any]) -> tuple[str | None, list[str]]:
    """Return (area id, list of human-readable errors)."""
    errors: list[str] = []
    area = area_from_title(pr.title)
    if area is None and pr.author == MAINTAINER:
        return None, []  # maintainer infrastructure PR (no area): only the full test suite applies
    if area is None:
        return None, ["PR title must start with `[area-id]` (e.g. `[validation] Validate user signup`) "
                      "or `[fix:area-id]` for a fix in a claimed area."]

    is_fix = is_fix_title(pr.title)
    territory = territory_by_id(state).get(area)
    if territory is None:
        errors.append(f"Area `{area}` does not exist.")
    else:
        wave = wave_by_number(state).get(territory["wave"])
        if is_fix:
            if territory["status"] != "claimed":
                errors.append(f"`[fix:...]` PRs are only for claimed areas; `{area}` is `{territory['status']}`.")
        elif wave is None or wave["status"] != "open" or territory["status"] not in ("free", "in_review"):
            errors.append(f"Area `{area}` is not open for claiming (status `{territory['status']}`).")

    if pr.author == MAINTAINER and not is_fix:
        errors.append("The maintainer does not compete for areas.")

    allowed = (f"app/areas/{area}/", f"tests/areas/{area}/")
    outside = [f for f in pr.files if not f.startswith(allowed)]
    if outside:
        errors.append("Only these folders may change: " + ", ".join(f"`{a}`" for a in allowed)
                      + ". Changed outside: " + ", ".join(f"`{f}`" for f in outside))
    conftests = [f for f in pr.files if f.rsplit("/", 1)[-1] == "conftest.py"]
    if conftests:
        errors.append("`conftest.py` files are not allowed in PRs (fixtures come from main): "
                      + ", ".join(f"`{f}`" for f in conftests))
    if not pr.files:
        errors.append("The PR changes no files.")

    for c in pr.commits:
        if c.author_login != pr.author:
            errors.append(f"Commit {c.sha[:7]} is authored by `{c.author_login or 'unknown account'}`, "
                          f"not by `{pr.author}`. All commits must be yours.")
        if CO_AUTHOR_RE.search(c.message):
            errors.append(f"Commit {c.sha[:7]} has a `Co-authored-by:` trailer; co-authors are not allowed.")
    return area, errors


def _api(path: str) -> list[dict[str, Any]]:  # pragma: no cover - network
    import urllib.request

    out: list[dict[str, Any]] = []
    url: str | None = f"https://api.github.com{path}?per_page=100"
    while url:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                                                   "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req) as resp:
            out.extend(json.load(resp))
            m = re.search(r'<([^>]+)>;\s*rel="next"', resp.headers.get("Link", ""))
            url = m.group(1) if m else None
    return out


def main() -> int:  # pragma: no cover - glue
    event = load_json(__import__("pathlib").Path(os.environ["GITHUB_EVENT_PATH"]))["pull_request"]
    repo, number = os.environ["GITHUB_REPOSITORY"], event["number"]
    pr = PullRequest(
        title=event["title"], author=event["user"]["login"], labels=[lb["name"] for lb in event["labels"]],
        files=[f["filename"] for f in _api(f"/repos/{repo}/pulls/{number}/files")],
        commits=[Commit(c["sha"], (c.get("author") or {}).get("login"), c["commit"]["message"])
                 for c in _api(f"/repos/{repo}/pulls/{number}/commits")],
    )
    area, errors = check(pr, load_json(STATE_PATH))
    if area and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"area={area}\n")
    for e in errors:
        print(f"::error::{e}")
    if not errors:
        print(f"OK: PR is valid for area `{area}`" if area else "OK: maintainer PR without an area, running all tests")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
