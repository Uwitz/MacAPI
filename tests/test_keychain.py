import secrets
import string
from unittest.mock import patch

import pytest
from Security import SecItemDelete

from keychain import (
    ACCOUNT,
    SERVICE,
    SECRET_LENGTH,
    KeychainError,
    generate_secret,
    get_secret,
    secret_exists,
    set_secret,
    zeroize,
)


def _cleanup():
    SecItemDelete({
        "class": "genp",
        "svce": SERVICE,
        "acct": ACCOUNT,
    })


@pytest.fixture(autouse=True)
def _clean_keychain():
    _cleanup()
    yield
    _cleanup()


def test_generate_secret_is_32_ascii():
    secret = generate_secret()
    assert len(secret) == SECRET_LENGTH == 32
    assert secret.decode("ascii").isalnum()
    for c in secret:
        assert c in (string.ascii_letters + string.digits).encode("ascii")


def test_generate_secret_is_unique():
    samples = {generate_secret() for _ in range(50)}
    assert len(samples) == 50


def test_secret_exists_false_initially():
    assert secret_exists() is False


def test_set_and_get_roundtrip():
    secret = generate_secret()
    set_secret(secret)
    assert secret_exists() is True
    got = get_secret()
    try:
        assert bytes(got) == secret
    finally:
        zeroize(got)


def test_set_secret_overwrites_existing():
    set_secret(generate_secret())
    second = generate_secret()
    set_secret(second)
    got = get_secret()
    try:
        assert bytes(got) == second
    finally:
        zeroize(got)


def test_set_secret_rejects_wrong_length():
    with pytest.raises(KeychainError, match="32 bytes"):
        set_secret(b"tooshort")
    with pytest.raises(KeychainError, match="32 bytes"):
        set_secret(b"x" * 64)


def test_get_secret_missing_raises():
    with pytest.raises(KeychainError, match="not found"):
        get_secret()


def test_get_secret_returns_bytearray():
    set_secret(generate_secret())
    got = get_secret()
    assert isinstance(got, bytearray)
    zeroize(got)


def test_zeroize():
    buf = bytearray(b"some secret data here!!!!!!!!")
    zeroize(buf)
    assert all(b == 0 for b in buf)
