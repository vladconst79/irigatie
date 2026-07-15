# Irigatie

Raspberry Pi irrigation controller. The main daemon owns GPIO control and a
local Unix socket. Web and timer entrypoints send commands to the daemon
instead of touching relays directly.

## Useful Checks

Run these on the Pi from `/home/pi/irigatie`:

```bash
./irigatie-control.py --check-config
./irigatie-control.py --test-db
./irigatie-control.py --test-relay-map
./irigatie-control.py --test-socket
./client.py status
```

`--test-relay-map` only prints configured relay pins. It does not switch
relays. `--relays-off` does switch relays and should be run only when the
valves are safe to force off.

## Recovery

If watering is stuck:

```bash
sudo systemctl stop irigatie.service
sudo /home/pi/irigatie/relays_off.py
```

Then verify relay state and daemon status:

```bash
sudo systemctl status irigatie.service --no-pager
sudo journalctl -u irigatie.service -n 100 --no-pager
sudo /home/pi/irigatie/irigatie-control.py --test-relay-map
```

To start again:

```bash
sudo systemctl start irigatie.service
sudo /home/pi/irigatie/client.py status
```

## systemd

Install or update tracked unit files:

```bash
sudo cp systemd-scripts/irigatie.service /etc/systemd/system/irigatie.service
sudo cp systemd-scripts/irigatie-http-gateway.service /etc/systemd/system/irigatie-http-gateway.service
sudo cp systemd-scripts/irigatie-online-rain.service /etc/systemd/system/irigatie-online-rain.service
sudo cp systemd-scripts/irigatie-online-rain.timer /etc/systemd/system/irigatie-online-rain.timer
sudo cp systemd-scripts/irigatie-db-cleanup.service /etc/systemd/system/irigatie-db-cleanup.service
sudo cp systemd-scripts/irigatie-db-cleanup.timer /etc/systemd/system/irigatie-db-cleanup.timer
sudo cp systemd-scripts/irigatie-relays-off.service /etc/systemd/system/irigatie-relays-off.service
sudo systemctl daemon-reload
```

Enable and start core services:

```bash
sudo systemctl enable irigatie-relays-off.service
sudo systemctl enable irigatie.service
sudo systemctl enable irigatie-http-gateway.service
sudo systemctl restart irigatie.service
sudo systemctl restart irigatie-http-gateway.service
```

Open-Meteo rain import is a helper timer:

```bash
sudo systemctl enable --now irigatie-online-rain.timer
sudo systemctl list-timers 'irigatie-online-rain.timer'
```

Database cleanup is a quarterly helper timer. It prunes zero Open-Meteo rain
events and old `rain_events` / `watering_log` history:

```bash
sudo /home/pi/irigatie/cleanup_database.py --dry-run /home/pi/irigatie/irigatie.conf
sudo systemctl enable --now irigatie-db-cleanup.timer
sudo systemctl list-timers 'irigatie-db-cleanup.timer'
```

Generated irrigation timers are managed by the daemon through
`RELOAD_SCHEDULES`:

```bash
sudo /home/pi/irigatie/client.py -c RELOAD_SCHEDULES
systemctl list-timers 'irigatie-program-*'
```

Common diagnostics:

```bash
sudo systemctl status irigatie.service --no-pager
sudo systemctl status irigatie-http-gateway.service --no-pager
sudo journalctl -u irigatie.service -f
sudo journalctl -u irigatie-http-gateway.service -f
sudo ls -l /run/irigatie/control.sock
sudo ss -ltnp 'sport = :8080'
```

The daemon and HTTP gateway units wait for `network-online.target`, but the
daemon can still start in offline mode if the remote database is unreachable.
It keeps GPIO/socket control available and retries the database connection in
the background. Check the daemon journal for `daemon left offline mode` after
network or MySQL connectivity returns.

## Web UI

The PHP web UI uses `web/irigatie.ini` for database settings and controller
gateway access:

```ini
[Controller]
CONTROLLER_URL = "http://raspberry-pi-host-or-ip:8080"
CONTROLLER_TOKEN = "replace-with-the-same-token-as-irigatie-conf"
```

The status page is available at:

```text
/status.php
```

It is read-only and reports daemon state, gateway/socket health, DB status,
queue depth, last rain event, relay state, safety checks, and schedule reload
status through the HTTP gateway.

## HTTP Gateway API

The gateway API contract is tracked in:

```text
api/irigatie-gateway.openapi.yaml
```

New web or mobile clients should use this HTTP API only. They should not talk
directly to GPIO, MySQL, systemd, or the daemon Unix socket.

Gateway status is available at both `/status` and `/api/status`. Mobile clients
that route all requests under `/api` should use `/api/status`.
`/api/snapshot` also includes `status.available`, `status.error`, and
`relays.transformer` so mobile clients can poll only the snapshot when they need
the app read model plus transformer relay state.

Set `[HTTP Gateway] DAEMON_STATUS_TIMEOUT_SECONDS` if the Pi or its network is
slow enough that daemon `STATUS` replies regularly exceed the default 15 seconds.
If Apache or another reverse proxy runs on a different host, set
`[HTTP Gateway] TRUSTED_PROXIES` to the proxy IPs, for example
`TRUSTED_PROXIES = 127.0.0.1, ::1, 192.168.19.10`. Forwarded client IP headers
are used for access logs only when the direct peer is in this list.

Schedule create/update/delete endpoints ask the daemon to reload generated
systemd timers automatically. Clients normally do not need to call
`POST /api/reload-schedules` after saving a schedule; that endpoint is for
manual recovery or admin use. The daemon status payload includes
`schedule_reload.state` so clients and monitoring can see whether the latest
reload is `unknown`, `running`, `ok`, or `error`.

## Database Backup And Restore

Backup schema and data:

```bash
mysqldump -h DB_HOST -u DB_USER -p --single-transaction irigatie > irigatie-backup.sql
```

Restore into an existing database:

```bash
mysql -h DB_HOST -u DB_USER -p irigatie < irigatie-backup.sql
```

For a schema-only bootstrap, use `fraze.sample.sql` as the tracked reference
and then restore real production data from a private backup.

Do not commit live database dumps. They can contain operational history and
credentials.

## Database Cleanup

The `irigatie-db-cleanup.timer` runs quarterly on January, April, July, and
October 1 at 03:15, with up to one hour of randomized delay. Retention is
configured in `irigatie.conf`:

```ini
[Database Cleanup]
RAIN_EVENTS_RETENTION_DAYS = 730
WATERING_LOG_RETENTION_DAYS = 730
DELETE_BATCH_SIZE = 1000
DELETE_ZERO_OPENMETEO = true
```

Run a manual preview:

```bash
sudo /home/pi/irigatie/cleanup_database.py --dry-run /home/pi/irigatie/irigatie.conf
```

## GPIO Pin Table

Default GPIO mapping from `irigatie.conf.sample`:

| Config key | Purpose | GPIO |
| --- | --- | --- |
| `R_TRAF` | transformer relay | 26 |
| `R_IRI1` | zone 1 relay | 21 |
| `R_IRI2` | zone 2 relay | 20 |
| `R_IRI3` | zone 3 relay | 16 |
| `R_IRI4` | zone 4 relay | 12 |
| `S_RAIN` | rain sensor input | 23 |
| `L_RED` | RGB LED red | 18 |
| `L_GREEN` | RGB LED green | 19 |
| `L_BLUE` | RGB LED blue | 13 |
| `B_BUT1` | manual button 1 | 9 |
| `B_BUT2` | manual button 2 | 11 |
| `B_BUT3` | manual button 3 | 22 |
| `B_BUT4` | manual button 4 | 10 |

Check the active Pi config without switching relays:

```bash
./irigatie-control.py --test-relay-map
```

## Rain Calibration

Rain accounting uses millimeters. Hardware rain pulses are converted with:

```text
mm = pulses * HARDWARE_PULSE_MM
```

The default pulse size is:

```ini
[Rain]
HARDWARE_PULSE_MM = 0.2794
```

Select the source used for irrigation credit:

```ini
[Rain]
SOURCE = openmeteo
```

Supported values:

```text
hardware
openmeteo
manual
hybrid
disabled
```

Open-Meteo, hardware, and manual rain events are logged in `rain_events`.
When a rain event changes irrigation credit, the event insert and
`programari.ploaie` update are written together so history and credit do not
diverge. Scheduled watering uses the configured source for credit decisions.

Manual corrections can be logged when an operator needs to fix bad weather
data or account for observed rainfall:

```bash
sudo /home/pi/irigatie/manual_rain_correction.py --amount-mm 5.0 --reason "gauge reading"
sudo /home/pi/irigatie/manual_rain_correction.py --amount-mm -3.0 --reason "undo over-credit"
```

Manual events are always stored in `rain_events` with source `manual`. They
change `programari.ploaie` only when `SOURCE = manual`, or when
`SOURCE = hybrid` and `HYBRID_MANUAL_FACTOR` is greater than zero.

Hybrid source mode uses explicit credit factors:

```ini
[Rain]
SOURCE = hybrid
HYBRID_HARDWARE_FACTOR = 0.0
HYBRID_OPENMETEO_FACTOR = 1.0
HYBRID_MANUAL_FACTOR = 1.0
```

The default hybrid policy keeps Open-Meteo as the credited source, allows
manual corrections, and logs hardware pulses without crediting them until the
physical sensor is calibrated. If both weather API and hardware are credited,
keep their factors below `1.0` to avoid double-counting the same rainfall.

## Disable Online Rain

If the hardware rain sensor is reinstalled and Open-Meteo should no longer
add credit:

```ini
[Rain]
SOURCE = hardware
```

Then stop and disable the online rain timer:

```bash
sudo systemctl disable --now irigatie-online-rain.timer
sudo systemctl status irigatie-online-rain.timer --no-pager
```

Restart the daemon after changing config:

```bash
sudo systemctl restart irigatie.service
sudo /home/pi/irigatie/client.py status
```
