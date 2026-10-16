from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from scripts.common import STATE_PATH, load_json

FIXTURES = Path(__file__).parent / "fixtures"
OLD = "2020-01-01T00:00:00Z"  # account created long ago


@pytest.fixture
def example() -> dict[str, Any]:
    return copy.deepcopy(load_json(FIXTURES / "example.json"))


@pytest.fixture
def fresh() -> dict[str, Any]:
    return copy.deepcopy(load_json(STATE_PATH))


@dataclass
class FakeGitHub:
    """In-memory GitHub API used by evaluate.py tests."""

    pulls: dict[int, dict[str, Any]] = field(default_factory=dict)
    ci: dict[str, str] = field(default_factory=dict)
    reacts: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    revs: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    users: dict[str, dict[str, Any]] = field(default_factory=dict)
    fail_merge: set[int] = field(default_factory=set)
    merged: list[int] = field(default_factory=list)
    closed: list[int] = field(default_factory=list)
    comments: list[tuple[int, str]] = field(default_factory=list)
    reviewers: list[tuple[int, str]] = field(default_factory=list)

    def add_pr(self, number: int, area: str, author: str, created: str = "2026-10-16T09:00:00Z",
               labels: tuple[str, ...] = (), ci: str = "success") -> None:
        sha = f"{number:040x}"
        self.pulls[number] = {"number": number, "title": f"[{area}] Something", "user": {"login": author, "type": "User"},
                              "created_at": created, "head": {"sha": sha}, "labels": [{"name": n} for n in labels],
                              "html_url": f"https://github.com/Simecekk/vibecoders-wars/pull/{number}"}
        self.ci[sha] = ci

    def thumbs(self, number: int, voter: str, at: str = "2026-10-16T10:00:00Z", vtype: str = "User") -> None:
        self.reacts.setdefault(number, []).append({"content": "+1", "created_at": at,
                                                   "user": {"login": voter, "type": vtype}})

    def review(self, number: int, voter: str, state: str = "APPROVED", at: str = "2026-10-16T11:00:00Z") -> None:
        self.revs.setdefault(number, []).append({"state": state, "submitted_at": at,
                                                 "user": {"login": voter, "type": "User"}})

    # --- GitHub protocol
    def open_pulls(self):
        return [p for n, p in self.pulls.items() if n not in self.merged and n not in self.closed]

    def ci_status(self, sha):
        return self.ci[sha]

    def reactions(self, number):
        return self.reacts.get(number, [])

    def reviews(self, number):
        return self.revs.get(number, [])

    def user(self, login):
        return self.users.get(login, {"id": abs(hash(login)) % 10**6, "created_at": OLD,
                                      "avatar_url": f"https://avatars.githubusercontent.com/{login}"})

    def merge(self, number, title):
        if number in self.fail_merge:
            raise RuntimeError("409 conflict")
        self.merged.append(number)

    def add_labels(self, number, labels):
        self.pulls[number]["labels"] += [{"name": n} for n in labels]

    def comment(self, number, body):
        self.comments.append((number, body))

    def close(self, number):
        self.closed.append(number)

    def request_reviewer(self, number, login):
        self.reviewers.append((number, login))


@pytest.fixture
def gh() -> FakeGitHub:
    return FakeGitHub()
