import hashlib
import json
import os
from datetime import timedelta

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["SEED_EVENTS"] = "3"
os.environ["SEED_CAPACITY"] = "5"
ALICE_TOKEN = "a" * 64
BOB_TOKEN = "b" * 64
os.environ["API_USERS"] = json.dumps({
    "alice": hashlib.sha256(ALICE_TOKEN.encode()).hexdigest(),
    "bob": hashlib.sha256(BOB_TOKEN.encode()).hexdigest(),
})

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from eventflow.config import Settings
from eventflow.db import SessionLocal
from eventflow.main import app, expire_pending_reservations
from eventflow.models import Reservation, utcnow
from eventflow.seed import seed


@pytest.fixture()
def client():
    seed(reset=True)
    with TestClient(app) as c:
        c.headers["Authorization"] = f"Bearer {ALICE_TOKEN}"
        yield c


def reserve(client, qty, key):
    return client.post("/api/reservations", json={"event_id": 1, "quantity": qty, "idempotency_key": key})


@pytest.mark.parametrize("database_url", [None, ""])
def test_database_url_is_required(monkeypatch, database_url):
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize("users", [
    None,
    "{}",
    '{"alice":"invalid"}',
    json.dumps({"Alice": "a" * 64}),
    json.dumps({"alice": "a" * 64, "bob": "a" * 64}),
])
def test_api_users_are_required(monkeypatch, users):
    if users is None:
        monkeypatch.delenv("API_USERS", raising=False)
    else:
        monkeypatch.setenv("API_USERS", users)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_reservations_require_authentication(client):
    for token in ("", "Bearer invalid", f"Bearer {'c' * 64}"):
        headers = {"Authorization": token}
        assert client.post("/api/reservations", headers=headers, json={
            "event_id": 1, "quantity": 1, "idempotency_key": "auth-test-001",
        }).status_code == 401
        assert client.post("/api/reservations/1/confirm", headers=headers).status_code == 401
        assert client.delete("/api/reservations/1", headers=headers).status_code == 401
    assert client.get("/api/events").status_code == 200


def test_reservation_ownership_and_idempotency(client):
    first = reserve(client, 2, "shared-key-001").json()
    bob_headers = {"Authorization": f"Bearer {BOB_TOKEN}"}
    assert client.post(f"/api/reservations/{first['id']}/confirm", headers=bob_headers).status_code == 404
    assert client.delete(f"/api/reservations/{first['id']}", headers=bob_headers).status_code == 404
    assert client.get("/api/events/1/availability").json()["available"] == 3
    other = client.post("/api/reservations", headers=bob_headers, json={
        "event_id": 1, "quantity": 1, "idempotency_key": "shared-key-001",
    })
    assert other.status_code == 201
    assert other.json()["id"] != first["id"]
    assert reserve(client, 2, "shared-key-001").json()["id"] == first["id"]
    assert client.post(f"/api/reservations/{first['id']}/confirm").status_code == 200
    assert client.delete(f"/api/reservations/{first['id']}").status_code == 204
    assert client.delete(f"/api/reservations/{other.json()['id']}", headers=bob_headers).status_code == 204
    assert client.get("/api/events/1/availability").json()["available"] == 5


def test_health_and_listing(client):
    assert client.get("/health").status_code == 200
    assert len(client.get("/api/events").json()) == 3


def test_no_overselling(client):
    assert reserve(client, 5, "key-00000001").status_code == 201
    assert reserve(client, 1, "key-00000002").status_code == 409
    assert client.get("/api/events/1/availability").json()["available"] == 0


def test_idempotency_and_cancel(client):
    first = reserve(client, 2, "key-00000003").json()
    assert reserve(client, 2, "key-00000003").json()["id"] == first["id"]
    assert client.get("/api/events/1/availability").json()["available"] == 3
    assert client.delete(f"/api/reservations/{first['id']}").status_code == 204
    assert client.get("/api/events/1/availability").json()["available"] == 5


def test_expired_reservation_releases_inventory_once(client):
    reservation = reserve(client, 2, "key-expired-001").json()
    with SessionLocal() as db:
        item = db.get(Reservation, reservation["id"])
        item.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()

    assert expire_pending_reservations() == 1
    assert expire_pending_reservations() == 0
    assert client.get("/api/events/1/availability").json()["available"] == 5
    assert client.post(f"/api/reservations/{reservation['id']}/confirm").status_code == 409
    assert client.delete(f"/api/reservations/{reservation['id']}").status_code == 204
    assert client.get("/api/events/1/availability").json()["available"] == 5
