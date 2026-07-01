# MacAPI

> Lock and unlock your Mac from your iPhone. End-to-end encrypted. Zero plaintext on the wire. Cloudflare never sees your password.

A hardened FastAPI server that exposes three endpoints — `/lock`, `/unlock`, `/poweroff` — protected by `OWNER_TOKEN` bearer auth, SHA-256 password verification, and TLS 1.3 with AES-256-GCM terminated on the Mac, not at the edge.

---

## How it works

```
iPhone                   Cloudflare (TCP)              Mac
──────                   ────────────────              ───
iOS Shortcut
  │ password (TLS 1.3)
  │ AES-256-GCM ────────► raw bytes ─────────────────► uvicorn
  │ OWNER_TOKEN                                           │
  │                       (sees ciphertext only)         │ SHA-256 hash check
  │                                                      │ (constant-time)
  │                                                      │
  │                                                      ▼
  │                                               Quartz CGEventPost
  │                                               ─────────────────
  │                                               types password into
  └───────────────────────────────────────────── lock screen
```

Cloudflare runs in **TCP tunnel mode** — it forwards raw bytes without terminating TLS. The TLS 1.3 session is end-to-end between the iPhone and the Mac. Cloudflare can see packet sizes and timing, not the password.

---

## Security model

| Layer | Mechanism |
|---|---|
| Transport | TLS 1.3 · AES-256-GCM · ECDHE forward secrecy · Ed25519 server cert |
| Endpoint auth | `Authorization: <OWNER_TOKEN>` header (32-byte url-safe random) |
| Password guard | SHA-256 hash stored in `.env` · constant-time compare · 401 on mismatch, no typing |
| Keychain | 32-byte `SHARED_SECRET` in macOS Keychain (envelope mode) · never touches shell or `argv` |
| Memory hygiene | Decrypted password held in a `bytearray`, zeroed immediately after typing |
| Cert pinning | iPhone pins the Mac cert's SHA-256 fingerprint · MITM impossible without the key |
| Replay | 60-second timestamp window in envelope mode |
| BFU poweroff | `/poweroff` triggers `sudo shutdown -h now` · FileVault keys lost from RAM |

### What this does not protect against

- A compromised iPhone that holds both `OWNER_TOKEN` and the Mac password
- A compromised Mac user session (can read `.env` and the cert)
- Replay within 60 s in envelope mode (an active network attacker capturing a request gets one window)

---

## Endpoints

| Method | Path | Auth | Effect |
|---|---|---|---|
| `GET` | `/` | none | health check — returns `MacAPI is online` |
| `GET` | `/lock` | `OWNER_TOKEN` | locks screen via Ctrl+Cmd+Q |
| `POST` | `/unlock` | `OWNER_TOKEN` + password | verifies password hash, then types via Quartz |
| `POST` | `/poweroff` | `OWNER_TOKEN` | `sudo shutdown -h now` — BFU mode, FileVault keys wiped |

### `/unlock` body

Plaintext mode (password over TLS):
```json
{ "password": "your-mac-password" }
```

Envelope mode (AES-256-GCM encrypted with `SHARED_SECRET`):
```json
{ "ct": "<base64(nonce || ciphertext || tag)>", "ts": 1719876543.0 }
```

---

## Setup

### 1. Install dependencies

```bash
cd MacAPI
touch .env
uv sync
```

### 2. First run

```bash
uv run python main.py
```

Generates on first run:
- `OWNER_TOKEN` (32-byte url-safe) → `.env`
- Ed25519 self-signed TLS cert → `certs/cert.pem` + `certs/key.pem` (mode `0600`)
- Prompts for Mac login password, stores SHA-256 hash in `.env` (plaintext never written to disk)
- Prints the cert's SHA-256 fingerprint — **pin this in your iOS Shortcut**

Server listens on `0.0.0.0:2201` with TLS 1.3 and AES-256-GCM ciphers only.

### 3. Cloudflare Tunnel (TCP mode)

```bash
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create macapi
```

`~/.cloudflared/config.yml`:
```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/<you>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: macapi.example.com
    service: tcp://localhost:2201
  - service: http_status:404
```

```bash
cloudflared tunnel route dns macapi macapi.example.com
cloudflared tunnel run macapi
```

Use `tcp://` not `https://`. HTTPS mode terminates TLS at the Cloudflare edge and exposes your password. TCP mode is a transparent byte forwarder.

### 4. iOS Shortcut

| # | Action | Setting |
|---|---|---|
| 1 | **Text** | `<OWNER_TOKEN>` |
| 2 | **Ask for Input** | Prompt: `Mac Password` · Type: Text |
| 3 | **Dictionary** | `password` → Input from step 2 |
| 4 | **Get Contents of URL** | `https://macapi.example.com/unlock` · POST · Header `Authorization: <token>` · Body: JSON from step 3 |

To verify the connection: add an **If** step that checks the response body contains `unlocked`.

To install the cert instead of pinning: AirDrop `certs/cert.pem` → install profile → Settings → General → About → Certificate Trust Settings → enable.

---

## Run as a launchd service

```bash
cp com.user.macapi.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.macapi.plist
```

`OWNER_TOKEN`, `PASSWORD_HASH`, cert, and Keychain entry persist across restarts. No interactive prompt on subsequent runs.

---

## `/poweroff` — BFU mode

FileVault encrypts the disk. The decryption key lives in RAM while the Mac is unlocked. `/poweroff` calls `sudo shutdown -h now`, wiping all RAM. On next boot, the FileVault password is required before any data is accessible — even with physical access to the disk.

Requires passwordless sudo for `/sbin/shutdown`. `setup.sh` configures this.

---

## Key management

**Rotate the TLS cert:**
```bash
rm certs/cert.pem certs/key.pem
uv run python main.py
```
Update the pinned fingerprint in the iOS Shortcut.

**Reset the password hash** (e.g. after changing the Mac login password):
```bash
sed -i '' '/^PASSWORD_HASH=/d' .env
uv run python main.py   # prompts for the new password
```

**View the Keychain secret** (for envelope mode setup):
```bash
uv run python tools/print_secret.py
```

---

## Tests

```bash
uv run pytest
```

76 tests across:
- `test_crypto.py` — AES-256-GCM envelope decryption
- `test_keychain.py` — real Keychain roundtrip with auto-cleanup
- `test_password_hash.py` — hash generation and constant-time verify
- `test_typer.py` — Quartz keyboard event mocking
- `test_server.py` — envelope and plaintext unlock flows, all auth/hash rejection paths
- `test_cert.py` — Ed25519 generation, TLS 1.3 context, cipher selection, TLS 1.2 rejection
- `test_paths.py` — path resolution across project dir and `~/Library/Application Support/MacAPI`

```bash
uv run ruff check   # lint
```

---

## Post-quantum readiness

The TLS bulk cipher (AES-256-GCM) provides ~128-bit post-quantum security under Grover's algorithm. The server cert uses Ed25519 today. When iOS gains TLS support for ML-DSA-87, swap one line in `cert.py` — the rest of the stack is unchanged.

---

## Security

Vulnerabilities: `security@uwitz.org` — do not open a public issue.

See [SECURITY.md](SECURITY.md) for scope, disclosure timeline, and what is explicitly out of scope (physical access, iPhone compromise).
