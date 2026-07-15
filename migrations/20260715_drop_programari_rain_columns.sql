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

ALTER TABLE programari
    DROP COLUMN ploaie,
    DROP COLUMN zile_fp;
