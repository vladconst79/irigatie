CREATE TABLE progman
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

CREATE TABLE programari
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
    max_ploaie decimal(10, 4) default 1.0000 null,
    activ      tinyint(1)     default 1      null,
    constraint programari_id_uindex
        unique (id)
)
    collate = utf8mb4_uca1400_ai_ci;

CREATE INDEX programari_activ_id_index
    ON programari (activ, id);

CREATE INDEX programari_traseu_id_index
    ON programari (traseu_id);

CREATE TABLE zone_rain_state
(
    traseu_id          int            not null
        primary key,
    rain_credit_mm     decimal(10, 4) not null default 0.0000,
    days_without_rain  int            not null default 1,
    updated_at         datetime       not null,
    last_rain_event_id int            null
);

CREATE TABLE rain_events
(
    id         int auto_increment
        primary key,
    source     varchar(16)    not null,
    event_time datetime       not null,
    amount_mm  decimal(10, 4) not null,
    raw_value  varchar(255)   null,
    created_at datetime       not null
);

CREATE INDEX rain_events_event_time_id_index
    ON rain_events (event_time, id);

CREATE INDEX rain_events_source_time_index
    ON rain_events (source, event_time);

CREATE TABLE runtime_state
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

CREATE TABLE trasee
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

CREATE TABLE watering_log
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

CREATE INDEX watering_log_program_index
    ON watering_log (program_id, traseu_id);

CREATE INDEX watering_log_started_at_index
    ON watering_log (started_at);

CREATE USER 'irigatie_user'@'localhost' IDENTIFIED BY 'replace-with-database-password';
GRANT SELECT,INSERT,UPDATE,DELETE ON irigatie.* TO 'irigatie_user'@'localhost';

SELECT trasee.denumire, programari.*
FROM programari
LEFT JOIN trasee ON programari.traseu_id = trasee.id;

UPDATE zone_rain_state SET rain_credit_mm = rain_credit_mm + 0.2794, days_without_rain = 1, updated_at = NOW();
