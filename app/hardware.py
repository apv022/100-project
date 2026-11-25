"""Hardware drivers. The web app only ever calls `driver.dispense_one(pill)`.

To hook up real hardware, fill in GpioDriver (or add another driver class),
put its pins/settings in each pill's `hw` dict in config.py, and set
DRIVER = "gpio" (or PILL_DRIVER=gpio in the service environment).
"""
import logging
import time

import config

log = logging.getLogger("hardware")


class DispenseError(Exception):
    """Raise this when the hardware fails (motor stall, jam, driver error...)."""


class Driver:
    name = "base"

    def dispense_one(self, pill):
        """Release exactly one pill of `pill` (a dict from config.PILLS).

        Return True if a pill was dispensed, False if the hardware is sure no
        pill came out (e.g. a drop sensor saw nothing), or raise DispenseError.
        Never called concurrently: the app runs one dispense at a time."""
        raise NotImplementedError

    def close(self):
        pass


class SimulatedDriver(Driver):
    name = "sim"

    def dispense_one(self, pill):
        log.info("[sim] dispensing one %s", pill["name"])
        time.sleep(config.SIM_DISPENSE_SECONDS)
        return True


class GpioDriver(Driver):
    """Placeholder for the real hardware. Pins etc. come from pill["hw"]."""
    name = "gpio"

    def __init__(self):
        # TODO: set up motor driver / sensors here (e.g. gpiozero devices).
        pass

    def dispense_one(self, pill):
        # TODO: run this pill's motor until one pill drops, then stop.
        raise DispenseError("GPIO driver not implemented yet")


DRIVERS = {"sim": SimulatedDriver, "gpio": GpioDriver}


def make_driver(name=None):
    name = name or config.DRIVER
    if name not in DRIVERS:
        raise ValueError(f"Unknown driver {name!r}; choose one of {sorted(DRIVERS)}")
    return DRIVERS[name]()
