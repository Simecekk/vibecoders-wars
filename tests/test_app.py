def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_example_area_is_mounted():
    from app.main import discover_areas

    assert "_example" in [area for area, _ in discover_areas()]


def test_home_shows_map_leaderboard_rules_and_nav(client):
    from app.pages import load_state

    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    for territory in load_state()["territories"]:
        assert f'data-area="{territory["id"]}"' in response.text
    assert "Leaderboard" in response.text
    assert "Daily winner" in response.text  # rules from RULES.md
    assert "Appendix A" not in response.text  # the bot/CI spec is not shown
    for link in ('href="/rules"', 'href="/docs"', 'href="https://github.com/Simecekk/vibecoders-wars"'):
        assert link in response.text


def test_rules_page(client):
    response = client.get("/rules")
    assert response.status_code == 200
    assert "<h2>Daily winner</h2>" in response.text
    assert "<table>" in response.text


def test_map_labels():
    from app.pages import render_home

    base = {"map": {"q": 0, "r": 0}, "owner": None}
    state = {
        "territories": [
            {**base, "id": "a", "name": "Free", "status": "free"},
            {**base, "id": "b", "name": "Mine", "status": "owned", "owner": "octocat", "map": {"q": 1, "r": 0}},
            {**base, "id": "c", "name": "Hot", "status": "contested", "map": {"q": 0, "r": 1}},
            {**base, "id": "d", "name": "Old", "status": "locked", "map": {"q": 1, "r": 1}},
            {**base, "id": "e", "name": "Gone", "status": "removed", "map": {"q": 2, "r": 1}},
        ],
    }
    html = render_home(state, "")
    assert '<g class="tile free" data-area="a">' in html and '<g class="tile free" data-area="d">' in html
    assert '<g class="tile owned" data-area="b">' in html and "@octocat" in html
    assert '<g class="tile contested" data-area="c">' in html
    assert 'data-area="e"' not in html


def test_leaderboard_ranks_by_areas_owned():
    from app.pages import leaderboard

    def area(owner, status="owned", at="2026-10-01T20:00:00Z"):
        return {"owner": owner, "status": status, "claimedAt": at}

    state = {
        "territories": [
            area("bob"),
            area("bob", at="2026-10-03T20:00:00Z"),
            area("alice", at="2026-10-02T20:00:00Z"),
            area("zed", "claimed"),
            area("carol", "contested"),
            area(None, "free"),
        ]
    }
    # zed reached 1 area before alice did, so zed ranks higher on the tie.
    assert leaderboard(state) == [("bob", 2), ("zed", 1), ("alice", 1)]
