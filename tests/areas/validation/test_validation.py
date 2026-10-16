import uuid

import pytest


def _username() -> str:
    return f"u_{uuid.uuid4().hex[:12]}"


def _signup(**overrides) -> dict:
    body = {
        "username": _username(),
        "email": "Ada@Example.com",
        "age": 30,
        "password": "secret123",
        "password_confirm": "secret123",
    }
    body.update(overrides)
    return body


def test_signup_creates_user_without_password(client):
    body = _signup()
    r = client.post("/validation/users", json=body)
    assert r.status_code == 201
    assert r.json() == {"username": body["username"], "email": "ada@example.com", "age": 30}


def test_signup_rejects_duplicate_username(client):
    body = _signup()
    assert client.post("/validation/users", json=body).status_code == 201
    assert client.post("/validation/users", json=body).status_code == 409


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("username", "ab"),
        ("username", "Has-Caps"),
        ("email", "not-an-email"),
        ("age", 12),
        ("age", 121),
        ("password", "short1"),
        ("password", "onlyletters"),
        ("password", "12345678"),
    ],
)
def test_signup_rejects_invalid_field(client, field, value):
    body = _signup(**{field: value})
    if field == "password":
        body["password_confirm"] = value
    r = client.post("/validation/users", json=body)
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"][-1] == field


def test_signup_rejects_mismatched_passwords(client):
    r = client.post("/validation/users", json=_signup(password_confirm="different123"))
    assert r.status_code == 422
    assert "passwords do not match" in r.json()["detail"][0]["msg"]


def test_signup_rejects_missing_field(client):
    body = _signup()
    del body["email"]
    assert client.post("/validation/users", json=body).status_code == 422


def test_get_user(client):
    body = _signup()
    client.post("/validation/users", json=body)
    r = client.get(f"/validation/users/{body['username']}")
    assert r.status_code == 200
    assert r.json()["username"] == body["username"]


def test_get_user_not_found(client):
    assert client.get(f"/validation/users/{_username()}").status_code == 404


def test_get_user_rejects_invalid_username_in_path(client):
    assert client.get("/validation/users/NOT_VALID").status_code == 422


def test_list_users_filters_by_age_and_limits(client):
    old = _signup(age=99)
    client.post("/validation/users", json=old)
    r = client.get("/validation/users", params={"min_age": 99, "limit": 100})
    assert r.status_code == 200
    assert old["username"] in [u["username"] for u in r.json()]
    assert all(u["age"] >= 99 for u in r.json())
    assert len(client.get("/validation/users", params={"limit": 1}).json()) == 1


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"min_age": 5}, {"min_age": "old"}])
def test_list_users_rejects_invalid_query(client, params):
    assert client.get("/validation/users", params=params).status_code == 422
