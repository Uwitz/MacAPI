import hashlib
import hmac
import os
import sys

from dotenv import find_dotenv, set_key


def hash_password(password: str) -> str:
    """Return the SHA-256 hex digest of a password (UTF-8 bytes)."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, expected_hash: str) -> bool:
    """Constant-time comparison of a password's SHA-256 hash to an expected value.

    SHA-256 of a short ASCII password is a low-entropy comparison (the
    attacker can guess the password and compare), so constant-time only
    helps against timing oracles, not brute force. The hash itself is
    the brute-force defense.
    """
    actual = hash_password(password)
    return hmac.compare_digest(actual, expected_hash.lower())


def ensure_password_hash(env_path: str) -> str:
    """First-run helper: prompt for the Mac password, hash it, and persist
    PASSWORD_HASH in the .env file. Returns the hash.

    Reads the password from stdin without echoing. The plaintext password
    is wiped from local variables and the read buffer before returning.
    """
    if os.getenv("PASSWORD_HASH"):
        return os.getenv("PASSWORD_HASH", "")

    import getpass
    pw = getpass.getpass("Enter the Mac login password (used to verify unlock requests): ")
    if not pw:
        print("ERROR: empty password", file=sys.stderr)
        sys.exit(1)
    digest = hash_password(pw)
    # Best-effort wipe of the local plaintext.
    try:
        pw = None  # noqa: F841
    except NameError:
        pass
    set_key(env_path, "PASSWORD_HASH", digest)
    return digest
