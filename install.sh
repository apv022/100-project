#!/usr/bin/env bash
# Install (or update) the pill dispenser web app on a Raspberry Pi.
# Safe to run again: after `git pull`, just run ./install.sh to update.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE=pill-dispenser
PORT="${PILL_PORT:-5000}"
fail() { echo; echo "ERROR: $*" >&2; exit 1; }

# 1. Checks
[ "$(id -u)" -ne 0 ] || fail "Run as your normal user, not with sudo. The script calls sudo itself."
if [ "${FORCE:-0}" != "1" ] && ! grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null; then
  fail "This does not look like a Raspberry Pi. (To install anyway: FORCE=1 ./install.sh)"
fi
command -v sudo >/dev/null || fail "sudo is required."

# 2. System packages
echo "==> Installing system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip curl tesseract-ocr tesseract-ocr-eng \
  || fail "apt install failed. Check the internet connection and run ./install.sh again."

# 3. Python environment
echo "==> Setting up Python environment"
[ -x "$REPO/venv/bin/python" ] || python3 -m venv "$REPO/venv"
"$REPO/venv/bin/pip" install -q --upgrade pip
"$REPO/venv/bin/pip" install -q -r "$REPO/requirements.txt" \
  || fail "pip install failed. Check the internet connection and run ./install.sh again."
mkdir -p "$REPO/data"

# 4. systemd service (starts on boot, restarts on crash)
echo "==> Installing the $SERVICE service"
sed -e "s|@USER@|$(id -un)|g" -e "s|@REPO@|$REPO|g" -e "s|@PORT@|$PORT|g" \
  "$REPO/deploy/pill-dispenser.service" | sudo tee /etc/systemd/system/$SERVICE.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable -q $SERVICE
sudo systemctl restart $SERVICE

# 5. Check it answers
echo "==> Waiting for the app"
ok=0
for _ in $(seq 1 20); do
  if curl -fs -o /dev/null "http://127.0.0.1:$PORT/api/state"; then ok=1; break; fi
  sleep 1
done

echo
echo "================ Summary ================"
if [ $ok = 1 ]; then
  echo "App is RUNNING on http://127.0.0.1:$PORT (localhost only)"
else
  echo "App did NOT respond. See: journalctl -u $SERVICE -e"
fi
echo "Phone access over Tailscale (if not set up yet): sudo tailscale serve --bg $PORT"
echo "Update later: git pull && ./install.sh"
[ $ok = 1 ] || exit 1
