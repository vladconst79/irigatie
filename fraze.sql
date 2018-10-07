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