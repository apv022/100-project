"""All settings for the pill dispenser in one place."""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def _on_raspberry_pi():
    try:
        with open("/proc/device-tree/model") as f:
            return "raspberry pi" in f.read().lower()
    except OSError:
        return False


# Simulation mode: no servos are touched, moves are just logged.
# Default: ON when not running on a Raspberry Pi (e.g. a laptop), OFF on a Pi.
# Override with an environment variable:  PILL_SIMULATION=1  or  PILL_SIMULATION=0
_env_sim = os.environ.get("PILL_SIMULATION")
SIMULATION = (not _on_raspberry_pi()) if _env_sim is None else _env_sim == "1"

# Web server. Kiosk browser points at http://localhost:PORT
HOST = os.environ.get("PILL_HOST", "127.0.0.1")  # localhost only; expose via `tailscale serve`, not 0.0.0.0
PORT = int(os.environ.get("PILL_PORT", "5000"))

# One block per pill / hopper. Each unit has its own servo.
#   pin           BCM GPIO number of the servo signal wire (pigpio: any GPIO works)
#   open_angle    disc angle where the pocket sits over the exit hole (pill drops)
#   closed_angle  disc angle where the pocket sits under the hopper (loading)
#   capacity      how many pills a full hopper holds (used by the Refill button)
PILLS = [
    {"id": "pill1", "name": "Pill A", "color": "#ff6b6b",
     "pin": 18, "open_angle": 90, "closed_angle": 0, "capacity": 30},
    {"id": "pill2", "name": "Pill B", "color": "#4dabf7",
     "pin": 12, "open_angle": 90, "closed_angle": 0, "capacity": 30},
    {"id": "pill3", "name": "Pill C", "color": "#ffd43b",
     "pin": 13, "open_angle": 90, "closed_angle": 0, "capacity": 30},
]

LOW_STOCK_THRESHOLD = 5   # show a warning at or below this many pills

# Servo motion (seconds)
SERVO_MOVE_TIME = 0.8     # time allowed for the disc to reach an angle
SERVO_HOLD_TIME = 0.6     # time the pocket stays over the exit hole
# Pulse widths for SG90 / MG90S class micro servos (seconds)
SERVO_MIN_PULSE = 0.0005
SERVO_MAX_PULSE = 0.0024

# Scheduler
SCHEDULER_INTERVAL = 3        # seconds between schedule checks
SCHEDULE_GRACE_MINUTES = 10   # a dose later than this after its time is skipped
                              # (so a reboot at 20:00 doesn't fire an 08:00 dose)
PAUSE_BETWEEN_PILLS = 2.0     # seconds between pills that are due together

HISTORY_LIMIT = 1000
MAX_SCHEDULE_ENTRIES = 40
