import os
import secrets
import ssl
import sys
import time

import Quartz
import uvicorn
from dotenv import find_dotenv, load_dotenv, set_key
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from cert import (
    CertError,
    cert_fingerprint,
    generate_self_signed_cert,
)
from crypto import CryptoError, decrypt_envelope
from keychain import (
    KeychainError,
    generate_secret,
    get_secret,
    secret_exists,
    set_secret,
    zeroize,
)
from password_hash import ensure_password_hash, verify_password
from typer import lock_screen, press_return, type_string


APP_SUPPORT_DIR = os.path.expanduser(
    os.getenv("MACAPI_HOME", "~/Library/Application Support/MacAPI")
)
_PROJECT_CERT = "certs/cert.pem"
_PROJECT_KEY = "certs/key.pem"
_PROJECT_ENV = ".env"


def _resolve(path: str) -> str:
    """If `path` doesn't exist, try the project-dir equivalent, then the
    app-support-dir equivalent. Returns the first that exists, or the
    original `path` if neither does (caller will generate it)."""
    candidates = [path]
    if path == _PROJECT_CERT or path == _PROJECT_KEY:
        candidates.append(os.path.join(APP_SUPPORT_DIR, "certs", os.path.basename(path)))
    if path == _PROJECT_ENV:
        candidates.append(os.path.join(APP_SUPPORT_DIR, "config.env"))
    for c in candidates:
        if os.path.exists(c):
            return c
    return path


TLS_CERT_PATH = _resolve(os.getenv("TLS_CERT", _PROJECT_CERT))
TLS_KEY_PATH = _resolve(os.getenv("TLS_KEY", _PROJECT_KEY))
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "2201"))


load_dotenv(_resolve(os.getenv("MACAPI_ENV", _PROJECT_ENV)))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPLAY_WINDOW_SECONDS = 60


def _owner_token() -> str | None:
    return os.getenv("OWNER_TOKEN")


def _password_hash() -> str | None:
    return os.getenv("PASSWORD_HASH")


def _is_screen_locked() -> bool:
    session = Quartz.CGSessionCopyCurrentDictionary() or {}
    return not (
        session.get("CGSSessionScreenIsLocked", 0) == 0
        and session.get("kCGSSessionOnConsoleKey", 0) == 1
    )


def _type_password(password: str) -> None:
    if _is_screen_locked():
        type_string(password)
        press_return()


def _check_owner_token(request: Request) -> None:
    """Verify the Authorization header matches OWNER_TOKEN."""
    if request.headers.get("Authorization") != _owner_token():
        raise HTTPException(status_code=401, detail="Unauthorized")


def _verify_and_type(password: str) -> None:
    """Verify the received password hashes to the stored PASSWORD_HASH before
    typing. Returns silently on success; raises 401 on mismatch."""
    expected = _password_hash()
    if not expected:
        raise HTTPException(
            status_code=500,
            detail="Server PASSWORD_HASH not configured. Run first-run setup.",
        )
    if not verify_password(password, expected):
        raise HTTPException(status_code=401, detail="Password hash mismatch")
    _type_password(password)


@app.get("/")
def read_root():
    return "MacAPI is online"


@app.get("/lock")
async def lock(request: Request):
    if request.headers.get("Authorization") != _owner_token():
        raise HTTPException(status_code=401, detail="Unauthorized")
    import sys
    print(f"[lock] authorized request from {request.client.host}", file=sys.stderr, flush=True)
    lock_screen()
    return "Locked the mac"


@app.post("/unlock")
async def unlock(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    # Both header AND body must carry the owner token.
    _check_owner_token(request)

    if "ct" in body and "ts" in body:
        return await _unlock_envelope(body)
    if "password" in body:
        return await _unlock_plaintext(body)

    raise HTTPException(
        status_code=400,
        detail="Body must contain 'password' (or 'ct'+'ts' for envelope mode)",
    )


async def _unlock_plaintext(body: dict) -> dict:
    """Password arrives in plaintext over TLS. Hash-check it before typing."""
    password = body.get("password")
    if not isinstance(password, str) or not password:
        raise HTTPException(status_code=400, detail="Missing or empty 'password' field")
    # Strip any trailing whitespace/newline the iOS Shortcut may have included.
    password = password.rstrip("\r\n\t ")
    import sys
    print(f"[unlock] received password (len={len(password)})", file=sys.stderr, flush=True)
    _verify_and_type(password)
    return {"status": "unlocked", "mode": "tls"}


async def _unlock_envelope(body: dict) -> dict:
    """Password arrives AES-256-GCM encrypted with SHARED_SECRET."""
    ct_b64 = body.get("ct")
    ts = body.get("ts")

    if not isinstance(ct_b64, str):
        raise HTTPException(status_code=400, detail="Missing 'ct' field")
    if not isinstance(ts, (int, float)):
        raise HTTPException(status_code=400, detail="Missing 'ts' field")

    if abs(time.time() - float(ts)) > REPLAY_WINDOW_SECONDS:
        raise HTTPException(status_code=401, detail="Timestamp out of range")

    try:
        key = get_secret()
    except KeychainError as e:
        raise HTTPException(status_code=500, detail=f"Keychain error: {e}")

    password_buf: bytearray | None = None
    try:
        password_bytes = decrypt_envelope(ct_b64, key)
        password_buf = bytearray(password_bytes)
        try:
            password = password_buf.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=401, detail="Decrypted payload is not valid UTF-8")
        _verify_and_type(password)
    except CryptoError as e:
        raise HTTPException(status_code=401, detail=f"Decryption failed: {e}")
    finally:
        zeroize(key)
        if password_buf is not None:
            zeroize(password_buf)

    return {"status": "unlocked", "mode": "envelope"}


def _first_run() -> None:
    env_path = find_dotenv()
    if not env_path:
        print(
            "ERROR: No .env file found. Create one (e.g. `touch .env`) and run again.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.getenv("OWNER_TOKEN"):
        token = secrets.token_urlsafe(32)
        set_key(env_path, "OWNER_TOKEN", token)
        print(f"Generated OWNER_TOKEN: {token}")
        print("Add this token to your iOS Shortcut.\n")

    if not secret_exists():
        secret = generate_secret()
        set_secret(secret)
        zeroize(bytearray(secret))
        print("Generated 32-byte SHARED_SECRET and stored in macOS Keychain.")
        print("  Service: com.user.macapi")
        print("  Account: shared-secret\n")
        print("To view it for your iOS Shortcut, run:")
        print("  uv run python tools/print_secret.py\n")

    if not os.path.exists(TLS_CERT_PATH) or not os.path.exists(TLS_KEY_PATH):
        generate_self_signed_cert(TLS_CERT_PATH, TLS_KEY_PATH)
        print(f"Generated self-signed Ed25519 TLS certificate.")
        print(f"  Cert: {TLS_CERT_PATH}")
        print(f"  Key:  {TLS_KEY_PATH}")
        print(f"  Fingerprint (SHA-256): {cert_fingerprint(TLS_CERT_PATH)}\n")
        print("Since this is a self-signed cert behind a Cloudflare TCP tunnel,")
        print("you must either install the cert on the iPhone (AirDrop cert.pem,")
        print("install profile, Settings → General → About → Certificate Trust")
        print("Settings → enable), or pin the SHA-256 fingerprint in the iOS")
        print("Shortcut. The fingerprint above is what you pin.\n")

    # Prompt for the Mac login password; store its SHA-256 in .env so the
    # server can verify received passwords before typing them.
    ensure_password_hash(env_path)


if __name__ == "__main__":
    _first_run()
    if not os.path.exists(TLS_CERT_PATH) or not os.path.exists(TLS_KEY_PATH):
        print(f"ERROR: TLS cert/key missing: {TLS_CERT_PATH}", file=sys.stderr)
        sys.exit(1)
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        ssl_certfile=TLS_CERT_PATH,
        ssl_keyfile=TLS_KEY_PATH,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        ssl_ciphers="ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!MD5:!RC4:!3DES:!DSS",
    )
