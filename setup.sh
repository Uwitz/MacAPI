#!/usr/bin/env bash
# setup.sh — one-shot setup for MacAPI
#
# What it does:
#   1. Installs uv dependencies
#   2. Creates ~/Library/Application Support/MacAPI/ (mode 700) for the
#      cert, key, and config.env (mode 600) — hidden from the home dir
#   3. Generates an Ed25519 self-signed cert (mode 600 on the key)
#   4. Generates OWNER_TOKEN
#   5. Prompts for the Mac login password → SHA-256 stored as PASSWORD_HASH
#   6. Writes ~/Library/LaunchAgents/com.user.macapi.plist so the server
#      starts at login and stays running
#   7. Loads the LaunchAgent
#
# Idempotent: re-running won't clobber an existing OWNER_TOKEN or
# PASSWORD_HASH unless you confirm.
#
# Usage:
#   cd /path/to/MacAPI && ./setup.sh
#
# Or from anywhere:
#   /path/to/MacAPI/setup.sh /path/to/MacAPI

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

PROJECT_DIR=""
LAUNCH_AGENT_OPT=""

for arg in "$@"; do
    case "$arg" in
        --boot)    LAUNCH_AGENT_OPT="y" ;;
        --no-boot) LAUNCH_AGENT_OPT="n" ;;
        -*)
            echo "Unknown flag: $arg" >&2
            echo "Usage: $0 [--boot|--no-boot] [project_dir]" >&2
            exit 1
            ;;
        *)
            PROJECT_DIR="$arg"
            ;;
    esac
done

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
USERNAME="$(whoami)"
HOME_DIR="$HOME"
APP_SUPPORT="$HOME_DIR/Library/Application Support/MacAPI"
CERT_DIR="$APP_SUPPORT/certs"
LOG_DIR="$APP_SUPPORT/logs"
ENV_FILE="$APP_SUPPORT/config.env"
PLIST_DEST="$HOME_DIR/Library/LaunchAgents/com.user.macapi.plist"
PY="$PROJECT_DIR/.venv/bin/python"

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

if [[ ! -d "$PROJECT_DIR" ]]; then
    echo "ERROR: project directory not found: $PROJECT_DIR" >&2
    exit 1
fi

if [[ ! -f "$PROJECT_DIR/main.py" ]]; then
    echo "ERROR: main.py not found in $PROJECT_DIR" >&2
    echo "       Pass the project dir as the first argument." >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# uv location
# ---------------------------------------------------------------------------

if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
elif [[ -x "$HOME_DIR/.local/bin/uv" ]]; then
    UV_BIN="$HOME_DIR/.local/bin/uv"
elif [[ -x /opt/homebrew/bin/uv ]]; then
    UV_BIN=/opt/homebrew/bin/uv
elif [[ -x /usr/local/bin/uv ]]; then
    UV_BIN=/usr/local/bin/uv
else
    echo "ERROR: uv not found. Install it: https://docs.astral.sh/uv/" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 1. Install dependencies
# ---------------------------------------------------------------------------

echo "==> Installing dependencies with uv"
( cd "$PROJECT_DIR" && "$UV_BIN" sync )

# ---------------------------------------------------------------------------
# 2. Create hidden app-support directory
# ---------------------------------------------------------------------------

echo "==> Creating $APP_SUPPORT (mode 700)"
mkdir -p "$APP_SUPPORT" "$CERT_DIR" "$LOG_DIR"
chmod 700 "$APP_SUPPORT" "$CERT_DIR" "$LOG_DIR"

# ---------------------------------------------------------------------------
# 3. Cert (Ed25519, self-signed) — migrate from project or generate fresh
# ---------------------------------------------------------------------------

if [[ -f "$CERT_DIR/cert.pem" && -f "$CERT_DIR/key.pem" ]]; then
    echo "==> Cert already exists at $CERT_DIR/cert.pem, skipping"
elif [[ -f "$PROJECT_DIR/certs/cert.pem" && -f "$PROJECT_DIR/certs/key.pem" ]]; then
    echo "==> Migrating existing cert from $PROJECT_DIR/certs/ to $CERT_DIR/"
    cp "$PROJECT_DIR/certs/cert.pem" "$CERT_DIR/cert.pem"
    cp "$PROJECT_DIR/certs/key.pem" "$CERT_DIR/key.pem"
    chmod 600 "$CERT_DIR/key.pem"
    chmod 644 "$CERT_DIR/cert.pem"
else
    echo "==> Generating Ed25519 self-signed cert"
    "$PY" -c "
from cert import generate_self_signed_cert
generate_self_signed_cert('$CERT_DIR/cert.pem', '$CERT_DIR/key.pem')
"
    chmod 600 "$CERT_DIR/key.pem"
    chmod 644 "$CERT_DIR/cert.pem"
fi

# ---------------------------------------------------------------------------
# 4. OWNER_TOKEN + PASSWORD_HASH — migrate from project .env or fresh
# ---------------------------------------------------------------------------

EXISTING_TOKEN=""
EXISTING_HASH=""
if [[ -f "$ENV_FILE" ]]; then
    EXISTING_TOKEN=$(grep '^OWNER_TOKEN=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)
    EXISTING_HASH=$(grep '^PASSWORD_HASH=' "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true)
elif [[ -f "$PROJECT_DIR/.env" ]]; then
    echo "==> Migrating OWNER_TOKEN and PASSWORD_HASH from $PROJECT_DIR/.env"
    EXISTING_TOKEN=$(grep '^OWNER_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)
    EXISTING_HASH=$(grep '^PASSWORD_HASH=' "$PROJECT_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2- || true)
fi

if [[ -n "$EXISTING_TOKEN" && -n "$EXISTING_HASH" ]]; then
    echo "==> Found existing values"
    echo "    OWNER_TOKEN: ${EXISTING_TOKEN:0:8}...  PASSWORD_HASH: ${EXISTING_HASH:0:8}..."
    read -r -p "    Keep these values? [Y/n] " REPLY
    REPLY="${REPLY:-Y}"
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        OWNER_TOKEN="$EXISTING_TOKEN"
        PASSWORD_HASH="$EXISTING_HASH"
    else
        REGEN=1
    fi
fi

if [[ -z "${OWNER_TOKEN:-}" ]]; then
    OWNER_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "==> Generated OWNER_TOKEN: $OWNER_TOKEN"
fi

if [[ -z "${PASSWORD_HASH:-}" ]]; then
    echo "==> Enter your Mac login password (used to verify unlock requests)"
    echo "    Input is hidden. Paste from clipboard works too (Cmd-V, then Enter)."
    unset MAC_PASSWORD
    while [[ -z "${MAC_PASSWORD:-}" ]]; do
        read -r -s -p "    Mac password: " MAC_PASSWORD
        echo
        if [[ -z "$MAC_PASSWORD" ]]; then
            echo "    (empty — try again)"
        fi
    done
    PASSWORD_HASH=$(printf '%s' "$MAC_PASSWORD" | shasum -a 256 | awk '{print $1}')
    unset MAC_PASSWORD
    echo "==> Hashed: ${PASSWORD_HASH:0:16}..."
fi

# ---------------------------------------------------------------------------
# 5. Write config.env (mode 600)
# ---------------------------------------------------------------------------

echo "==> Writing $ENV_FILE (mode 600)"
{
    echo "OWNER_TOKEN=$OWNER_TOKEN"
    echo "PASSWORD_HASH=$PASSWORD_HASH"
    echo "TLS_CERT=$CERT_DIR/cert.pem"
    echo "TLS_KEY=$CERT_DIR/key.pem"
    echo "HOST=0.0.0.0"
    echo "PORT=2201"
} > "$ENV_FILE"
chmod 600 "$ENV_FILE"

# ---------------------------------------------------------------------------
# 6. Install LaunchAgent (boot on login) — only if user opts in
# ---------------------------------------------------------------------------

LAUNCH_AGENT_INSTALLED=0

if [[ -z "${LAUNCH_AGENT_OPT:-}" ]]; then
    echo ""
    echo "==> Start automatically on login?"
    echo "    YES  → installs a LaunchAgent so the server runs in the background"
    echo "           and auto-restarts on login. Recommended for a Mac you control."
    echo "    NO   → you'll need to run 'uv run main.py' manually (or set this up"
    echo "           yourself) each time you want the server running."
    if [[ -f "$PLIST_DEST" ]]; then
        echo "    NOTE: an existing LaunchAgent is already at $PLIST_DEST"
    fi
    read -r -p "    Install LaunchAgent? [Y/n] " REPLY
    REPLY="${REPLY:-Y}"
    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        LAUNCH_AGENT_OPT="y"
    else
        LAUNCH_AGENT_OPT="n"
    fi
fi

if [[ "$LAUNCH_AGENT_OPT" == "y" ]]; then
    echo "==> Writing $PLIST_DEST"
    cat > "$PLIST_DEST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.macapi</string>
    <key>ProgramArguments</key>
    <array>
        <string>$UV_BIN</string>
        <string>run</string>
        <string>--project</string>
        <string>$PROJECT_DIR</string>
        <string>main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>$HOME_DIR/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>OWNER_TOKEN</key>
        <string>$OWNER_TOKEN</string>
        <key>PASSWORD_HASH</key>
        <string>$PASSWORD_HASH</string>
        <key>TLS_CERT</key>
        <string>$CERT_DIR/cert.pem</string>
        <key>TLS_KEY</key>
        <string>$CERT_DIR/key.pem</string>
        <key>HOST</key>
        <string>0.0.0.0</string>
        <key>PORT</key>
        <string>2201</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/server.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/server.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF
    chmod 644 "$PLIST_DEST"

    echo "==> Loading LaunchAgent com.user.macapi"
    launchctl bootout "gui/$(id -u)/com.user.macapi" 2>/dev/null || true
    launchctl bootstrap "gui/$(id -u)" "$PLIST_DEST" 2>/dev/null || \
        launchctl load "$PLIST_DEST" 2>/dev/null || \
        echo "    (could not load LaunchAgent — load it manually with: launchctl load $PLIST_DEST)"

    LAUNCH_AGENT_INSTALLED=1
else
    echo "==> Skipping LaunchAgent install (you chose not to auto-start on login)"
    if [[ -f "$PLIST_DEST" ]]; then
        echo "    Unloading existing LaunchAgent at $PLIST_DEST..."
        launchctl bootout "gui/$(id -u)/com.user.macapi" 2>/dev/null || true
        rm -f "$PLIST_DEST"
        echo "    Removed $PLIST_DEST"
    fi
fi

# Give launchd a moment to start it
sleep 1

# ---------------------------------------------------------------------------
# 8. Summary
# ---------------------------------------------------------------------------

echo ""
echo "================================================================"
echo "  MacAPI setup complete"
echo "================================================================"
echo "  Config:        $ENV_FILE (mode 600)"
echo "  Cert:          $CERT_DIR/cert.pem"
echo "  Key:           $CERT_DIR/key.pem (mode 600)"
echo "  Logs:          $LOG_DIR/server.log"
if [[ "$LAUNCH_AGENT_INSTALLED" == "1" ]]; then
    echo "  LaunchAgent:   $PLIST_DEST (auto-starts on login)"
    echo ""
    echo "  Server is now running in the background and will auto-start on login."
else
    echo "  LaunchAgent:   not installed (run 'uv run main.py' manually)"
    echo ""
    echo "  To start the server manually: cd $PROJECT_DIR && uv run main.py"
fi
echo ""
echo "  OWNER_TOKEN:   $OWNER_TOKEN"
echo "                 (paste this into your iOS Shortcut's Authorization header)"
echo ""
echo "  Useful commands:"
echo "    tail -f $LOG_DIR/server.log     # live logs"
echo "    launchctl list | grep macapi    # process status (if LaunchAgent installed)"
echo "    launchctl kickstart -k gui/\$(id -u)/com.user.macapi   # restart"
echo "    launchctl bootout gui/\$(id -u)/com.user.macapi        # stop"
echo "================================================================"
