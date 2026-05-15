-- migrations/recalibrate_maia_delta.sql
-- Adds recalibration columns to maia_move_delta and creates
-- concept_position_pattern + coaching_insights tables.

-- Extend maia_move_delta with new columns
ALTER TABLE maia_move_delta
    ADD COLUMN IF NOT EXISTS is_consistent_miss  BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS miss_severity        VARCHAR(20),
    ADD COLUMN IF NOT EXISTS position_type        VARCHAR(40),
    ADD COLUMN IF NOT EXISTS recency_weight       FLOAT DEFAULT 1.0;

-- Per-(concept, position_type) pattern scoring table
CREATE TABLE IF NOT EXISTS concept_position_pattern (
    id                  SERIAL PRIMARY KEY,
    player_id           INTEGER NOT NULL,
    concept_code        VARCHAR(20) NOT NULL,
    position_type       VARCHAR(40) NOT NULL,
    phase               VARCHAR(20),

    occurrence_count    INTEGER DEFAULT 0,
    game_count          INTEGER DEFAULT 0,
    miss_rate           FLOAT,

    avg_cpl             FLOAT,
    avg_wp_delta        FLOAT,

    avg_maia_prob       FLOAT,
    bracket_avg_prob    FLOAT,
    maia_deficit        FLOAT,

    win_rate_with_miss  FLOAT,
    win_rate_baseline   FLOAT,
    result_impact       FLOAT,

    trend_direction     VARCHAR(10),
    trend_confidence    FLOAT,
    months_worsening    INTEGER DEFAULT 0,

    priority_score      FLOAT,

    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_id, concept_code, position_type)
);

CREATE INDEX IF NOT EXISTS idx_cpp_player_priority
    ON concept_position_pattern(player_id, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_cpp_concept
    ON concept_position_pattern(player_id, concept_code);

-- AI-generated coaching insight strings
CREATE TABLE IF NOT EXISTS coaching_insights (
    id              SERIAL PRIMARY KEY,
    player_id       INTEGER NOT NULL,
    concept_code    VARCHAR(20),
    position_type   VARCHAR(40),
    insight_text    TEXT NOT NULL,
    priority_score  FLOAT,
    generated_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(player_id, concept_code, position_type)
);
