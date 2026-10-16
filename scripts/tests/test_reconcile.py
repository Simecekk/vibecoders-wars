"""Self-healing: a merged winner whose state write was lost gets its owner recorded."""
import copy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.common import load_json
from scripts.evaluate import evaluate, reconcile_merged
from scripts.tests.conftest import FakeGitHub
from scripts.validate_state import validate

NOW = datetime(2026, 10, 16, 19, 0, 30, tzinfo=UTC)
MERGED = "2026-10-16T18:45:13Z"


@dataclass
class MergedGitHub(FakeGitHub):
    merged_times: dict[int, str] = field(default_factory=dict)

    def merged_at(self, number):
        return self.merged_times.get(number)


@pytest.fixture
def lost_write():
    """State as left by a run that merged PR #8 but failed to push the state."""
    s = copy.deepcopy(load_json(Path(__file__).parent / "fixtures" / "initial_state.json"))
    next(t for t in s["territories"] if t["id"] == "validation")["status"] = "in_review"
    s["pullRequests"].append(
        {
            "number": 8,
            "url": "https://github.com/Simecekk/vibecoders-wars/pull/8",
            "title": "[validation] Validate user signup",
            "author": "alice",
            "territoryId": "validation",
            "state": "open",
            "createdAt": "2026-10-16T17:42:17Z",
            "headSha": "f" * 40,
            "ciStatus": "success",
            "validity": "valid",
            "labels": [],
            "votes": [],
            "score": 1,
            "result": "pending",
        }
    )
    return s


def terr(s):
    return next(t for t in s["territories"] if t["id"] == "validation")


def test_merged_pr_is_recorded_as_owner(lost_write):
    gh = MergedGitHub(merged_times={8: MERGED})
    out, changed = evaluate(lost_write, gh, NOW)
    assert changed and validate(out) == [], validate(out)
    t = terr(out)
    assert (t["status"], t["owner"], t["winningPr"], t["claimedAt"]) == ("claimed", "alice", 8, MERGED)
    rec = next(r for r in out["pullRequests"] if r["number"] == 8)
    assert (rec["state"], rec["result"], rec["mergedAt"]) == ("merged", "won", MERGED)
    assert [e["id"] for e in out["pointsLedger"]] == ["claim:validation"]
    assert gh.merged == []  # no second merge


def test_reconcile_is_idempotent(lost_write):
    gh = MergedGitHub(merged_times={8: MERGED})
    out, _ = evaluate(lost_write, gh, NOW)
    again, changed = evaluate(copy.deepcopy(out), gh, NOW)
    assert not changed and again == out


def test_unmerged_pr_is_left_alone(lost_write):
    gh = MergedGitHub()
    assert reconcile_merged(lost_write, gh) == 0
    assert terr(lost_write)["owner"] is None


def test_invalid_or_blocked_record_is_not_claimed(lost_write):
    rec = lost_write["pullRequests"][-1]
    rec["validity"] = "invalid"
    assert reconcile_merged(lost_write, MergedGitHub(merged_times={8: MERGED})) == 0
    rec["validity"], rec["labels"] = "valid", ["vv:blocked"]
    assert reconcile_merged(lost_write, MergedGitHub(merged_times={8: MERGED})) == 0


def test_client_without_merged_at_skips(lost_write):
    assert reconcile_merged(lost_write, FakeGitHub()) == 0
