#!/usr/bin/env bash
# One-shot installer for the pill dispenser. Safe to run more than once.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fail() { echo; echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; WARNINGS+=("$*"); }
WARNINGS=()

# 1. Sanity checks
[ "$(id -u)" -ne 0 ] || fail "Run as your normal user (not root / not with sudo). The script calls sudo itself."
if [ "${FORCE:-0}" != "1" ] && ! grep -qi "raspberry pi" /proc/device-tree/model 2>/dev/null; then
  fail "This does not look like a Raspberry Pi. (To install anyway: FORCE=1 ./install.sh)"
fi
command -v sudo >/dev/null || fail "sudo is required."

PORT="$(grep -E '^PORT' "$REPO/config.py" | grep -oE '"[0-9]+"' | tr -d '"' | head -1)"; PORT="${PORT:-5000}"

# 2. System packages
echo "==> Installing system packages"
sudo apt-get update
if apt-cache show chromium >/dev/null 2>&1; then CHROMIUM=chromium; else CHROMIUM=chromium-browser; fi
sudo apt-get install -y python3-venv python3-pip pigpio python3-pigpio "$CHROMIUM" unclutter git curl \
  || fail "apt install failed. Check your internet connection and run ./install.sh again."

# 3. pigpiod (smooth servo signals)
echo "==> Enabling pigpiod"
sudo systemctl enable --now pigpiod || warn "Could not start pigpiod. Servos will not move until it runs (sudo systemctl status pigpiod)."

# 4. Python virtual environment
echo "==> Creating Python environment"
python3 -m venv --system-site-packages "$REPO/venv"
"$REPO/venv/bin/pip" install --upgrade pip
"$REPO/venv/bin/pip" install -r "$REPO/requirements.txt" || fail "pip install failed. Check your internet connection and run ./install.sh again."
mkdir -p "$REPO/data"

# 5. systemd service for the app
echo "==> Installing the app service"
sed -e "s|@USER@|$(id -un)|g" -e "s|@REPO@|$REPO|g" "$REPO/deploy/pill-dispenser.service" \
  | sudo tee /etc/systemd/system/pill-dispenser.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable pill-dispenser
sudo systemctl restart pill-dispenser

# 6. Kiosk browser at desktop login, no screen blanking
echo "==> Setting up kiosk mode"
chmod +x "$REPO/deploy/kiosk.sh" "$REPO/install.sh" "$REPO/update.sh"
mkdir -p "$HOME/.config/autostart"
sed "s|@REPO@|$REPO|g" "$REPO/deploy/pill-kiosk.desktop" > "$HOME/.config/autostart/pill-kiosk.desktop"
sudo raspi-config nonint do_blanking 1 || warn "Could not turn off screen blanking (Raspberry Pi Configuration > Display > Screen Blanking)."

# 7. Summary
sleep 2
IP="$(hostname -I | awk '{print $1}')"
echo
echo "================ Install summary ================"
echo "Installed: system packages, pigpiod, Python venv, pill-dispenser service, kiosk autostart"
if systemctl is-active --quiet pill-dispenser; then echo "App service: RUNNING"; else echo "App service: NOT running (see: journalctl -u pill-dispenser -e)"; fi
echo "Address on the Pi:   http://localhost:$PORT"
[ -n "$IP" ] && echo "Address on your LAN: http://$IP:$PORT"
for w in "${WARNINGS[@]:-}"; do [ -n "$w" ] && echo "Warning: $w"; done
echo
echo "Next: reboot (sudo reboot) to start the full-screen kiosk."
echo "If something failed: see Troubleshooting in README.md, or run ./install.sh again."
