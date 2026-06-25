import base64
import os

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from crypto import CryptoError, decrypt_envelope


SECRET = b"abcdefghijklmnopqrstuvwxyz012345"


def _ios_shortcut_envelope(plaintext: bytes, key: bytes = SECRET) -> str:
    """Produce the same output format the iOS Shortcut 'Encrypt' action makes.

    iOS Shortcuts calls CryptoKit's `AES.GCM.seal(plaintext, using: SymmetricKey(data: key))`
    and returns `base64(nonce(12) || ciphertext || tag(16))`.
    """
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct_with_tag = aesgcm.encrypt(nonce, plaintext, None)
    return base64.b64encode(nonce + ct_with_tag).decode("ascii")


def test_roundtrip_ios_format():
    ct = _ios_shortcut_envelope(b"my_secret_password")
    assert decrypt_envelope(ct, SECRET) == b"my_secret_password"


def test_roundtrip_empty():
    ct = _ios_shortcut_envelope(b"")
    assert decrypt_envelope(ct, SECRET) == b""


def test_roundtrip_unicode():
    ct = _ios_shortcut_envelope("pässwörd🔐".encode("utf-8"))
    assert decrypt_envelope(ct, SECRET) == "pässwörd🔐".encode("utf-8")


def test_wrong_key_rejected():
    ct = _ios_shortcut_envelope(b"hello", key=b"X" * 32)
    with pytest.raises(CryptoError, match="authentication"):
        decrypt_envelope(ct, SECRET)


def test_tampered_ciphertext_rejected():
    ct = _ios_shortcut_envelope(b"hello")
    raw = bytearray(base64.b64decode(ct))
    raw[len(raw) // 2] ^= 0x01
    with pytest.raises(CryptoError, match="authentication"):
        decrypt_envelope(base64.b64encode(bytes(raw)).decode(), SECRET)


def test_tampered_tag_rejected():
    ct = _ios_shortcut_envelope(b"hello")
    raw = bytearray(base64.b64decode(ct))
    raw[-1] ^= 0x01  # flip a bit in the GCM tag
    with pytest.raises(CryptoError, match="authentication"):
        decrypt_envelope(base64.b64encode(bytes(raw)).decode(), SECRET)


def test_invalid_base64():
    with pytest.raises(CryptoError, match="base64"):
        decrypt_envelope("not!base64@", SECRET)


def test_ciphertext_too_short():
    with pytest.raises(CryptoError, match="too short"):
        decrypt_envelope(base64.b64encode(b"short").decode(), SECRET)


def test_wrong_key_length():
    with pytest.raises(CryptoError, match="32 bytes"):
        decrypt_envelope(_ios_shortcut_envelope(b"x"), b"short")


def test_bytearray_key_works():
    """bytearray is supported so callers can zeroize after use."""
    ct = _ios_shortcut_envelope(b"hello")
    key_buf = bytearray(SECRET)
    try:
        assert decrypt_envelope(ct, key_buf) == b"hello"
    finally:
        for i in range(len(key_buf)):
            key_buf[i] = 0
    assert all(b == 0 for b in key_buf)
