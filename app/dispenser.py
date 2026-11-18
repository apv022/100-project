"""Servo control and the dispense routine.

One servo per pill. Only one servo ever moves at a time (a single lock), which
keeps the current draw on the servo supply low."""
import logging
import threading
import time
from datetime import datetime

import config
from . import storage

log = logging.getLogger("dispenser")

PILLS = {p["id"]: p for p in config.PILLS}


class Dispenser:
    def __init__(self):
        self._lock = threading.Lock()
        self._servos = {}
        self._factory = None
        self.active = None  # pill id currently being dispensed

    # -- hardware ---------------------------------------------------------
    def _servo(self, pill):
        if pill["id"] not in self._servos:
            from gpiozero import AngularServo
            if self._factory is None:
                from gpiozero.pins.pigpio import PiGPIOFactory
                self._factory = PiGPIOFactory()  # needs the pigpiod service
            self._servos[pill["id"]] = AngularServo(
                pill["pin"], initial_angle=None,
                min_angle=0, max_angle=180,
                min_pulse_width=config.SERVO_MIN_PULSE,
                max_pulse_width=config.SERVO_MAX_PULSE,
                pin_factory=self._factory)
        return self._servos[pill["id"]]

    def _move(self, pill, angle):
        if config.SIMULATION:
            log.info("[sim] %s servo (GPIO %s) -> %s deg", pill["name"], pill["pin"], angle)
            time.sleep(config.SERVO_MOVE_TIME / 4)
            return
        self._servo(pill).angle = angle
        time.sleep(config.SERVO_MOVE_TIME)

    def _cycle(self, pill):
        """Closed -> open (pill drops) -> closed, then release the servo."""
        self._move(pill, pill["closed_angle"])
        self._move(pill, pill["open_angle"])
        if config.SIMULATION:
            time.sleep(config.SERVO_HOLD_TIME / 4)
        else:
            time.sleep(config.SERVO_HOLD_TIME)
        self._move(pill, pill["closed_angle"])
        if not config.SIMULATION:
            self._servo(pill).angle = None  # stop pulses: no jitter, no hum

    # -- public -----------------------------------------------------------
    def dispense(self, pill_id, source="manual", wait=False):
        """Dispense one pill. Returns {"ok", "status", "message", "remaining"}.

        status: ok | busy | empty | error | unknown
        wait=False returns "busy" at once if another dispense is running;
        wait=True (scheduler) queues behind it."""
        pill = PILLS.get(pill_id)
        if pill is None:
            return _result(False, "unknown", "Unknown pill.")
        if not self._lock.acquire(blocking=wait):
            return _result(False, "busy", "Dispenser is busy, try again in a moment.")
        try:
            self.active = pill_id
            remaining = storage.get_inventory()[pill_id]
            if remaining <= 0:
                _log(pill, source, "empty")
                return _result(False, "empty", f"{pill['name']} hopper is empty.", 0)
            try:
                self._cycle(pill)
            except Exception as exc:  # hardware problem: pigpiod down, etc.
                log.exception("dispense failed")
                _log(pill, source, "error")
                return _result(False, "error", f"Servo error: {exc}", remaining)
            remaining -= 1
            storage.update("inventory", {}, lambda inv: {**storage.get_inventory(), pill_id: remaining})
            _log(pill, source, "ok")
            return _result(True, "ok", f"{pill['name']} dispensed.", remaining)
        finally:
            self.active = None
            self._lock.release()


def _log(pill, source, status):
    storage.add_history({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "pill": pill["id"], "name": pill["name"],
        "source": source, "status": status,
    })


def _result(ok, status, message, remaining=None):
    return {"ok": ok, "status": status, "message": message, "remaining": remaining}


dispenser = Dispenser()
