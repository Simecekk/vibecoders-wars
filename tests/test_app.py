def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_example_area_is_mounted():
    from app.main import discover_areas

    assert "_example" in [area for area, _ in discover_areas()]


def test_root_shows_area_map(client):
    from app.map_page import load_state

    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    for territory in load_state()["territories"]:
        assert f'data-area="{territory["id"]}"' in response.text


def test_map_labels():
    from app.map_page import render_map

    base = {"wave": 1, "tier": "S", "basePoints": 10, "map": {"q": 0, "r": 0}, "owner": None}
    state = {
        "currentWave": 1,
        "waves": [{"number": 1, "status": "open"}, {"number": 2, "status": "locked"}],
        "territories": [
            {**base, "id": "a", "name": "Free", "status": "free"},
            {**base, "id": "b", "name": "Mine", "status": "claimed", "owner": "octocat", "map": {"q": 1, "r": 0}},
            {**base, "id": "c", "name": "Later", "status": "locked", "wave": 2, "map": {"q": 0, "r": 1}},
        ],
    }
    html = render_map(state)
    assert "volno · S · 10 b." in html
    assert "@octocat · S · 10 b." in html
    assert "vlna 2" in html and "🔒" in html


def test_leaderboard_counts_claimed_areas():
    from app.map_page import leaderboard

    def area(owner, status="claimed"):
        return {"owner": owner, "status": status}

    state = {"territories": [area("bob"), area("alice"), area("bob"), area("carol", "in_review"), area(None, "free")]}
    assert leaderboard(state) == [("bob", 2), ("alice", 1)]
