import base64
import os
import time
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi.testclient import TestClient

from keychain import KeychainError
from password_hash import hash_password

from main import app


SECRET = b"abcdefghijklmnopqrstuvwxyz012345"
TOKEN = "test_token_123"
PASSWORD = "mypassword"
PASSWORD_HASH = hash_password(PASSWORD)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("OWNER_TOKEN", TOKEN)
    monkeypatch.setenv("PASSWORD_HASH", PASSWORD_HASH)


@pytest.fixture
def key_mock():
    with patch("main.get_secret", return_value=bytearray(SECRET)) as mock:
        yield mock


@pytest.fixture
def client():
    return TestClient(app)


def _ios_shortcut_envelope(plaintext: bytes, key: bytes = SECRET) -> str:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ct_with_tag).decode("ascii")


def _auth():
    return {"Authorization": TOKEN, "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# Root + lock
# ---------------------------------------------------------------------------


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200


def test_lock_requires_auth(client):
    r = client.get("/lock")
    assert r.status_code == 401


def test_lock_with_auth(client):
    with patch("main.lock_screen") as mock_lock:
        r = client.get("/lock", headers={"Authorization": TOKEN})
    assert r.status_code == 200
    mock_lock.assert_called_once()


# ---------------------------------------------------------------------------
# /unlock: header + body owner_token defense in depth
# ---------------------------------------------------------------------------


def test_unlock_rejects_missing_authorization_header(client, key_mock):
    r = client.post("/unlock", json={"owner_token": TOKEN, "password": PASSWORD})
    assert r.status_code == 401


def test_unlock_rejects_wrong_authorization_header(client, key_mock):
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "password": PASSWORD},
        headers={"Authorization": "wrong"},
    )
    assert r.status_code == 401


def test_unlock_rejects_missing_body_owner_token(client, key_mock):
    r = client.post(
        "/unlock",
        json={"password": PASSWORD},
        headers=_auth(),
    )
    assert r.status_code == 401
    assert "owner_token" in r.json()["detail"]


def test_unlock_rejects_wrong_body_owner_token(client, key_mock):
    r = client.post(
        "/unlock",
        json={"owner_token": "wrong", "password": PASSWORD},
        headers=_auth(),
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# /unlock: Option B (plaintext over TLS)
# ---------------------------------------------------------------------------


def test_unlock_plaintext_success_types_password(client, key_mock):
    with patch("main._is_screen_locked", return_value=True), \
         patch("main.type_string") as mock_type, \
         patch("main.press_return") as mock_return:
        r = client.post(
            "/unlock",
            json={"owner_token": TOKEN, "password": PASSWORD},
            headers=_auth(),
        )
    assert r.status_code == 200
    assert r.json()["mode"] == "tls"
    mock_type.assert_called_once_with(PASSWORD)
    mock_return.assert_called_once()


def test_unlock_plaintext_skips_typing_when_unlocked(client, key_mock):
    with patch("main._is_screen_locked", return_value=False), \
         patch("main.type_string") as mock_type:
        r = client.post(
            "/unlock",
            json={"owner_token": TOKEN, "password": PASSWORD},
            headers=_auth(),
        )
    assert r.status_code == 200
    mock_type.assert_not_called()


def test_unlock_plaintext_rejects_empty_string(client, key_mock):
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "password": ""},
        headers=_auth(),
    )
    assert r.status_code == 400


def test_unlock_plaintext_rejects_non_string(client, key_mock):
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "password": 12345},
        headers=_auth(),
    )
    assert r.status_code == 400


def test_unlock_plaintext_rejects_wrong_password(client, key_mock):
    """A password that doesn't hash to the stored value must be rejected."""
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "password": "wrongpassword"},
        headers=_auth(),
    )
    assert r.status_code == 401
    assert "hash" in r.json()["detail"].lower()


def test_unlock_plaintext_does_not_touch_keychain(client, monkeypatch):
    def explode():
        raise AssertionError("get_secret should not be called in plaintext mode")

    monkeypatch.setattr("main.get_secret", explode)
    with patch("main._is_screen_locked", return_value=True), \
         patch("main.type_string"):
        r = client.post(
            "/unlock",
            json={"owner_token": TOKEN, "password": PASSWORD},
            headers=_auth(),
        )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# /unlock: Option A (AES-256-GCM envelope)
# ---------------------------------------------------------------------------


def test_unlock_envelope_success_types_password(client, key_mock):
    ct = _ios_shortcut_envelope(PASSWORD.encode())
    with patch("main._is_screen_locked", return_value=True), \
         patch("main.type_string") as mock_type:
        r = client.post(
            "/unlock",
            json={"owner_token": TOKEN, "ct": ct, "ts": time.time()},
            headers=_auth(),
        )
    assert r.status_code == 200
    assert r.json()["mode"] == "envelope"
    mock_type.assert_called_once_with(PASSWORD)


def test_unlock_envelope_rejects_wrong_key(client, key_mock):
    ct = _ios_shortcut_envelope(PASSWORD.encode(), key=b"X" * 32)
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "ct": ct, "ts": time.time()},
        headers=_auth(),
    )
    assert r.status_code == 401


def test_unlock_envelope_rejects_old_timestamp(client, key_mock):
    ct = _ios_shortcut_envelope(PASSWORD.encode())
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "ct": ct, "ts": time.time() - 120},
        headers=_auth(),
    )
    assert r.status_code == 401


def test_unlock_envelope_rejects_decrypted_password_with_wrong_hash(client, key_mock):
    """Even with a valid envelope, the decrypted password must hash correctly."""
    ct = _ios_shortcut_envelope(b"wrongpassword")
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "ct": ct, "ts": time.time()},
        headers=_auth(),
    )
    assert r.status_code == 401
    assert "hash" in r.json()["detail"].lower()


def test_unlock_envelope_zeroizes_key_even_on_failure(client, key_mock):
    seen_keys = []
    def tracking():
        k = bytearray(SECRET)
        seen_keys.append(k)
        return k
    with patch("main.get_secret", side_effect=tracking):
        r = client.post(
            "/unlock",
            json={
                "owner_token": TOKEN,
                "ct": base64.b64encode(b"\x00" * 40).decode(),
                "ts": time.time(),
            },
            headers=_auth(),
        )
    assert r.status_code == 401
    assert seen_keys
    assert all(b == 0 for b in seen_keys[0])


# ---------------------------------------------------------------------------
# /unlock: missing/invalid body
# ---------------------------------------------------------------------------


def test_unlock_rejects_body_with_no_password_or_envelope(client, key_mock):
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "foo": "bar"},
        headers=_auth(),
    )
    assert r.status_code == 400


def test_unlock_rejects_invalid_json(client, key_mock):
    r = client.post(
        "/unlock",
        content="not json",
        headers=_auth(),
    )
    assert r.status_code == 400


def test_unlock_envelope_takes_precedence_over_plaintext(client, key_mock):
    """If both are present, envelope mode wins."""
    ct = _ios_shortcut_envelope(PASSWORD.encode())
    with patch("main._is_screen_locked", return_value=True), \
         patch("main.type_string") as mock_type:
        r = client.post(
            "/unlock",
            json={
                "owner_token": TOKEN,
                "password": "plaintext-password",
                "ct": ct,
                "ts": time.time(),
            },
            headers=_auth(),
        )
    assert r.status_code == 200
    assert r.json()["mode"] == "envelope"
    mock_type.assert_called_once_with(PASSWORD)


# ---------------------------------------------------------------------------
# /unlock: server misconfig (no PASSWORD_HASH) returns 500
# ---------------------------------------------------------------------------


def test_unlock_returns_500_when_password_hash_unset(client, key_mock, monkeypatch):
    monkeypatch.delenv("PASSWORD_HASH", raising=False)
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "password": PASSWORD},
        headers=_auth(),
    )
    assert r.status_code == 500
    assert "PASSWORD_HASH" in r.json()["detail"]


def test_unlock_envelope_keychain_failure_returns_500(client, monkeypatch):
    def boom():
        raise KeychainError("simulated")
    monkeypatch.setattr("main.get_secret", boom)
    r = client.post(
        "/unlock",
        json={"owner_token": TOKEN, "ct": "AAAA", "ts": time.time()},
        headers=_auth(),
    )
    assert r.status_code == 500
