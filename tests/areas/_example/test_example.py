def test_get_item(client):
    assert client.get("/_example/items/1").json() == {"id": 1, "name": "tiger"}
    assert client.get("/_example/items/99").status_code == 404


def test_echo(client):
    assert client.post("/_example/echo", json={"id": 2, "name": "lion"}).json() == {"id": 2, "name": "lion"}
