import pytest

from password_hash import hash_password, verify_password


def test_hash_password_is_sha256_hex():
    h = hash_password("hunter2")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_hash_password_deterministic():
    assert hash_password("same") == hash_password("same")


def test_hash_password_different_inputs_differ():
    assert hash_password("a") != hash_password("b")


def test_verify_password_accepts_correct():
    h = hash_password("hunter2")
    assert verify_password("hunter2", h) is True


def test_verify_password_rejects_wrong():
    h = hash_password("hunter2")
    assert verify_password("hunter3", h) is False


def test_verify_password_case_sensitive():
    h = hash_password("hunter2")
    assert verify_password("Hunter2", h) is False


def test_verify_password_accepts_uppercase_hash():
    """Stored hash might be uppercased if read from a tool that uppercases."""
    h = hash_password("hunter2").upper()
    assert verify_password("hunter2", h) is True


def test_verify_password_empty_string():
    h = hash_password("hunter2")
    assert verify_password("", h) is False
    assert verify_password("hunter2", "") is False


def test_verify_password_unicode():
    h = hash_password("pässwörd🔐")
    assert verify_password("pässwörd🔐", h) is True
    assert verify_password("pässwörd", h) is False
