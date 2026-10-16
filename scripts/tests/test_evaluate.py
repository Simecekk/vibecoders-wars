import copy
from datetime import UTC, datetime

from scripts.evaluate import evaluate, is_evaluation_hour, penalty
from scripts.validate_state import validate

NOW = datetime(2026, 10, 16, 18, 0, 30, tzinfo=UTC)  # 20:00:30 Prague (CEST)
YOUNG = {"id": 9, "created_at": "2026-10-01T00:00:00Z", "avatar_url": "https://avatars.githubusercontent.com/x"}


def terr(state, area):
    return next(t for t in state["territories"] if t["id"] == area)


def ledger(state, reason=None):
    return [e for e in state["pointsLedger"] if reason is None or e["reason"] == reason]


def run(state, gh, now=NOW):
    out, _ = evaluate(state, gh, now)
    assert validate(out) == [], validate(out)
    return out


def test_thumbs_and_approve_scoring_and_merge(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.add_pr(2, "validation", "bob", created="2026-10-16T09:30:00Z")
    gh.thumbs(1, "v1")
    gh.thumbs(2, "v2")
    gh.review(2, "v3")  # approve = 2 points
    s = run(fresh, gh)
    assert gh.merged == [2] and gh.closed == [1]
    t = terr(s, "validation")
    assert (t["status"], t["owner"], t["winningPr"]) == ("claimed", "bob", 2)
    res = s["evaluations"][-1]["results"][0]
    assert {c["pr"]: c["score"] for c in res["candidates"]} == {1: 1, 2: 3}
    assert [(e["player"], e["points"]) for e in ledger(s, "claim")] == [("bob", 10)]
    assert next(p for p in s["players"] if p["login"] == "bob")["score"] == 10


def test_thumbs_and_approve_on_same_pr_add_up(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.thumbs(1, "v1")
    gh.review(1, "v1")
    s = run(fresh, gh)
    assert s["evaluations"][-1]["results"][0]["candidates"][0]["score"] == 3


def test_excluded_votes(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.thumbs(1, "alice")  # author
    gh.thumbs(1, "dependabot[bot]", vtype="Bot")
    gh.thumbs(1, "Simecekk")
    gh.thumbs(1, "newbie")
    gh.users["newbie"] = YOUNG
    s = run(fresh, gh)
    reasons = {v["voter"]: v["reason"] for v in s["pullRequests"][0]["votes"]}
    assert reasons == {"alice": "is_author", "Simecekk": "is_maintainer",
                       "newbie": "account_too_young"}
    assert gh.merged == [] and terr(s, "validation")["status"] == "in_review"
    assert s["evaluations"][-1]["results"][0]["winnerPr"] is None  # minimum 1 point


def test_only_first_vote_in_area_counts(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.add_pr(2, "validation", "bob")
    gh.thumbs(2, "v1", at="2026-10-16T10:00:00Z")
    gh.review(1, "v1", at="2026-10-16T12:00:00Z")  # second vote in the area: ignored
    s = run(fresh, gh)
    assert gh.merged == [2]
    v = next(p for p in s["pullRequests"] if p["number"] == 1)["votes"][0]
    assert v["reason"] == "already_voted_in_area" and not v["counted"]


def test_votes_after_evaluation_start_ignored(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.thumbs(1, "v1", at="2026-10-16T18:05:00Z")
    run(fresh, gh)
    assert gh.merged == []


def test_latest_review_state_wins(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.review(1, "v1", at="2026-10-16T10:00:00Z")
    gh.review(1, "v1", "CHANGES_REQUESTED", at="2026-10-16T11:00:00Z")
    run(fresh, gh)
    assert gh.merged == []


def test_tie_older_pr_wins(fresh, gh):
    gh.add_pr(5, "validation", "alice", created="2026-10-16T09:00:00Z")
    gh.add_pr(3, "validation", "bob", created="2026-10-16T10:00:00Z")
    gh.thumbs(5, "v1")
    gh.thumbs(3, "v2")
    run(fresh, gh)
    assert gh.merged == [5]


def test_tie_same_time_lower_number_wins(fresh, gh):
    gh.add_pr(5, "validation", "alice")
    gh.add_pr(3, "validation", "bob")
    gh.thumbs(5, "v1")
    gh.thumbs(3, "v2")
    run(fresh, gh)
    assert gh.merged == [3]


def test_loser_gets_lost_label_comment_participation_once(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.add_pr(2, "validation", "bob")
    gh.thumbs(2, "v1")
    s = run(fresh, gh)
    assert {"name": "vv:lost"} in gh.pulls[1]["labels"] and 1 in gh.closed
    assert any(n == 1 and "+1 participation" in body for n, body in gh.comments)
    assert [(e["player"], e["points"]) for e in ledger(s, "participation")] == [("alice", 1)]
    # alice loses again in the same area later -> still only one participation entry
    terr(s, "validation").update(status="free", owner=None, winningPr=None, claimedAt=None)
    s["pointsLedger"] = [e for e in s["pointsLedger"] if e["reason"] != "claim"]
    gh.add_pr(7, "validation", "alice")
    gh.add_pr(8, "validation", "carol")
    gh.thumbs(8, "v9")
    s = run(s, gh)
    assert len([e for e in ledger(s, "participation") if e["player"] == "alice"]) == 1


def test_red_ci_loser_gets_no_participation(fresh, gh):
    gh.add_pr(1, "validation", "alice", ci="failure")
    gh.add_pr(2, "validation", "bob")
    gh.thumbs(2, "v1")
    s = run(fresh, gh)
    assert 1 in gh.closed and ledger(s, "participation") == []


def test_winner_other_pr_in_wave_lost(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.add_pr(2, "error-handling", "alice")
    gh.thumbs(1, "v1")
    s = run(fresh, gh)
    assert gh.merged == [1] and gh.closed == [2]
    assert next(p for p in s["pullRequests"] if p["number"] == 2)["lostReason"] == "won_other_area_in_wave"
    assert len(ledger(s, "participation")) == 1


def test_first_pr_badge(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.add_pr(2, "error-handling", "bob", ci="failure")
    s = run(fresh, gh)
    badges = {p["login"]: [b["id"] for b in p["badges"]] for p in s["players"]}
    assert badges == {"alice": ["first-pr"]}
    s = run(s, gh)
    assert [b["id"] for b in next(p for p in s["players"] if p["login"] == "alice")["badges"]] == ["first-pr"]


def test_wave_opens_when_all_claimed(fresh, gh):
    wave1 = fresh["waves"][0]["territoryIds"]
    for i, area in enumerate(wave1, start=1):
        gh.add_pr(i, area, f"player{i}")
        gh.thumbs(i, "v1")  # one voter per area is fine
    s = run(fresh, gh)
    assert [w["status"] for w in s["waves"]] == ["completed", "open"] and s["currentWave"] == 2
    assert all(terr(s, t)["status"] == "free" for t in s["waves"][1]["territoryIds"])


def test_blocked_pr_is_skipped(fresh, gh):
    gh.add_pr(1, "validation", "alice", labels=("vv:blocked",))
    gh.thumbs(1, "v1")
    s = run(fresh, gh)
    assert gh.merged == [] and s["evaluations"] == []


def test_invalid_limits(fresh, gh):
    gh.add_pr(1, "validation", "alice", created="2026-10-16T08:00:00Z")
    gh.add_pr(2, "validation", "alice", created="2026-10-16T08:01:00Z")      # second PR same area
    gh.add_pr(3, "error-handling", "alice", created="2026-10-16T08:02:00Z")
    gh.add_pr(4, "crud-endpoints", "alice", created="2026-10-16T08:03:00Z")  # third area
    gh.add_pr(5, "auth", "bob")                                             # locked wave
    run(fresh, gh)
    invalid = {n for n, p in gh.pulls.items() if {"name": "vv:invalid"} in p["labels"]}
    assert invalid == {2, 4, 5}
    comments = len(gh.comments)
    run(fresh, gh)  # label already there -> no duplicate comment
    assert len(gh.comments) == comments


def test_owner_cannot_claim_second_area_in_wave(example, gh):
    gh.add_pr(50, "error-handling", "jnovak")
    gh.thumbs(50, "v1")
    run(example, gh)
    assert 50 not in gh.merged and {"name": "vv:invalid"} in gh.pulls[50]["labels"]


def test_merge_failure_keeps_in_review(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.thumbs(1, "v1")
    gh.fail_merge.add(1)
    s = run(fresh, gh)
    assert terr(s, "validation")["status"] == "in_review" and ledger(s, "claim") == []
    assert any("merging failed" in b for _, b in gh.comments)


def test_no_change_no_evaluation_entry(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.users["newbie"] = YOUNG
    gh.thumbs(1, "newbie")
    s1, changed1 = evaluate(fresh, gh, NOW)  # first run: badge -> changed
    assert changed1 and len(s1["evaluations"]) == 1
    before = copy.deepcopy(s1)
    s2, changed2 = evaluate(s1, gh, NOW)
    assert not changed2 and s2 == before  # no merge/points/labels: nothing appended, nothing to write
    young = [v for v in s1["pullRequests"][0]["votes"] if v["voter"] == "newbie"]
    assert young[0]["reason"] == "account_too_young"  # kept in the audit


def test_bot_votes_never_stored(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.thumbs(1, "dependabot[bot]", vtype="Bot")
    gh.thumbs(1, "renovate", vtype="Bot")
    gh.thumbs(1, "v1")
    s = run(fresh, gh)
    assert [v["voter"] for p in s["pullRequests"] for v in p.get("votes", [])] == ["v1"]


def test_fix_label_alone_is_not_a_fix(fresh, gh):
    s = claimed_state(fresh)
    gh.add_pr(10, "crud-endpoints", "carol", labels=("vv:fix",))  # normal title
    gh.review(10, "bob")
    run(s, gh)
    assert gh.merged == [] and {"name": "vv:invalid"} in gh.pulls[10]["labels"]


def test_idempotent(fresh, gh):
    gh.add_pr(1, "validation", "alice")
    gh.add_pr(2, "validation", "bob")
    gh.thumbs(1, "v1")
    s1 = run(fresh, gh)
    snapshot = copy.deepcopy(s1)
    s2 = run(s1, gh)
    for key in ("territories", "pointsLedger", "players", "waves", "pullRequests"):
        assert s2[key] == snapshot[key]
    assert gh.merged == [1]


# ---- vv:fix

def claimed_state(state, area="crud-endpoints", owner="bob"):
    terr(state, area).update(status="claimed", owner=owner, winningPr=1, claimedAt="2026-10-15T18:00:00Z")
    state["players"].append({"login": owner, "githubId": 1, "avatarUrl": "https://a.b/c", "status": "active",
                             "joinedAt": "2026-10-15T18:00:00Z", "badges": [], "score": 10})
    state["pointsLedger"].append({"id": f"claim:{area}", "player": owner, "points": 10, "reason": "claim",
                                  "territoryId": area, "pr": 1, "at": "2026-10-15T18:00:00Z"})
    return state


def test_fix_merged_with_owner_approval(fresh, gh):
    s = claimed_state(fresh)
    gh.add_pr(10, "crud-endpoints", "carol", fix=True)
    gh.thumbs(10, "v1")  # thumbs on fixes do not matter
    gh.review(10, "bob")
    s = run(s, gh)
    assert gh.merged == [10] and terr(s, "crud-endpoints")["owner"] == "bob"
    p = ledger(s, "participation")
    assert [(e["player"], e["points"], e.get("note")) for e in p] == [("carol", 1, "fix")]
    assert s["evaluations"] == []  # skipped in voting
    assert {"name": "vv:fix"} in gh.pulls[10]["labels"]  # bot labels [fix:...] PRs
    assert all(p["number"] != 10 for p in s["pullRequests"])
    assert (10, "bob") in gh.reviewers


def test_fix_merged_with_maintainer_approval(fresh, gh):
    s = claimed_state(fresh)
    gh.add_pr(10, "crud-endpoints", "carol", fix=True)
    gh.review(10, "Simecekk")
    run(s, gh)
    assert gh.merged == [10]


def test_fix_not_merged_without_owner_approval(fresh, gh):
    s = claimed_state(fresh)
    gh.add_pr(10, "crud-endpoints", "carol", fix=True)
    gh.thumbs(10, "v1")
    gh.review(10, "dave")  # random approver
    s = run(s, gh)
    assert gh.merged == [] and ledger(s, "participation") == []


def test_fix_not_merged_with_red_ci(fresh, gh):
    s = claimed_state(fresh)
    gh.add_pr(10, "crud-endpoints", "carol", fix=True, ci="failure")
    gh.review(10, "bob")
    run(s, gh)
    assert gh.merged == []


def test_fix_participation_once_per_area_and_none_for_maintainer(fresh, gh):
    s = claimed_state(fresh)
    gh.add_pr(10, "crud-endpoints", "carol", fix=True)
    gh.add_pr(11, "crud-endpoints", "carol", fix=True)
    gh.add_pr(12, "crud-endpoints", "Simecekk", fix=True)
    for n in (10, 11, 12):
        gh.review(n, "bob")
    s = run(s, gh)
    assert sorted(gh.merged) == [10, 11, 12]
    assert [e["player"] for e in ledger(s, "participation")] == ["carol"]


# ---- clock and penalty

def test_evaluation_hour_summer_and_winter():
    assert is_evaluation_hour(datetime(2026, 7, 1, 18, 5, tzinfo=UTC))      # 20:05 CEST
    assert not is_evaluation_hour(datetime(2026, 7, 1, 19, 5, tzinfo=UTC))  # 21:05 CEST
    assert is_evaluation_hour(datetime(2026, 12, 1, 19, 40, tzinfo=UTC))    # 20:40 CET (late cron)
    assert not is_evaluation_hour(datetime(2026, 12, 1, 18, 5, tzinfo=UTC))  # 19:05 CET


def test_penalty(example):
    s = penalty(example, "jnovak", "crud-endpoints", "fake votes", NOW)
    assert validate(s) == []
    t = terr(s, "crud-endpoints")
    assert (t["status"], t["owner"]) == ("free", None)
    assert ledger(s, "penalty_cheating")[0]["points"] == -10
