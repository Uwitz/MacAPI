import base64

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoError(Exception):
    pass


NONCE_SIZE = 12
TAG_SIZE = 16


def decrypt_envelope(ct_b64: str, key: bytes | bytearray) -> bytes:
    """Decrypt an iOS Shortcut 'Encrypt' action envelope.

    The iOS Shortcut 'Encrypt' action with AES-256 calls CryptoKit's
    `AES.GCM.seal` with a 32-byte key and returns
    `base64(nonce(12) || ciphertext || tag(16))`.
    """
    if isinstance(key, bytearray):
        key = bytes(key)
    if len(key) != 32:
        raise CryptoError(f"key must be 32 bytes, got {len(key)}")

    try:
        combined = base64.b64decode(ct_b64, validate=True)
    except Exception as e:
        raise CryptoError(f"invalid base64 ciphertext: {e}")

    if len(combined) < NONCE_SIZE + TAG_SIZE:
        raise CryptoError(f"ciphertext too short: {len(combined)} bytes")

    nonce = combined[:NONCE_SIZE]
    ciphertext_with_tag = combined[NONCE_SIZE:]

    try:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except InvalidTag:
        raise CryptoError("GCM authentication failed (wrong key or tampered ciphertext)")
