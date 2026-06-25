import secrets
import string

from Security import (
    SecItemAdd,
    SecItemCopyMatching,
    SecItemDelete,
    errSecItemNotFound,
    errSecSuccess,
    kSecAttrAccount,
    kSecAttrService,
    kSecClass,
    kSecClassGenericPassword,
    kSecReturnData,
    kSecValueData,
)


SERVICE = "com.user.macapi"
ACCOUNT = "shared-secret"
SECRET_LENGTH = 32


class KeychainError(Exception):
    pass


def _query() -> dict:
    return {
        kSecClass: kSecClassGenericPassword,
        kSecAttrService: SERVICE,
        kSecAttrAccount: ACCOUNT,
    }


def generate_secret() -> bytes:
    """Generate a 32-character random ASCII secret (exactly 32 bytes UTF-8)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(SECRET_LENGTH)).encode("ascii")


def secret_exists() -> bool:
    try:
        get_secret()
        return True
    except KeychainError:
        return False


def get_secret() -> bytearray:
    """Fetch the 32-byte secret from the macOS Keychain as a mutable bytearray.

    Returns a bytearray so the caller can zero it in place after use.
    Never touches the shell, so the secret is not exposed via `ps`.
    """
    query = _query()
    query[kSecReturnData] = True
    status, data = SecItemCopyMatching(query, None)
    if status == errSecItemNotFound:
        raise KeychainError(
            "SHARED_SECRET not found in Keychain. "
            "Run the server once to generate it."
        )
    if status != errSecSuccess:
        raise KeychainError(f"Keychain read failed: OSStatus {status}")
    if data is None:
        raise KeychainError("Keychain returned no data")
    secret = bytearray(bytes(data))
    if len(secret) != SECRET_LENGTH:
        raise KeychainError(
            f"SHARED_SECRET in Keychain is {len(secret)} bytes, expected {SECRET_LENGTH}. "
            "Delete the entry and let the server regenerate it."
        )
    return secret


def set_secret(secret: bytes) -> None:
    """Store the 32-byte secret in the macOS Keychain.

    Uses PyObjC's Security framework — no shell, no `ps` exposure.
    """
    if len(secret) != SECRET_LENGTH:
        raise KeychainError(f"secret must be exactly {SECRET_LENGTH} bytes, got {len(secret)}")

    SecItemDelete(_query())

    attrs = _query()
    attrs[kSecValueData] = bytes(secret)
    status, _ = SecItemAdd(attrs, None)
    if status != errSecSuccess:
        raise KeychainError(f"Keychain write failed: OSStatus {status}")


def zeroize(buffer: bytearray) -> None:
    """Overwrite a bytearray with zeros in place."""
    for i in range(len(buffer)):
        buffer[i] = 0
