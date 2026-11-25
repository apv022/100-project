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
PILLS = [
    {"id": "pill1", "name": "Pill A", "color": "#ff6b6b", "capacity": 30, "hw": {}},
    {"id": "pill2", "name": "Pill B", "color": "#4dabf7", "capacity": 30, "hw": {}},
    {"id": "pill3", "name": "Pill C", "color": "#ffd43b", "capacity": 30, "hw": {}},
]

LOW_STOCK_THRESHOLD = 5       # warn at or below this many pills
SIM_DISPENSE_SECONDS = 1.0    # how long a simulated dispense takes

# Scheduler
SCHEDULER_INTERVAL = 3        # seconds between schedule checks
SCHEDULE_GRACE_MINUTES = 10   # a dose later than this after its time is skipped
                              # (so a reboot at 20:00 doesn't fire an 08:00 dose)
PAUSE_BETWEEN_PILLS = 2.0     # seconds between pills that are due together

HISTORY_LIMIT = 1000
MAX_SCHEDULE_ENTRIES = 40
