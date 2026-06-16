# Irrigation Project TODO

## 1. Python 3 Migration

* [x] Port `irigatie-control.py` from Python 2 to Python 3.
* [x] Replace `ConfigParser` with `configparser`.
* [x] Replace Python 2 octal literals like `0777` with `0o777`.
* [x] Audit all socket handling for `bytes` vs `str`.
* [x] Replace `threading.Event.isSet()` with `is_set()`.
* [x] Verify `pymysql` compatibility under Python 3.
* [x] Verify `gpiozero` behavior under Python 3.
* [x] Keep the socket protocol compatible with the old `client.py`.
* [x] Port `client.py` to Python 3.
* [x] Test with relays disconnected or mocked before live deployment.
* [x] Keep the old Python 2 version as rollback.

## 2. Verify Repository Completeness

* [x] Confirm the repo contains all project source files from `/home/pi/irigatie`.
* [x] Confirm systemd unit files are tracked somewhere sensible, for example:

    * [x] `systemd-scripts/irigatie.service`
    * [x] `systemd-scripts/irigatie-online-rain.service`
    * [x] `systemd-scripts/irigatie-online-rain.timer`
* [ ] Confirm `irigatie.conf` is handled intentionally:

    * [ ] tracked if it contains no secrets
    * [ ] replaced with `irigatie.conf.example` if it contains secrets
* [ ] Confirm DB schema is tracked, without live data or secrets.
* [ ] Confirm `.gitignore` excludes:

    * [ ] secrets
    * [ ] runtime state files
    * [ ] logs
    * [ ] Python cache files
    * [ ] local IDE files if desired
* [ ] Add or update `README.md` if missing or stale.

## 3. Normalize systemd Units

* [x] Keep real unit files directly in `/etc/systemd/system/`.
* [x] Keep `.wants/` entries as symlinks only.
* [x] Change main service from `Type=idle` to `Type=simple`.
* [x] Add clean shutdown handling through `SIGTERM`.
* [x] Remove `ExecStop=/home/pi/irigatie/client.py -c SHUTDOWN` after confirming it is no longer needed.
* [x] Add `TimeoutStopSec=20`.
* [x] Use `Restart=on-failure`.
* [x] Keep or add `RestartSec=3`.
* [x] Verify unit state:

```bash
systemctl cat irigatie.service
systemctl show irigatie.service -p FragmentPath -p UnitFileState -p LoadState
```

## 4. Add Boot-Time Relay Safety

* [x] Create a minimal `relays_off.py`.
* [x] Create `irigatie-relays-off.service`.
* [x] Make it run early at boot before `irigatie.service`.
* [ ] Force these OFF at boot:

    * [x] transformer relay
    * [x] zone 1 relay
    * [x] zone 2 relay
    * [x] zone 3 relay
    * [x] zone 4 relay
* [ ] Enable it with systemd.
* [ ] Test by rebooting while no watering is active.

## 5. Add Daemon Startup Safety

* [x] At the very start of `irigatie-control.py`, force all relays OFF.
* [ ] Do this before:

    * [x] opening the socket
    * [x] accepting commands
    * [x] registering button callbacks
    * [x] starting LED status thread
    * [x] starting schedules
* [ ] Mark any previously running job as interrupted.
* [x] Log startup relay reset to syslog.

## 6. Wrap Relay Control in `try/finally`

* [ ] Replace raw patterns like:

```python
relay.on()
time.sleep(duration)
relay.off()
```

with:

```python
try:
    relay.on()
    time.sleep(duration)
finally:
    relay.off()
```

* [ ] Also wrap transformer control.
* [ ] Ensure transformer turns off even if:

    * [ ] DB query fails
    * [ ] socket command fails
    * [ ] exception occurs during watering
    * [ ] service is stopped
    * [ ] user presses Ctrl+C

## 7. Replace Global `program_activ` with a Proper Lock

* [ ] Add a `threading.Lock()`.
* [ ] Ensure only one watering job can run at a time.
* [ ] Protect both manual and scheduled programs with the same lock.
* [ ] Avoid race conditions between:

    * [ ] physical buttons
    * [ ] socket commands
    * [ ] future internal scheduler
    * [ ] systemd restarts

## 8. Replace Fire-and-Forget Threads with a Command Queue

* [ ] Create one controller worker thread.
* [ ] Make buttons, socket commands, and scheduler enqueue commands.
* [ ] Make the worker execute commands one at a time.
* [ ] Queue commands like:

    * [ ] `START scheduled_program_id`
    * [ ] `EXEC manual_program_id`
    * [ ] `STOP`
    * [ ] `SHUTDOWN`
* [ ] Reject or ignore commands when one is already running, depending on policy.
* [ ] Log rejected commands.

## 9. Add Hard Runtime Limits

* [ ] Add config values:

```ini
[Safety]
MAX_ZONE_SECONDS = 3600
MAX_PROGRAM_SECONDS = 7200
```

* [ ] Refuse absurd DB durations.
* [ ] Clamp or abort any zone duration above the configured maximum.
* [ ] Log safety aborts.
* [ ] Make sure DB corruption cannot water forever.

## 10. Add Runtime State Tracking

* [ ] Add a DB table or local state file recording:

    * [ ] current state: `idle`, `running`, `stopping`, `error`
    * [ ] source: `manual`, `scheduled`, `socket`
    * [ ] program id
    * [ ] route/zone id
    * [ ] started time
    * [ ] expected end time
    * [ ] heartbeat time
* [ ] On daemon startup:

    * [ ] if previous state was `running`, mark it `interrupted`
    * [ ] force all relays OFF
* [ ] During watering, update heartbeat periodically.
* [ ] On normal finish, mark state as `idle`.

## 11. Replace Cron Scheduling

* [ ] Stop using cron for irrigation schedules.
* [ ] Move schedule checking into the daemon.
* [ ] Make the daemon periodically query DB for due scheduled programs.
* [ ] Use a loop interval of 15-30 seconds.
* [ ] Ensure missed schedules after reboot are handled deliberately:

    * [ ] skip if too old
    * [ ] run only if still inside allowed window
* [ ] Add per-program allowed window, for example:

```text
scheduled at 06:00
valid until 06:20
```

## 12. Keep systemd Timers Only for Helper Jobs

* [x] Keep `irigatie-online-rain.timer` for Open-Meteo updates.
* [ ] Do not use timers or cron to directly control relays.
* [x] Any timer-triggered action should call the daemon/client, not GPIO directly.

## 13. Refactor Repeated Zone Code

* [ ] Replace four copy-pasted zone blocks with a loop.
* [ ] Create a zone map:

```python
zones = {
    1: relay_1,
    2: relay_2,
    3: relay_3,
    4: relay_4,
}
```

* [ ] Store zone metadata from DB:

    * [ ] id
    * [ ] name
    * [ ] active flag
    * [ ] relay
* [ ] Use a common function:

```python
run_zone(zone_id, duration_seconds)
```

## 14. Split Hardware Control from Business Logic

* [ ] Create a hardware abstraction layer.
* [ ] Suggested files:

```text
gpio_hw.py
controller.py
db.py
config.py
rain.py
socket_server.py
```

* [ ] `gpio_hw.py` owns relays, buttons, and LED.
* [ ] `controller.py` decides what to water.
* [ ] `db.py` owns SQL queries.
* [ ] `rain.py` owns rain accounting.
* [ ] `socket_server.py` owns command parsing.

## 15. Add Mock GPIO Mode

* [ ] Add config:

```ini
[Hardware Control]
GPIO_BACKEND = real
```

or:

```ini
[Hardware Control]
GPIO_BACKEND = mock
```

* [ ] In mock mode:

    * [ ] relay actions only log messages
    * [ ] button setup is skipped or simulated
    * [ ] LED actions are ignored or logged
* [ ] Use mock mode for development on Mac or VM.

## 16. Improve SQL Safety

* [ ] Replace string-concatenated SQL with parameterized queries.
* [ ] Audit all DB writes.
* [ ] Use short-lived cursors.
* [ ] Avoid one shared global cursor across threads.
* [ ] Prefer opening DB connections per operation or using a small safe wrapper.
* [ ] Log SQL errors clearly.

## 17. Normalize Rain Units

* [ ] Decide final unit: millimeters.
* [ ] Treat hardware pulses as input conversion only.
* [ ] Rename mentally or in DB:

    * [ ] `ploaie` -> `rain_credit_mm`
    * [ ] `max_ploaie` -> `rain_threshold_mm`
* [ ] If DB rename is too risky, keep old columns but use clear variable names in code.
* [ ] Convert tipping bucket pulses using:

```text
mm = pulses * 0.2794
```

## 18. Separate Rain Sources

* [ ] Do not let hardware sensor and API both write directly into `programari.ploaie`.
* [ ] Add separate rain logs:

    * [ ] API rain events
    * [ ] hardware rain events
    * [ ] manual rain corrections
* [ ] Use only one selected source for irrigation credit, or a deliberate weighted combination.
* [ ] Add config:

```ini
[Rain]
SOURCE = openmeteo
```

Possible values:

```text
hardware
openmeteo
manual
hybrid
disabled
```

## 19. Add Rain Event Logging

* [ ] Add table:

```sql
rain_events
```

Suggested fields:

```text
id
source
event_time
amount_mm
raw_value
created_at
```

* [ ] Log Open-Meteo imports.
* [ ] Later log hardware sensor pulses.
* [ ] Use this to compare API vs physical sensor accuracy.

## 20. Add Watering Event Logging

* [ ] Add table:

```sql
watering_log
```

Suggested fields:

```text
id
started_at
ended_at
source
program_id
traseu_id
planned_seconds
actual_seconds
rain_credit_mm
result
error
```

Results:

```text
completed
skipped_rain
skipped_inactive
interrupted
failed
safety_abort
```

## 21. Add Status Command

* [ ] Extend client/socket protocol with:

```text
STATUS
```

* [ ] Return:

    * [ ] daemon state
    * [ ] current program
    * [ ] current zone
    * [ ] remaining seconds
    * [ ] last rain update
    * [ ] DB status
    * [ ] relay state
* [ ] Optional later: JSON output.

## 22. Add Stop Command

* [ ] Extend protocol with:

```text
STOP
```

* [ ] It should:

    * [ ] request current job to stop
    * [ ] turn current zone off
    * [ ] turn transformer off
    * [ ] mark job as interrupted
* [ ] Avoid relying only on `SHUTDOWN`.

## 23. Harden Socket Control

* [ ] Move socket from:

```text
/tmp/python_irigatie_unix_socket
```

to:

```text
/run/irigatie/control.sock
```

* [ ] Avoid `0777`.
* [ ] Use mode `0660`.
* [ ] Restrict owner/group.
* [ ] Validate all commands strictly.
* [ ] Reject malformed commands.

## 24. Improve Logging

* [ ] Keep syslog/journald logging.
* [ ] Add consistent prefixes:

    * [ ] startup
    * [ ] shutdown
    * [ ] command received
    * [ ] watering start
    * [ ] watering stop
    * [ ] relay safety
    * [ ] DB error
    * [ ] rain update
* [ ] Avoid relying on `Deeebug` prints.
* [ ] Make debug configurable from `irigatie.conf`.

## 25. Improve Configuration

* [ ] Create `irigatie.conf.example`.
* [ ] Validate config on startup.
* [ ] Fail clearly if required config is missing.
* [ ] Print/log effective GPIO pin mapping.
* [ ] Print/log rain source mode.
* [ ] Print/log DB connection target without password.

## 26. Add Test Commands

* [ ] Add safe dry-run commands:

    * [ ] validate config
    * [ ] test DB connection
    * [ ] test socket
    * [ ] test relay mapping one by one
    * [ ] force all relays off
* [ ] Example commands:

```bash
./irigatie-control.py --check-config
./irigatie-control.py --relays-off
./client.py status
```

## 27. Fresh OS Deployment

* [ ] Do not in-place upgrade Stretch.
* [ ] Prepare new SD card with Raspberry Pi OS Legacy 32-bit Lite.
* [ ] Install Python 3 dependencies.
* [ ] Copy project from git.
* [ ] Restore config.
* [ ] Restore or connect DB.
* [ ] Test mock mode.
* [ ] Test real GPIO with valves disconnected.
* [ ] Test one short watering cycle.
* [ ] Keep old SD card as rollback.

## 28. Documentation

* [ ] Add a recovery section:

```text
If watering is stuck:
  sudo systemctl stop irigatie.service
  sudo /home/pi/irigatie/relays_off.py
```

* [ ] Add systemd commands.
* [ ] Add DB backup/restore notes.
* [ ] Add GPIO pin table.
* [ ] Add rain calibration notes.
* [ ] Add instructions for disabling online rain if hardware sensor is reinstalled.

## 29. Future Optional Improvements

* [ ] Web status page.
* [ ] Home Assistant integration.
* [ ] MQTT status publishing.
* [ ] Notification on watering start/stop/failure.
* [ ] Notification if API rain import fails for more than N hours.
* [ ] Notification if daemon restarts during watering.
* [ ] Simple Grafana dashboard from `rain_events` and `watering_log`.
* [ ] Compare Open-Meteo rain vs physical sensor over time.
