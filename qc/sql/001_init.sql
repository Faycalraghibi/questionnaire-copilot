-- Schema from spec section 7.1 and run log from 00-AGENT-RULES section 7.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE policies (
    policy_id   TEXT PRIMARY KEY,
    title       TEXT NOT NULL
);

CREATE TABLE policy_versions (
    policy_id       TEXT NOT NULL REFERENCES policies(policy_id) ON DELETE CASCADE,
    version         INTEGER NOT NULL,
    effective_date  DATE NOT NULL,
    source_file     TEXT NOT NULL,
    is_current      BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (policy_id, version)
);

-- At most one current version per policy.
CREATE UNIQUE INDEX policy_versions_one_current
    ON policy_versions (policy_id) WHERE is_current;

CREATE TABLE chunks (
    id          BIGSERIAL PRIMARY KEY,
    policy_id   TEXT NOT NULL,
    version     INTEGER NOT NULL,
    section     TEXT NOT NULL,
    text        TEXT NOT NULL,
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    embedding   vector(384),
    FOREIGN KEY (policy_id, version) REFERENCES policy_versions(policy_id, version) ON DELETE CASCADE
);

CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX chunks_policy_version_idx ON chunks (policy_id, version);

CREATE TABLE questionnaires (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    sheet_map   JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE questions (
    id                BIGSERIAL PRIMARY KEY,
    questionnaire_id  BIGINT NOT NULL REFERENCES questionnaires(id) ON DELETE CASCADE,
    qid               TEXT NOT NULL,
    sheet             TEXT NOT NULL,
    row               INTEGER NOT NULL,
    col_question      INTEGER NOT NULL,
    col_answer        INTEGER,
    text              TEXT NOT NULL,
    UNIQUE (questionnaire_id, qid)
);

CREATE TABLE drafts (
    id            BIGSERIAL PRIMARY KEY,
    question_id   BIGINT NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    run_id        TEXT NOT NULL,
    source        TEXT NOT NULL CHECK (source IN ('library', 'policies', 'none')),
    short_answer  TEXT,
    explanation   TEXT,
    citations     JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence    TEXT CHECK (confidence IN ('high', 'medium', 'low')),
    status        TEXT NOT NULL
                  CHECK (status IN ('drafted', 'needs_input', 'approved', 'rejected', 'edited')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reviews (
    id                 BIGSERIAL PRIMARY KEY,
    draft_id           BIGINT NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
    reviewer           TEXT NOT NULL,
    action             TEXT NOT NULL,
    final_answer       TEXT,
    final_explanation  TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE answer_library (
    id               BIGSERIAL PRIMARY KEY,
    question_text    TEXT NOT NULL,
    embedding        vector(384),
    short_answer     TEXT,
    explanation      TEXT,
    citations        JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_versions  JSONB NOT NULL DEFAULT '[]'::jsonb,
    approved_by      TEXT NOT NULL,
    approved_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    stale            BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE run_steps (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    item_id     TEXT,
    step        TEXT NOT NULL,
    input       JSONB,
    output      JSONB,
    tokens_in   INTEGER NOT NULL DEFAULT 0,
    tokens_out  INTEGER NOT NULL DEFAULT 0,
    cost_usd    NUMERIC(12, 6) NOT NULL DEFAULT 0,
    latency_ms  INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX run_steps_run_idx ON run_steps (run_id);
