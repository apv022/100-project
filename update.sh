#!/usr/bin/env bash
# Pull the latest code, refresh Python packages, restart the app.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO"
git pull --ff-only
"$REPO/venv/bin/pip" install -r requirements.txt
sed -e "s|@USER@|$(id -un)|g" -e "s|@REPO@|$REPO|g" deploy/pill-dispenser.service \
  | sudo tee /etc/systemd/system/pill-dispenser.service >/dev/null
sed "s|@REPO@|$REPO|g" deploy/pill-kiosk.desktop > "$HOME/.config/autostart/pill-kiosk.desktop"
chmod +x deploy/kiosk.sh
sudo systemctl daemon-reload
sudo systemctl restart pill-dispenser
echo "Updated and restarted. Reload the browser (or reboot) to see UI changes."
