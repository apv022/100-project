#!/usr/bin/env bash
# Launch Chromium full-screen on the dispenser UI. Started at desktop login.
PORT="${PILL_PORT:-5000}"
URL="http://localhost:${PORT}"

# Stop screen blanking (X11 only; harmless elsewhere) and hide the cursor.
command -v xset >/dev/null && { xset s off; xset -dpms; xset s noblank; } 2>/dev/null
command -v unclutter >/dev/null && (unclutter -idle 0.5 -root >/dev/null 2>&1 &)

# Wait for the app (up to ~60 s).
for _ in $(seq 1 60); do
  curl -fs -o /dev/null "$URL" && break
  sleep 1
done

BROWSER="$(command -v chromium || command -v chromium-browser)"
exec "$BROWSER" --kiosk --noerrdialogs --disable-infobars --check-for-update-interval=31536000 \
  --disable-session-crashed-bubble --disable-pinch --overscroll-history-navigation=0 \
  --no-first-run --password-store=basic "$URL"
