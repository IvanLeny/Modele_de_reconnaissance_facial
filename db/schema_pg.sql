-- Schéma PostgreSQL SANS pgvector (cahier des charges, Étape 4a) — version
-- applicable telle quelle sous Windows, où pgvector n'est pas installé par
-- défaut. La récupération du prototype est STRUCTURÉE (par code indicateur,
-- intitulé et filtrage temporel SQL) : elle n'a pas besoin de la colonne
-- vectorielle. pgvector reste une extension future (voir db/schema.sql).

CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    type         TEXT NOT NULL,
    exercice     INTEGER,
    periode      TEXT,
    source_file  TEXT,
    n_pages      INTEGER,
    structure    TEXT DEFAULT 'MINPMEESA/DEPP'
);

CREATE TABLE IF NOT EXISTS passages (
    id               BIGSERIAL PRIMARY KEY,
    doc_id           TEXT REFERENCES documents(doc_id),
    exercice         INTEGER NOT NULL,      -- porte le filtrage temporel (WHERE)
    nature           TEXT,
    code_indicateur  TEXT,
    section          TEXT,
    page             INTEGER,
    texte            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tableaux (
    id           BIGSERIAL PRIMARY KEY,
    doc_id       TEXT REFERENCES documents(doc_id),
    exercice     INTEGER NOT NULL,
    tableau_n    INTEGER,
    page         INTEGER,
    ligne        TEXT,
    colonne      TEXT,
    valeur       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS appariement (
    code_indicateur  TEXT NOT NULL,
    exercice         INTEGER NOT NULL,
    graphique_n      INTEGER,
    tableau_n        INTEGER,
    intitule         TEXT,
    PRIMARY KEY (code_indicateur, exercice)
);

CREATE INDEX IF NOT EXISTS idx_passages_ex   ON passages(exercice);
CREATE INDEX IF NOT EXISTS idx_passages_code ON passages(code_indicateur);
CREATE INDEX IF NOT EXISTS idx_tableaux_ex   ON tableaux(exercice);
-- Recherche plein-texte native (français) pour la voie lexicale.
CREATE INDEX IF NOT EXISTS idx_passages_fts
    ON passages USING GIN (to_tsvector('french', texte));
