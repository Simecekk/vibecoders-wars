from scripts.check_pr import Commit, PullRequest, check


def pr(title="[validation] Validate signup", author="alice", files=None, commits=None, labels=()):
    return PullRequest(title=title, author=author, labels=list(labels),
                       files=files if files is not None else ["app/areas/validation/router.py",
                                                              "tests/areas/validation/test_router.py"],
                       commits=commits if commits is not None else [Commit("a" * 40, author, "Add validation")])


def claimed(state, area="crud-endpoints", owner="bob"):
    t = next(t for t in state["territories"] if t["id"] == area)
    t.update(status="claimed", owner=owner, winningPr=1, claimedAt="2026-10-16T18:00:00Z")
    return state


def test_valid(fresh):
    assert check(pr(), fresh) == ("validation", [])


def test_bad_title(fresh):
    area, errors = check(pr(title="Validate signup"), fresh)
    assert area is None and "must start with" in errors[0]


def test_unknown_area(fresh):
    assert "does not exist" in check(pr(title="[nope] x", files=["app/areas/nope/router.py"]), fresh)[1][0]


def test_locked_area(fresh):
    _, errors = check(pr(title="[auth] x", files=["app/areas/auth/router.py"]), fresh)
    assert "not open" in errors[0]


def test_files_outside_area(fresh):
    _, errors = check(pr(files=["app/areas/validation/router.py", "app/main.py"]), fresh)
    assert any("app/main.py" in e for e in errors)


def test_other_area_folder_rejected(fresh):
    _, errors = check(pr(files=["app/areas/validation-extra/router.py"]), fresh)
    assert errors


def test_foreign_commit(fresh):
    _, errors = check(pr(commits=[Commit("b" * 40, "mallory", "x")]), fresh)
    assert any("mallory" in e for e in errors)


def test_unlinked_commit_author(fresh):
    _, errors = check(pr(commits=[Commit("b" * 40, None, "x")]), fresh)
    assert any("unknown account" in e for e in errors)


def test_co_authored_by(fresh):
    _, errors = check(pr(commits=[Commit("c" * 40, "alice", "x\n\nCo-authored-by: Bob <b@x.cz>")]), fresh)
    assert any("Co-authored-by" in e for e in errors)


def test_maintainer_cannot_compete(fresh):
    _, errors = check(pr(author="Simecekk", commits=[Commit("a" * 40, "Simecekk", "x")]), fresh)
    assert any("maintainer" in e for e in errors)


def test_fix_into_claimed_area_passes(fresh):
    files = ["app/areas/crud-endpoints/router.py"]
    assert check(pr(title="[crud-endpoints] Fix 500", files=files, labels=["vv:fix"]), claimed(fresh))[1] == []


def test_claimed_area_without_fix_fails(fresh):
    files = ["app/areas/crud-endpoints/router.py"]
    _, errors = check(pr(title="[crud-endpoints] Fix 500", files=files), claimed(fresh))
    assert "not open" in errors[0]


def test_fix_into_free_area_fails(fresh):
    _, errors = check(pr(labels=["vv:fix"]), fresh)
    assert "only for claimed" in errors[0]
