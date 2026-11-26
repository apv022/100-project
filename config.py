"""All settings for the pill dispenser in one place."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("PILL_DATA_DIR", os.path.join(BASE_DIR, "data"))

# Web server: localhost only. Reach it from other devices with `tailscale serve`.
HOST = os.environ.get("PILL_HOST", "127.0.0.1")
PORT = int(os.environ.get("PILL_PORT", "5000"))

# Which hardware driver dispenses pills (see app/hardware.py):
#   "sim"  - no hardware, just logs and waits (default until the hardware is ready)
#   "gpio" - real hardware, to be implemented in GpioDriver
DRIVER = os.environ.get("PILL_DRIVER", "sim")

# One block per pill / container. `hw` is free-form settings for the hardware
# driver (pins, motor channel, sensor pin...). Fill it in when the hardware exists.
# `name` is only a fallback label; the prescription name set in the app wins.
PILLS = [
    {"id": "pill1", "name": "Container A", "color": "#ff6b6b", "capacity": 30, "hw": {}},
    {"id": "pill2", "name": "Container B", "color": "#4dabf7", "capacity": 30, "hw": {}},
    {"id": "pill3", "name": "Container C", "color": "#ffd43b", "capacity": 30, "hw": {}},
]

LOW_STOCK_THRESHOLD = 5       # warn at or below this many pills
SIM_DISPENSE_SECONDS = 1.0    # how long a simulated dispense takes

# Scheduler
SCHEDULER_INTERVAL = 3        # seconds between schedule checks
SCHEDULE_GRACE_MINUTES = 10   # a dose later than this after its time is skipped
                              # (so a reboot at 20:00 doesn't fire an 08:00 dose)
PAUSE_BETWEEN_PILLS = 2.0     # seconds between pills that are due together

# Defaults for the Settings screen (editable in the app, stored in data/settings.json)
DEFAULT_SETTINGS = {
    "refill_reminder_time": "18:00",  # daily time to check stock and send refill reminders
    "refill_warn_days": 3,            # remind when this many days of pills or fewer are left
    "remind_after_min": 5,            # beep again if a dose hasn't been taken after this long
    "alarm_after_min": 15,            # sound the alarm + notify after this long
    "missed_after_min": 60,           # give up and mark the dose "not taken" after this long
}

# Optional phone push notifications through ntfy (https://ntfy.sh or a self-hosted
# server). Example: PILL_NTFY_URL=https://ntfy.sh/some-long-random-topic
# Off by default: notification text (medication names) is sent to that server.
NTFY_URL = os.environ.get("PILL_NTFY_URL", "")

# Prescription label scanning (OCR). Needs the `tesseract` command (install.sh
# installs tesseract-ocr).
TESSERACT_CMD = os.environ.get("PILL_TESSERACT", "tesseract")
OCR_TIMEOUT = 90                 # seconds; a Pi 3 is slow
MAX_UPLOAD_MB = 12

HISTORY_LIMIT = 1000
NOTIFICATION_LIMIT = 200
DOSE_LIMIT = 500
MAX_SCHEDULE_ENTRIES = 40
