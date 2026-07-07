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
* [x] Confirm `irigatie.conf` is handled intentionally:

    * [x] live `irigatie.conf` is ignored because it contains secrets
    * [x] replaced with `irigatie.conf.sample`
* [x] Confirm DB schema is tracked, without live data or secrets.
* [x] Confirm `.gitignore` excludes:

    * [x] secrets
    * [x] runtime state files
    * [x] logs
    * [x] Python cache files
    * [x] local IDE files if desired
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
* [x] Force these OFF at boot:

    * [x] transformer relay
    * [x] zone 1 relay
    * [x] zone 2 relay
    * [x] zone 3 relay
    * [x] zone 4 relay
* [x] Enable it with systemd.
* [x] Test by rebooting while no watering is active.

## 5. Add Daemon Startup Safety

* [x] At the very start of `irigatie-control.py`, force all relays OFF.
* [x] Do this before:

    * [x] opening the socket
    * [x] accepting commands
    * [x] registering button callbacks
    * [x] starting LED status thread
    * [x] starting schedules
* [x] Mark any previously running job as interrupted.
* [x] Log startup relay reset to syslog.

## 6. Wrap Relay Control in `try/finally`

* [x] Replace raw patterns like:

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

* [x] Also wrap transformer control.
* [x] Ensure transformer turns off even if:

    * [x] DB query fails
    * [x] socket command fails
    * [x] exception occurs during watering
    * [x] service is stopped
    * [x] user presses Ctrl+C

## 7. Replace Global `program_activ` with a Proper Lock

* [x] Add a `threading.Lock()`.
* [x] Ensure only one watering job can run at a time.
* [x] Protect both manual and scheduled programs with the same lock.
* [x] Avoid race conditions between:

    * [x] physical buttons
    * [x] socket commands
    * [x] future internal scheduler
    * [x] systemd restarts

## 8. Replace Fire-and-Forget Threads with a Command Queue

* [x] Create one controller worker thread.
* [x] Make buttons, socket commands, and scheduler enqueue commands.
    * [x] buttons
    * [x] socket commands
    * [x] scheduler
* [x] Make the worker execute commands one at a time.
* [x] Queue commands like:

    * [x] `START scheduled_program_id`
    * [x] `EXEC manual_program_id`
    * [x] `STOP`
    * [x] `SHUTDOWN`
* [x] Queue up to four scheduled watering commands and reject manual commands while watering is active or queued.
* [x] Log rejected commands.

## 9. Add Hard Runtime Limits

* [x] Add config values:

```ini
[Safety]
MAX_ZONE_SECONDS = 3600
MAX_PROGRAM_SECONDS = 7200
```

* [x] Refuse absurd DB durations.
* [x] Clamp or abort any zone duration above the configured maximum.
* [x] Log safety aborts.
* [x] Make sure DB corruption cannot water forever.

## 10. Add Runtime State Tracking

* [x] Add a DB table or local state file recording:

    * [x] current state: `idle`, `running`, `stopping`, `interrupted`, `error`
    * [x] source: `manual`, `scheduled`, `socket`
    * [x] program id
    * [x] route/zone id
    * [x] started time
    * [x] expected end time
    * [x] heartbeat time
* [x] On daemon startup:

    * [x] if previous state was `running`, mark it `interrupted`
    * [x] force all relays OFF
* [x] During watering, update heartbeat periodically.
* [x] On normal finish, mark state as `idle`.

## 11. Add Local HTTP Command Gateway

* [x] Create a tiny Python HTTP daemon on the Raspberry Pi.
* [x] Expose only safe command endpoints:

    * [x] `POST /commands/start`
    * [x] `POST /commands/exec`
    * [x] `POST /commands/stop`
    * [x] `GET /status`
    * [x] `POST /reload-schedules`
* [x] Validate all request bodies strictly.
* [x] Require authentication.
* [x] Bind to an external LAN/VPN interface for the remote web server.
* [x] Forward accepted commands to the irrigation Unix socket.
* [x] Do not control GPIO directly from the HTTP daemon.
* [x] Add a systemd service for the gateway.
* [x] Update remote web UI to call the gateway instead of the Unix socket directly.

## 12. Replace Cron Scheduling With systemd Timers

* [x] Stop using cron for irrigation schedules.
    * [x] Main PHP web UI no longer rebuilds cron.
    * [x] Legacy `web/android` endpoints no longer rebuild cron.
* [x] Create `generate_systemd_schedules.py`.
* [x] Generate one templated `irigatie-program@.service`.
* [x] Generate one `irigatie-program-<id>.timer` per `programari` row.
* [x] Timer services must call `client.py -c START -p <program_id>`.
* [x] Convert supported cron fields to `OnCalendar`:

    * [x] `*`
    * [x] single number
    * [x] comma list
    * [x] numeric range
    * [x] comma list of numeric ranges
    * [x] `*/N` for `dom` and `dow`
* [x] Disable/remove stale generated timers for deleted `programari` rows.
* [x] Run `systemctl daemon-reload` after timer changes.
* [x] Enable/start generated timers.
* [x] Add `RELOAD_SCHEDULES` command.
* [x] Make web/API server call `RELOAD_SCHEDULES` after schedule insert/update/delete.
* [x] Verify with `systemctl list-timers 'irigatie-program-*'`.
* [x] Document that `irigatie.service` runs as root so it can manage generated timer units.

## 13. Keep systemd Timers Only for Helper Jobs

* [x] Keep `irigatie-online-rain.timer` for Open-Meteo updates.
* [x] Do not use timers or cron to directly control relays.
    * [x] Generated irrigation timers call `client.py`, which delegates to `irigatie-control.py`.
    * [x] `irigatie-online-rain.timer` updates rain accounting only.
    * [x] `irigatie-relays-off.service` touches relays directly, but it is a boot safety service, not a timer or cron schedule.
* [x] Any timer-triggered action should call the daemon/client, not GPIO directly.

## 14. Refactor Repeated Zone Code

* [x] Replace four copy-pasted zone blocks with a loop.
* [x] Create a zone map:

```python
zones = {
    1: relay_1,
    2: relay_2,
    3: relay_3,
    4: relay_4,
}
```

* [x] Store zone metadata from DB:

    * [x] id
    * [x] name
    * [x] active flag
    * [x] relay
* [x] Use a common function:

```python
run_zone(zone_id, duration_seconds)
```

## 15. Split Hardware Control from Business Logic

* [x] Create a hardware abstraction layer.
* [x] Suggested files:

```text
gpio_hw.py
controller.py
db.py
config.py
rain.py
socket_server.py
```

* [x] `config.py` owns typed config loading and defaults.
* [x] `gpio_hw.py` owns relays, buttons, and LED.
* [x] `controller.py` decides what to water.
* [x] `db.py` owns SQL queries.
* [x] `rain.py` owns rain accounting.
* [x] `socket_server.py` owns command parsing.
* [x] Resume the remaining `## 15` module splits after `## 16` mock GPIO mode is done.

## 16. Add Mock GPIO Mode

* [x] Add config:

```ini
[Hardware Control]
GPIO_BACKEND = real
```

or:

```ini
[Hardware Control]
GPIO_BACKEND = mock
```

* [x] In mock mode:

    * [x] relay actions only log messages
    * [x] button setup is skipped or simulated
    * [x] LED actions are ignored or logged
* [x] Use mock mode for development on Mac or VM.

## 17. Improve SQL Safety

* [ ] Replace string-concatenated SQL with parameterized queries.
* [ ] Audit all DB writes.
* [ ] Use short-lived cursors.
* [ ] Avoid one shared global cursor across threads.
* [ ] Prefer opening DB connections per operation or using a small safe wrapper.
* [ ] Log SQL errors clearly.

## 18. Normalize Rain Units

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

## 19. Separate Rain Sources

* [x] Do not let hardware sensor and API both write directly into `programari.ploaie`.
* [ ] Add separate rain logs:

    * [x] API rain events
    * [x] hardware rain events
    * [ ] manual rain corrections
* [x] Use only one selected source for irrigation credit, or a deliberate weighted combination.
* [x] Add config:

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

## 20. Add Rain Event Logging

* [x] Add table:

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

* [x] Log Open-Meteo imports.
* [x] Later log hardware sensor pulses.
* [x] Use this to compare API vs physical sensor accuracy.

## 21. Add Watering Event Logging

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

## 22. Add Status Command

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

## 23. Add Stop Command

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

## 24. Harden Socket Control

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

## 25. Improve Logging

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

## 26. Improve Configuration

* [x] Create `irigatie.conf.sample`.
* [ ] Validate config on startup.
* [ ] Fail clearly if required config is missing.
* [ ] Print/log effective GPIO pin mapping.
* [ ] Print/log rain source mode.
* [ ] Print/log DB connection target without password.

## 27. Add Test Commands

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

## 28. Fresh OS Deployment

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

## 29. Documentation

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

## 30. Future Optional Improvements

* [ ] Web status page.
* [ ] Home Assistant integration.
* [ ] MQTT status publishing.
* [ ] Notification on watering start/stop/failure.
* [ ] Notification if API rain import fails for more than N hours.
* [ ] Notification if daemon restarts during watering.
* [ ] Simple Grafana dashboard from `rain_events` and `watering_log`.
* [ ] Compare Open-Meteo rain vs physical sensor over time.
