# Database Specification

This document describes the MariaDB/MySQL schema used by the irrigation
controller. The schema stores irrigation zones, scheduled programs, manual
programs, runtime status, rain accounting events, and watering history.

## Engine And Character Set

The provided tables use the default storage engine and the
`utf8mb4_uca1400_ai_ci` collation where explicitly declared.

Application code connects with `pymysql` and expects regular MySQL/MariaDB
`datetime`, `decimal`, `int`, `tinyint`, and `varchar` semantics.

## Tables

### `trasee`

Stores irrigation zones.

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | `int auto_increment` | no | | Zone identifier. |
| `denumire` | `varchar(32)` | yes | `NULL` | Zone display name. |
| `tip` | `int` | yes | `1` | Zone type. `1` = sprinkler, `2` = drip. |
| `activ` | `tinyint(1)` | yes | `1` | Whether the zone is enabled. |

Indexes:

| Name | Columns | Type |
| --- | --- | --- |
| `PRIMARY` | `id` | primary key |
| `trasee_id_uindex` | `id` | unique |

### `programari`

Stores scheduled irrigation entries. Cron-like date/time fields are stored as
short strings because they are also used to generate systemd timer schedules.

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | `int auto_increment` | no | | Schedule identifier. |
| `traseu_id` | `int` | yes | `NULL` | Target zone id from `trasee.id`. |
| `m` | `varchar(10)` | yes | `NULL` | Minute expression. |
| `h` | `varchar(10)` | yes | `NULL` | Hour expression. |
| `dom` | `varchar(10)` | yes | `NULL` | Day-of-month expression. |
| `mon` | `varchar(10)` | yes | `NULL` | Month expression. |
| `dow` | `varchar(10)` | yes | `NULL` | Day-of-week expression. |
| `durata` | `int` | yes | `0` | Planned watering duration, in minutes. |
| `ploaie` | `decimal(10,4)` | yes | `0.0000` | Current rain credit in millimeters. |
| `max_ploaie` | `decimal(10,4)` | yes | `1.0000` | Rain threshold in millimeters. |
| `zile_fp` | `int` | yes | `1` | Days without rain used by rain-credit reduction. |
| `activ` | `tinyint(1)` | yes | `1` | Whether the schedule is enabled. |

Indexes:

| Name | Columns | Type |
| --- | --- | --- |
| `PRIMARY` | `id` | primary key |
| `programari_id_uindex` | `id` | unique |
| `programari_activ_id_index` | `activ`, `id` | secondary index |
| `programari_traseu_id_index` | `traseu_id` | secondary index |

### `progman`

Stores manual watering programs. Each duration column maps to one zone id.

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | `int auto_increment` | no | | Manual program identifier. |
| `denumire` | `varchar(32)` | yes | `NULL` | Manual program display name. |
| `durata_t1` | `int` | yes | `0` | Zone 1 duration in minutes. |
| `durata_t2` | `int` | yes | `0` | Zone 2 duration in minutes. |
| `durata_t3` | `int` | yes | `0` | Zone 3 duration in minutes. |
| `durata_t4` | `int` | yes | `0` | Zone 4 duration in minutes. |

Indexes:

| Name | Columns | Type |
| --- | --- | --- |
| `PRIMARY` | `id` | primary key |
| `progman_id_uindex` | `id` | unique |

### `runtime_state`

Stores the daemon's current runtime state. The application treats this as a
single-row table with `id = 1`.

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | `tinyint` | no | | Runtime row id. Use `1`. |
| `state` | `varchar(16)` | no | | Runtime state such as `idle`, `running`, `stopping`, `error`, or `interrupted`. |
| `source` | `varchar(16)` | yes | `NULL` | Source of the current command. |
| `command` | `varchar(16)` | yes | `NULL` | Current command, for example `START`, `EXEC`, `TEST`, or `STOP`. |
| `program_id` | `int` | yes | `NULL` | Current scheduled/manual program id. |
| `traseu_id` | `int` | yes | `NULL` | Current zone id. |
| `started_at` | `datetime` | yes | `NULL` | Start timestamp for current run. |
| `expected_end_at` | `datetime` | yes | `NULL` | Expected end timestamp for current run or zone. |
| `heartbeat_at` | `datetime` | yes | `NULL` | Last daemon heartbeat timestamp. |
| `updated_at` | `datetime` | no | | Last state update timestamp. |
| `message` | `varchar(255)` | yes | `NULL` | Short status or error message. |

Indexes:

| Name | Columns | Type |
| --- | --- | --- |
| `PRIMARY` | `id` | primary key |

### `rain_events`

Stores rain events imported from hardware, Open-Meteo, manual correction, or
hybrid accounting.

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | `int auto_increment` | no | | Rain event identifier. |
| `source` | `varchar(16)` | no | | Rain source, for example `hardware`, `openmeteo`, or `manual`. |
| `event_time` | `datetime` | no | | Timestamp the rain event represents. |
| `amount_mm` | `decimal(10,4)` | no | | Rain amount in millimeters. May be negative for corrections. |
| `raw_value` | `varchar(255)` | yes | `NULL` | Source-specific raw value or operator note. |
| `created_at` | `datetime` | no | | Insert timestamp. |

Indexes:

| Name | Columns | Type |
| --- | --- | --- |
| `PRIMARY` | `id` | primary key |
| `rain_events_event_time_id_index` | `event_time`, `id` | secondary index |
| `rain_events_source_time_index` | `source`, `event_time` | secondary index |

### `watering_log`

Stores completed, interrupted, and failed watering attempts.

| Column | Type | Null | Default | Description |
| --- | --- | --- | --- | --- |
| `id` | `int auto_increment` | no | | Watering log identifier. |
| `started_at` | `datetime` | no | | Start timestamp. |
| `ended_at` | `datetime` | no | | End timestamp. |
| `source` | `varchar(16)` | no | | Command source. |
| `program_id` | `int` | yes | `NULL` | Scheduled/manual program id when applicable. |
| `traseu_id` | `int` | yes | `NULL` | Zone id when applicable. |
| `planned_seconds` | `decimal(10,3)` | yes | `NULL` | Planned duration in seconds. |
| `actual_seconds` | `decimal(10,3)` | yes | `NULL` | Actual elapsed duration in seconds. |
| `rain_credit_mm` | `decimal(10,4)` | yes | `NULL` | Rain credit used for the decision. |
| `result` | `varchar(32)` | no | | Result code, for example completed, interrupted, skipped, or error states. |
| `error` | `varchar(255)` | yes | `NULL` | Truncated exception or failure text. |

Indexes:

| Name | Columns | Type |
| --- | --- | --- |
| `PRIMARY` | `id` | primary key |
| `watering_log_started_at_index` | `started_at` | secondary index |
| `watering_log_program_index` | `program_id`, `traseu_id` | secondary index |

## Relationships

The schema does not define foreign key constraints, but the application uses
these logical relationships:

| Source column | Target column | Usage |
| --- | --- | --- |
| `programari.traseu_id` | `trasee.id` | Scheduled watering zone. |
| `runtime_state.program_id` | `programari.id` or `progman.id` | Currently running scheduled/manual program. |
| `runtime_state.traseu_id` | `trasee.id` | Currently running zone. |
| `watering_log.program_id` | `programari.id` or `progman.id` | Historical program reference. |
| `watering_log.traseu_id` | `trasee.id` | Historical zone reference. |

## Operational Notes

- `runtime_state` is maintained by the daemon and should normally contain only
  row `id = 1`.
- Rain credits are accumulated in `programari.ploaie`.
- Scheduled watering reduces `programari.ploaie` and increments
  `programari.zile_fp` after a scheduled program decision.
- `rain_events` and `watering_log` are append-only operational history tables.
- Manual program duration columns are discovered dynamically using
  `SHOW COLUMNS FROM progman LIKE 'durata_t%'`, so additional `durata_tN`
  columns can be added for more zones.

## Reference DDL

```sql
create table progman
(
    id        int auto_increment
        primary key,
    denumire  varchar(32)   null,
    durata_t1 int default 0 null,
    durata_t2 int default 0 null,
    durata_t3 int default 0 null,
    durata_t4 int default 0 null,
    constraint progman_id_uindex
        unique (id)
)
    collate = utf8mb4_uca1400_ai_ci;

create table programari
(
    id         int auto_increment
        primary key,
    traseu_id  int                           null,
    m          varchar(10)                   null,
    h          varchar(10)                   null,
    dom        varchar(10)                   null,
    mon        varchar(10)                   null,
    dow        varchar(10)                   null,
    durata     int            default 0      null,
    ploaie     decimal(10, 4) default 0.0000 null,
    max_ploaie decimal(10, 4) default 1.0000 null,
    zile_fp    int            default 1      null,
    activ      tinyint(1)     default 1      null,
    constraint programari_id_uindex
        unique (id)
)
    collate = utf8mb4_uca1400_ai_ci;

create index programari_activ_id_index
    on programari (activ, id);

create index programari_traseu_id_index
    on programari (traseu_id);

create table rain_events
(
    id         int auto_increment
        primary key,
    source     varchar(16)    not null,
    event_time datetime       not null,
    amount_mm  decimal(10, 4) not null,
    raw_value  varchar(255)   null,
    created_at datetime       not null
);

create index rain_events_event_time_id_index
    on rain_events (event_time, id);

create index rain_events_source_time_index
    on rain_events (source, event_time);

create table runtime_state
(
    id              tinyint      not null
        primary key,
    state           varchar(16)  not null,
    source          varchar(16)  null,
    command         varchar(16)  null,
    program_id      int          null,
    traseu_id       int          null,
    started_at      datetime     null,
    expected_end_at datetime     null,
    heartbeat_at    datetime     null,
    updated_at      datetime     not null,
    message         varchar(255) null
);

create table trasee
(
    id       int auto_increment
        primary key,
    denumire varchar(32)          null,
    tip      int        default 1 null,
    activ    tinyint(1) default 1 null,
    constraint trasee_id_uindex
        unique (id)
)
    collate = utf8mb4_uca1400_ai_ci;

create table watering_log
(
    id              int auto_increment
        primary key,
    started_at      datetime       not null,
    ended_at        datetime       not null,
    source          varchar(16)    not null,
    program_id      int            null,
    traseu_id       int            null,
    planned_seconds decimal(10, 3) null,
    actual_seconds  decimal(10, 3) null,
    rain_credit_mm  decimal(10, 4) null,
    result          varchar(32)    not null,
    error           varchar(255)   null
);

create index watering_log_program_index
    on watering_log (program_id, traseu_id);

create index watering_log_started_at_index
    on watering_log (started_at);
```
