# Fresh Installation

This guide describes a clean Raspberry Pi installation for `irigatie`.

The default deployment model is:

- Raspberry Pi Zero W or Raspberry Pi Zero 2 W
- Raspberry Pi OS / Raspbian Stretch or newer
- platform `python3` interpreter
- project installed at `/home/pi/irigatie`
- irrigation daemon and HTTP gateway running as root through systemd
- remote MariaDB server by default
- Open-Meteo rain import enabled by default

The code is kept compatible with Python 3.5 for the original Pi Zero W
deployment, but newer Raspberry Pi OS releases with newer Python 3 versions are
acceptable.

## 1. Install OS Packages

Start from a Raspberry Pi OS installation with network access and systemd.

Install the packages used by the controller:

```bash
sudo apt update
sudo apt install -y \
  git \
  ca-certificates \
  python3 \
  python3-gpiozero \
  python3-rpi.gpio \
  python3-pymysql \
  default-mysql-client
```

For a local MariaDB deployment instead of a remote database server, also
install:

```bash
sudo apt install -y default-mysql-server
```

## 2. Clone the Repository

Install the project under `/home/pi/irigatie`:

```bash
cd /home/pi
git clone https://github.com/vladconst79/irigatie.git
cd /home/pi/irigatie
```

## 3. Create Configuration

Create a private runtime config from the sample:

```bash
cp irigatie.sample.conf irigatie.conf
chmod 600 irigatie.conf
```

Edit `irigatie.conf` and set at least:

- `[ConectGPIO]` pins for your relay board, rain sensor, LED, and buttons
- `[Hardware Control] GPIO_BACKEND = real`
- `[HTTP Gateway] AUTH_TOKEN` to a long random token
- `[HTTP Gateway] BIND_HOST` and `BIND_PORT`
- `[SQL]` database host, port, user, password, and database name
- `[Weather API]` latitude, longitude, and timezone
- `[Notifications]` settings if alerts are enabled

The default control socket settings are:

```ini
[Control Socket]
SOCKET_PATH = /run/irigatie/control.sock
SOCKET_MODE = 0660
SOCKET_OWNER = root
SOCKET_GROUP = root
```

## 4. Bootstrap the Database

The default setup uses a remote MariaDB server. Create the database, import the
schema from `fraze.sample.sql`, then create credentials manually for the Pi.

From the MariaDB server, or from a machine that can connect to it:

```bash
mysql -h DB_HOST -u root -p
```

Create the database:

```sql
CREATE DATABASE irigatie CHARACTER SET utf8mb4;
```

Import the schema:

```bash
mysql -h DB_HOST -u root -p irigatie < fraze.sample.sql
```

Then create or adjust the application user manually. Prefer restricting the
host to the Pi address or a trusted MariaDB host pattern instead of using `%`:

```sql
CREATE USER 'irigatie_user'@'192.168.19.52' IDENTIFIED BY 'replace-with-database-password';
GRANT SELECT, INSERT, UPDATE, DELETE ON irigatie.* TO 'irigatie_user'@'192.168.19.52';
FLUSH PRIVILEGES;
```

Use the Pi address in place of `192.168.19.52`. If the Pi address is not fixed,
use a narrow wildcard host pattern such as `192.168.19.%`.

If the database server rejects a collation from `fraze.sample.sql`, use a
MariaDB-supported `utf8mb4` collation for that server and keep the table layout
the same.

For an existing production system, restore a private database backup instead of
creating empty tables:

```bash
mysql -h DB_HOST -u DB_USER -p irigatie < irigatie-backup.sql
```

## 5. Install systemd Units

Copy the tracked units into `/etc/systemd/system`:

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

The main daemon intentionally runs as root because it owns GPIO control and
regenerates systemd schedule timers.

## 6. First-Run Checks

Before enabling watering, validate config, database access, relay mapping, and
socket behavior:

```bash
sudo /home/pi/irigatie/irigatie-control.py --check-config
sudo /home/pi/irigatie/irigatie-control.py --test-db
sudo /home/pi/irigatie/irigatie-control.py --test-relay-map
```

`--test-relay-map` only prints configured relay pins. It does not switch
relays.

With valves disconnected or otherwise safe, verify relay shutdown:

```bash
sudo /home/pi/irigatie/relays_off.py
```

## 7. Enable Services

Enable the boot-time relay-off safety service and the core daemons:

```bash
sudo systemctl enable irigatie-relays-off.service
sudo systemctl enable irigatie.service
sudo systemctl enable irigatie-http-gateway.service
sudo systemctl restart irigatie.service
sudo systemctl restart irigatie-http-gateway.service
```

Enable Open-Meteo rain import:

```bash
sudo systemctl enable --now irigatie-online-rain.timer
```

Enable database cleanup:

```bash
sudo systemctl enable --now irigatie-db-cleanup.timer
```

Check status:

```bash
sudo systemctl status irigatie.service --no-pager
sudo systemctl status irigatie-http-gateway.service --no-pager
sudo systemctl list-timers 'irigatie-*'
sudo /home/pi/irigatie/client.py status
```

## 8. Gateway Access

The HTTP gateway listens on `[HTTP Gateway] BIND_HOST:BIND_PORT`, commonly
`0.0.0.0:8080` on a trusted LAN/VPN. It requires `AUTH_TOKEN` and should not be
exposed directly to the public internet without firewall, VPN, or reverse proxy
protection.

Use the OpenAPI contract for client integration:

```text
api/irigatie-gateway.openapi.yaml
```

## 9. Notifications

Notifications are optional. For unattended operation, enable at least watering
failure alerts:

```ini
[Notifications]
ENABLED = true
ON_WATERING_FAILURE = true
```

Configure either SMTP, CallMeBot, or both in `irigatie.conf`.

## 10. Schedule Generation

After schedules are added or restored in the database, ask the daemon to
regenerate systemd timers:

```bash
sudo /home/pi/irigatie/client.py -c RELOAD_SCHEDULES
systemctl list-timers 'irigatie-program-*'
```

## 11. Rollback and Backup Notes

Before a hardware migration, keep the old SD card untouched as rollback.

After the new installation passes config, DB, relay-map, socket, Open-Meteo,
and one short live watering test, image the completed card and store a database
backup separately.
