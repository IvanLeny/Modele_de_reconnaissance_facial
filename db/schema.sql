-- Schéma de la base (cahier des charges, Étape 4a) — PostgreSQL + pgvector.
-- Sur la machine cible : CREATE EXTENSION IF NOT EXISTS vector;
-- Le même schéma logique est repris en SQLite pour le développement/les tests
-- (src/retrieval/store.py) ; seul le type du vecteur diffère.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    doc_id       TEXT PRIMARY KEY,
    type         TEXT NOT NULL,        -- annuaire | rapport_analyse | note_conjoncture | contexte
    exercice     INTEGER,              -- année de l'exercice (données)
    periode      TEXT,                 -- ex. « T3 2024 » pour une note de conjoncture
    source_file  TEXT,
    n_pages      INTEGER,
    structure    TEXT DEFAULT 'MINPMEESA/DEPP'
);

-- Passages de commentaire (rapports d'analyse, notes de conjoncture).
CREATE TABLE IF NOT EXISTS passages (
    id               BIGSERIAL PRIMARY KEY,
    doc_id           TEXT REFERENCES documents(doc_id),
    exercice         INTEGER NOT NULL,   -- porte le filtrage temporel (clause WHERE)
    nature           TEXT,               -- 'commentaire' | 'donnee'
    code_indicateur  TEXT,               -- rattachement à un indicateur (via appariement)
    section          TEXT,
    page             INTEGER,
    texte            TEXT NOT NULL,
    vecteur          vector(384)         -- embedding (encodeur multilingue)
);

-- Valeurs linéarisées des tableaux (Annuaires) : chaque valeur avec ses libellés.
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

-- Table d'appariement (code indicateur stable ↔ tableau / graphique par exercice).
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
-- Recherche plein-texte native pour la voie lexicale (français).
CREATE INDEX IF NOT EXISTS idx_passages_fts
    ON passages USING GIN (to_tsvector('french', texte));
