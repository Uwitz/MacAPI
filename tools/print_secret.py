"""Print the SHARED_SECRET from the macOS Keychain.

Run this once to get the secret you need to paste into your iOS Shortcut's
'Encrypt' action key field. Requires Keychain access permission on first run.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from keychain import KeychainError, get_secret, zeroize


def main() -> int:
    try:
        secret = get_secret()
    except KeychainError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        print(f"SHARED_SECRET: {secret.decode('ascii')}")
    finally:
        zeroize(secret)

    print()
    print("Copy the 32-character secret above into your iOS Shortcut's")
    print("'Encrypt' action key field. The 'Encrypt' action must be set")
    print("to AES (the default) and the key MUST be exactly 32 bytes")
    print("when interpreted as UTF-8 — this is enforced by CryptoKit")
    print("on the iOS side.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
