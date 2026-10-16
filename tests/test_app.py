def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_example_area_is_mounted():
    from app.main import discover_areas

    assert "_example" in [area for area, _ in discover_areas()]
