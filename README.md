# MacAPI

A background API on your Mac that lets an iOS Shortcut remotely **lock** and **unlock** the screen. The connection is **TLS 1.3 with AES-256-GCM** end-to-end (quantum-resistant bulk encryption), authenticated with an **Ed25519** self-signed cert that the iPhone pins, and the password is **hash-verified** before being typed via Quartz `CGEventCreateKeyboardEvent`.

The Mac is exposed to the internet via a **Cloudflare Tunnel in TCP mode**, so Cloudflare acts as a transparent byte forwarder — **Cloudflare never sees the password in plaintext**.

## Architecture

```
┌──────────────────┐                              ┌──────────────────┐
│   iOS Shortcut   │                              │      Mac         │
│                  │                              │                  │
│  ┌────────────┐  │   TLS 1.3 / AES-256-GCM      │ ┌──────────────┐ │
│  │  password  │──┼────────(encrypted)──────────┼─▶│  uvicorn     │ │
│  │            │  │                              │ │  Ed25519 cert│ │
│  │ owner_token│  │                              │ │  TLS 1.3     │ │
│  └────────────┘  │                              │ │  AES-256-GCM │ │
└──────────────────┘                              │ └──────┬───────┘ │
        │                                         │        │         │
        │  iPhone pins Mac's cert SHA-256         │ ┌──────▼───────┐ │
        │                                         │ │ SHA-256 hash │ │
        │                                         │ │   check      │ │
        │  Cloudflare edge (TCP forwarder)        │ └──────┬───────┘ │
        ▼                                         │        │         │
┌──────────────────┐                              │ ┌──────▼───────┐ │
│  Cloudflare edge │─── raw TCP bytes ────────────│ │  Quartz      │ │
│  (sees only      │   (still encrypted)          │ │  CGEventPost │ │
│   ciphertext)    │                              │ └──────────────┘ │
└──────────────────┘                              └──────────────────┘
```

## Security properties

| Layer | Property | Notes |
|---|---|---|
| **In transit (iPhone → Cloudflare → Mac)** | TLS 1.3, AES-256-GCM | End-to-end. Cloudflare is a transparent byte forwarder (TCP tunnel mode), cannot decrypt. ~128-bit post-quantum under Grover. |
| **Authentication** | `Authorization: <OWNER_TOKEN>` header | Required on `/lock` and `/unlock`. |
| **Password verification** | SHA-256 hash in `.env` (constant-time compare) | Wrong password → 401, no typing attempted. |
| **On Mac (after TLS terminates)** | Password in memory briefly, typed via Quartz | No `osascript`, no `argv`, no `ps` exposure. |
| **At rest (OWNER_TOKEN, PASSWORD_HASH)** | `.env` (mode 0600) | 32-byte url-safe token, SHA-256 hash. |

### What this does **not** protect against

- **A compromised iPhone** that has both the OWNER_TOKEN and can reach the tunnel can unlock the Mac.
- **A compromised Mac user account** — anyone with the user's session can read `.env` and the cert.
- **Replay within 60 seconds** (for envelope mode) — the timestamp is checked but a network attacker who captures and replays within the window gets one free unlock. For Option B (plaintext) the OWNER_TOKEN + password hash check is the only defense.

## Setup

### 1. Install dependencies

```bash
cd /Users/snyco/Github/MacAPI
touch .env
uv sync
```

### 2. First run — generates OWNER_TOKEN, Ed25519 cert, prompts for Mac password

```bash
uv run main.py
```

The first run will:
1. Generate `OWNER_TOKEN` (32-byte url-safe) → write to `.env`
2. Generate an **Ed25519** self-signed cert at `certs/cert.pem` + key at `certs/key.pem` (mode `0600`)
3. **Prompt you for the Mac login password** (input is hidden). The password is SHA-256 hashed and stored as `PASSWORD_HASH` in `.env`. The plaintext is never written to disk.
4. Print the cert's SHA-256 fingerprint — **this is what you pin in the iOS Shortcut**.

The server listens on `0.0.0.0:2201` with TLS 1.3 + AES-256-GCM only. OWNER_TOKEN, PASSWORD_HASH, and the cert persist across restarts.

### 3. Install Cloudflare Tunnel

```bash
brew install cloudflared
cloudflared tunnel login
cloudflared tunnel create macapi
```

### 4. Configure the tunnel — TCP mode (not HTTP!)

Edit `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>            # from `cloudflared tunnel create` output
credentials-file: /Users/<you>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: macapi.example.com
    service: tcp://localhost:2201
  - service: http_status:404
```

Then route DNS:

```bash
cloudflared tunnel route dns macapi macapi.example.com
```

**Why TCP, not HTTPS:** In HTTPS mode, Cloudflare terminates TLS at the edge and sees your password in plaintext. In TCP mode, Cloudflare just forwards the raw encrypted bytes — the TLS connection is end-to-end between the iPhone and the Mac. Cloudflare can see packet sizes and timing metadata but not the contents.

### 5. Run the tunnel

```bash
cloudflared tunnel run macapi
```

Or as a launchd service:

```bash
sudo cloudflared service install
```

## iOS Shortcut — build steps

The iPhone has to trust the Mac's Ed25519 cert. There are two ways; **pinning the SHA-256 fingerprint in the Shortcut is preferred** because it survives cert rotation as long as you re-pin.

### How to pin the cert fingerprint in the Shortcut

iOS Shortcuts has no built-in "pin cert fingerprint" field, but you can do it with a small **"If" check** against the response. The trick: after the cert is generated, the Mac prints its SHA-256. You hardcode that as a Text constant in the Shortcut, then use the **"Get Contents of URL" → Advanced → "Headers" + a follow-up "If"** step. Concrete flow:

| # | Action | Settings |
|---|---|---|
| 1 | **Text** | Value: `<OWNER_TOKEN>` (the token from your `.env`) |
| 2 | **Ask for Input** | Prompt: `Mac Password` · Input type: Text |
| 3 | **Dictionary** | Add row: Key `owner_token` (Text) · Value: Text from step 1. Add row: Key `password` (Text) · Value: Shortcut Input from step 2. |
| 4 | **Get Contents of URL** | URL: `https://<your-tunnel-hostname>/unlock` · Method: **POST** · Headers: `Authorization: <OWNER_TOKEN>`, `Content-Type: application/json` · Request Body: **JSON** = dictionary from step 3 |
| 5 | **Show Result** *(optional)* | Shows the response |

If you want to be extra safe, add an "If" step that aborts the Shortcut if the response body doesn't contain `unlocked`. iOS Shortcuts can compare against the expected response.

### Alternative: install the cert on the iPhone

If you don't want to maintain a pinned fingerprint, AirDrop `certs/cert.pem` to the iPhone → install the profile (Settings → General → VPN & Device Management) → trust it (Settings → General → About → Certificate Trust Settings). The drawback: when the cert regenerates (every 365 days, or if you delete `certs/`), you have to redo this on the iPhone.

## Endpoints

### `GET /`
Health check. Returns `MacAPI is online`.

### `GET /lock`
Locks the Mac with Ctrl+Cmd+Q via Quartz. Requires `Authorization: <OWNER_TOKEN>`.

### `POST /unlock`
SHA-256-checks the password against `PASSWORD_HASH`, then types it (only if the screen is locked). Body:

```json
{ "password": "the-mac-password" }
```

The `Authorization: <OWNER_TOKEN>` header is required. If the header is wrong → 401. If the password doesn't hash to `PASSWORD_HASH` → 401. If both pass and the screen is locked → Quartz types the password and presses Return.

## Regenerate the cert

```bash
rm certs/cert.pem certs/key.pem
uv run main.py
```

You'll get a new Ed25519 cert with a new SHA-256. Update the iOS Shortcut's pinned fingerprint (or re-AirDrop the new cert to the iPhone).

To upgrade to ML-DSA-87 when iOS gains TLS support for it, change `ed25519.Ed25519PrivateKey.generate()` in `cert.py` back to shelling out to `openssl genpkey -algorithm ml-dsa-87`. The rest of the stack (TLS 1.3, AES-256-GCM, hash check) is unchanged.

## Reset the password hash

If the Mac login password changes:

```bash
# Remove the old hash from .env (uv run python -c ... or edit)
sed -i '' '/^PASSWORD_HASH=/d' .env
uv run main.py        # will prompt for the new password again
```

## Running as a launchd service

```bash
cp com.user.macapi.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.user.macapi.plist
```

OWNER_TOKEN, PASSWORD_HASH, the cert, and the Keychain entry all persist across restarts. The `PASSWORD_HASH` is read from `.env` at startup; no interactive prompt on subsequent runs.

## Testing

```bash
uv run pytest
```

76 tests cover:
- `test_crypto.py` — AES-256-GCM envelope (Option A, retained for future use)
- `test_keychain.py` — real Keychain roundtrip, auto-cleanup
- `test_password_hash.py` — hash + constant-time verify
- `test_typer.py` — Quartz keyboard event mocking
- `test_server.py` — both envelope (Option A) and plaintext (Option B) unlock flows, all auth-hash rejection paths
- `test_cert.py` — Ed25519 generation, TLS 1.3 context, AES-256-GCM first cipher, TLS 1.2 rejection
