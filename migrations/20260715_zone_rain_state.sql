CREATE TABLE IF NOT EXISTS zone_rain_state
(
    traseu_id          int            not null
        primary key,
    rain_credit_mm     decimal(10, 4) not null default 0.0000,
    days_without_rain  int            not null default 1,
    updated_at         datetime       not null,
    last_rain_event_id int            null
);

INSERT IGNORE INTO zone_rain_state
    (traseu_id, rain_credit_mm, days_without_rain, updated_at)
SELECT
    trasee.id,
    COALESCE(MAX(programari.ploaie), 0.0000),
    COALESCE(MAX(programari.zile_fp), 1),
    NOW()
FROM trasee
LEFT JOIN programari ON programari.traseu_id = trasee.id
GROUP BY trasee.id;

-- Follow with 20260715_drop_programari_rain_columns.sql after the updated
-- application code is deployed.
