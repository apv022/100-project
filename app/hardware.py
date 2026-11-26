"""Hardware drivers. The app only talks to hardware through a Driver.

To hook up real hardware, fill in GpioDriver (or add another driver class),
put pins/settings in each container's `hw` dict and SPEAKER_HW in config.py,
then set DRIVER = "gpio" (or PILL_DRIVER=gpio in the service environment).
Every method except dispense_one may be left as a no-op: the app still works.
"""
import logging
import time

import config

log = logging.getLogger("hardware")


class DispenseError(Exception):
    """Raise this when the hardware fails (motor stall, jam, driver error...)."""


class Driver:
    name = "base"

    # --- dispensing -------------------------------------------------------
    def dispense_one(self, pill):
        """Release exactly one pill from container `pill` (dict from config.PILLS).

        Return True if a pill came out, False if a sensor is sure nothing came
        out, or raise DispenseError. Never called concurrently."""
        raise NotImplementedError

    # --- speaker ----------------------------------------------------------
    def beep(self, pattern):
        """Short sound. pattern: "dose" (pills ready), "reminder" (still not
        taken), "error" (something failed), "test"."""

    def alarm_on(self):
        """Start a continuous / repeating alarm until alarm_off()."""

    def alarm_off(self):
        """Stop the alarm."""

    # --- cup sensor (optional) ---------------------------------------------
    def cup_state(self):
        """Return "full" if pills are waiting in the cup, "empty" if the cup is
        empty (so a pending dose counts as taken), or None if there is no sensor."""
        return None

    def close(self):
        pass


class SimulatedDriver(Driver):
    name = "sim"

    def __init__(self):
        self.alarming = False

    def dispense_one(self, pill):
        log.info("[sim] dispensing one pill from %s", pill["id"])
        time.sleep(config.SIM_DISPENSE_SECONDS)
        return True

    def beep(self, pattern):
        log.info("[sim] beep: %s", pattern)

    def alarm_on(self):
        if not self.alarming:
            log.info("[sim] ALARM ON")
        self.alarming = True

    def alarm_off(self):
        if self.alarming:
            log.info("[sim] alarm off")
        self.alarming = False


class GpioDriver(Driver):
    """Placeholder for the real hardware. Pins etc. come from pill["hw"]."""
    name = "gpio"

    def __init__(self):
        # TODO: set up motor drivers, speaker/buzzer and sensors (e.g. gpiozero).
        pass

    def dispense_one(self, pill):
        # TODO: run this container's motor until one pill drops, then stop.
        raise DispenseError("GPIO driver not implemented yet")

    def beep(self, pattern):
        log.info("TODO speaker beep: %s", pattern)

    def alarm_on(self):
        log.info("TODO speaker alarm on")

    def alarm_off(self):
        log.info("TODO speaker alarm off")


DRIVERS = {"sim": SimulatedDriver, "gpio": GpioDriver}


def make_driver(name=None):
    name = name or config.DRIVER
    if name not in DRIVERS:
        raise ValueError(f"Unknown driver {name!r}; choose one of {sorted(DRIVERS)}")
    return DRIVERS[name]()


def safe(fn, *args):
    """Call a speaker/sensor method without letting a hardware error crash the app."""
    try:
        return fn(*args)
    except Exception:
        log.exception("hardware call %s failed", getattr(fn, "__name__", fn))
        return None
