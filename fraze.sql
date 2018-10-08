CREATE TABLE trasee
(
  id int NOT NULL AUTO_INCREMENT,
  denumire varchar(32),
  tip int DEFAULT 1,
  primary key (id)
);
CREATE UNIQUE INDEX trasee_id_uindex ON trasee (id);
CREATE TABLE programari
(
    id int PRIMARY KEY NOT NULL AUTO_INCREMENT,
    traseu_id int,
    m varchar(10),
    h varchar(10),
    dom varchar(10),
    mon varchar(10),
    dow varchar(10),
    durata int DEFAULT 0 NULL,
    ploaie int DEFAULT 0 NULL
);
CREATE UNIQUE INDEX programari_id_uindex ON programari (id);

CREATE USER 'thumpback'@'localhost' IDENTIFIED BY 'hip4\staler';
GRANT SELECT,INSERT,UPDATE,DELETE on irigatie.* to 'thumpback'@'localhost';

SELECT trasee.denumire, programari.* FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id;

UPDATE programari SET ploaie = ploaie + 1;

CREATE TABLE progman
(
    id int PRIMARY KEY AUTO_INCREMENT,
    denumire varchar(32),
    durata_t1 int DEFAULT 0,
    durata_t2 int DEFAULT 0,
    durata_t3 int DEFAULT 0,
    durata_t4 int DEFAULT 0
);
CREATE UNIQUE INDEX progman_id_uindex ON progman (id)

