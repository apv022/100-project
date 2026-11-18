# Pill Dispenser (Raspberry Pi 3 B+)

A timed dispenser for **three different pills**. Three identical units sit side by side: a hopper of one pill on a servo-turned disc with a single pill-sized pocket. The servo rotates the pocket over an exit hole, the pill drops into a shared chute and cup, then the disc turns back. A touchscreen web app sets the schedule, dispenses on demand, logs history and tracks pills remaining. No microcontroller, no weight sensor, no vibration.

> **Safety: this is a class prototype. It is NOT safe for dispensing real medication to people.** Test with candy or dummy pills only.

## Install (on the Pi)

Raspberry Pi OS Desktop, 32-bit, Pi 3 B+, internet needed for install only.

```bash
git clone <this repo's URL> pill-dispenser && cd pill-dispenser
```
```bash
./install.sh
```

Then `sudo reboot`. The app starts on boot and Chromium opens full-screen on the touchscreen. From a phone on the same network, open the address printed at the end of the install.

## Update

```bash
git pull && ./update.sh
```

## Wiring

Each servo has its own signal wire; power comes from a **separate 5 V supply (at least 2 A)**, never from the Pi.

| Servo | Signal (orange/yellow) | Power red | Ground brown/black |
|-------|------------------------|-----------|--------------------|
| Pill A | GPIO 18 | supply +5 V | supply GND |
| Pill B | GPIO 12 | supply +5 V | supply GND |
| Pill C | GPIO 13 | supply +5 V | supply GND |

- **Common ground:** connect the supply's GND to a Pi ground pin. Without it the signals do nothing.
- **Do not** connect the supply's +5 V to the Pi's 5 V pin. The Pi keeps its own power supply.
- The software moves one servo at a time, never all three at once.
- Pins, angles, names and hopper capacity are in `config.py`.

## Using it

- **Home:** next dose time and a big *Dispense Now* button per pill (asks for confirmation).
- **Schedule:** add, edit, switch on/off, delete times, each tied to one pill. Pills due at the same minute dispense one after another.
- **History:** every dispense with timestamp, pill, scheduled or manual, and failures (empty hopper, servo error).
- **Settings:** pills remaining per hopper, with Refill (sets to full) and +/- 1.

Each scheduled time fires once per day, up to 10 minutes late (so a reboot does not fire old doses). Check the Pi's timezone: `sudo raspi-config` > Localisation.

## Run on a laptop (simulation)

No servos needed. Simulation turns on automatically when not on a Raspberry Pi.

```bash
python3 -m venv venv && venv/bin/pip install -r requirements.txt
```
```bash
PILL_SIMULATION=1 venv/bin/python -m app.app
```

Open http://localhost:5000. Run the tests with `PILL_SIMULATION=1 venv/bin/python -m unittest`.

## Layout

| Path | Purpose |
|------|---------|
| `config.py` | all constants: pills, pins, angles, timing, simulation, port |
| `app/app.py` | Flask routes and JSON API |
| `app/dispenser.py` | servo control (gpiozero + pigpio) and the dispense routine |
| `app/scheduler.py` | background schedule checker |
| `app/storage.py` | JSON files, safe write (temp file then rename) |
| `app/templates`, `app/static` | touchscreen UI (Alpine JS vendored locally, fully offline) |
| `data/` | `schedule.json`, `history.json`, `inventory.json`, created on first run, git-ignored |
| `deploy/` | systemd unit, kiosk launcher, autostart entry |
| `cad/` | 3D print files and design brief |
| `tests/` | unit tests |

## Troubleshooting

- **Servo jitters or does nothing:** `systemctl status pigpiod`; start it with `sudo systemctl enable --now pigpiod`. Check the common ground.
- **Pi reboots or freezes when servos move:** servos must use the separate 5 V supply. Check the supply is at least 2 A.
- **History shows "Error" with a servo message:** pigpiod is not running, or the wrong pin in `config.py`.
- **Pills jam or double-drop:** adjust pocket depth and diameter first, then add a paddle, then steepen the hopper. Tune each pocket separately. Open/closed angles are in `config.py`.
- **Blank screen or no browser:** reboot after install; run `deploy/kiosk.sh` from a terminal on the desktop to see errors. The app itself: `journalctl -u pill-dispenser -e`.
- **Screen goes dark:** `sudo raspi-config` > Display > Screen Blanking > Off.
- **Install failed:** check internet, then run `./install.sh` again (it is safe to repeat).
- **Wrong times:** set the Pi timezone (see above).
