import psycopg
from db_setup import get_connection

def run_schema_update():
    conn = get_connection()
    cur = conn.cursor()

    print("Running schema update...")

    # ─── GAMES TABLE additions ───────────────────────────────────────────
    cur.execute("""
        ALTER TABLE games
        ADD COLUMN IF NOT EXISTS novelty_move        INTEGER,
        ADD COLUMN IF NOT EXISTS novelty_fen         TEXT,
        ADD COLUMN IF NOT EXISTS session_id          INTEGER,
        ADD COLUMN IF NOT EXISTS opponent_avg_cpl    FLOAT,
        ADD COLUMN IF NOT EXISTS opponent_accuracy_pct FLOAT,
        ADD COLUMN IF NOT EXISTS opponent_time_pressure_moves INTEGER;
    """)
    print("  games table updated.")

    # ─── MOVES TABLE additions ────────────────────────────────────────────
    cur.execute("""
        ALTER TABLE moves
        ADD COLUMN IF NOT EXISTS played_move_rank       INTEGER,
        ADD COLUMN IF NOT EXISTS played_move_cp         INTEGER,
        ADD COLUMN IF NOT EXISTS pv_line_4              TEXT,
        ADD COLUMN IF NOT EXISTS pv_line_5              TEXT,
        ADD COLUMN IF NOT EXISTS contextual_severity    FLOAT,
        ADD COLUMN IF NOT EXISTS position_tension       FLOAT,
        ADD COLUMN IF NOT EXISTS position_complexity    FLOAT,
        ADD COLUMN IF NOT EXISTS candidate_move_count   INTEGER,
        ADD COLUMN IF NOT EXISTS is_only_move           BOOLEAN,
        ADD COLUMN IF NOT EXISTS moves_since_novelty    INTEGER,
        ADD COLUMN IF NOT EXISTS is_likely_premove      BOOLEAN,
        ADD COLUMN IF NOT EXISTS is_likely_panic        BOOLEAN,
        ADD COLUMN IF NOT EXISTS mutual_blunder_window  BOOLEAN,
        ADD COLUMN IF NOT EXISTS cumulative_drift_5     FLOAT,
        ADD COLUMN IF NOT EXISTS drift_flag             BOOLEAN;
    """)
    print("  moves table updated.")

    # ─── MOVE CONCEPTS additions ──────────────────────────────────────────
    cur.execute("""
        ALTER TABLE move_concepts
        ADD COLUMN IF NOT EXISTS attribution_weight  FLOAT DEFAULT 1.0,
        ADD COLUMN IF NOT EXISTS cpl_attributed      INTEGER,
        ADD COLUMN IF NOT EXISTS detection_method    TEXT,
        ADD COLUMN IF NOT EXISTS is_primary_cause    BOOLEAN DEFAULT FALSE;
    """)
    print("  move_concepts table updated.")

    # ─── SESSIONS ─────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            started_at      TIMESTAMPTZ,
            ended_at        TIMESTAMPTZ,
            game_count      INTEGER,
            game_type       TEXT,
            avg_cpl         FLOAT,
            tilt_detected   BOOLEAN DEFAULT FALSE,
            tilt_coefficient FLOAT,
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    print("  sessions table created.")

    # ─── ELO HISTORY ──────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS elo_history (
            id          SERIAL PRIMARY KEY,
            player_id   INTEGER REFERENCES players(id),
            game_type   TEXT NOT NULL,
            elo         INTEGER NOT NULL,
            recorded_at TIMESTAMPTZ NOT NULL,
            game_id     INTEGER REFERENCES games(id)
        );
    """)

    # Populate elo_history from existing games data
    cur.execute("""
        INSERT INTO elo_history (player_id, game_type, elo, recorded_at, game_id)
        SELECT player_id, game_type, player_elo, played_at, id
        FROM games
        WHERE player_elo IS NOT NULL
        ON CONFLICT DO NOTHING;
    """)
    print("  elo_history table created and populated.")

    # ─── OPENINGS ─────────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS openings (
            eco         TEXT NOT NULL,
            name        TEXT NOT NULL,
            pgn         TEXT,
            uci_moves   TEXT,
            epd         TEXT,
            PRIMARY KEY (eco, name)
        );
    """)
    print("  openings table created.")

    # ─── WEAKNESS GRAPH ────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weakness_graph (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            concept_code    TEXT REFERENCES concepts(code),
            game_type       TEXT NOT NULL,

            occurrence_count        INTEGER DEFAULT 0,
            occurrence_rate         FLOAT,
            avg_cpl_when_occurs     FLOAT,
            avg_contextual_severity FLOAT,
            avg_attribution_weight  FLOAT,

            trend_30_days           FLOAT,
            trend_90_days           FLOAT,

            avg_exploitability              FLOAT,
            opponent_capitalization_rate    FLOAT,

            estimated_elo_impact    FLOAT,
            primary_study_module    TEXT,

            updated_at  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (player_id, concept_code, game_type)
        );
    """)
    print("  weakness_graph table created.")

    # ─── CONCEPT STUDY MAPPING ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS concept_study_mapping (
            concept_code            TEXT REFERENCES concepts(code),
            study_module            TEXT NOT NULL,
            study_subtype           TEXT NOT NULL,
            effectiveness_score     FLOAT DEFAULT 0.5,
            min_attribution_weight  FLOAT DEFAULT 0.3,
            elo_bracket_min         INTEGER,
            elo_bracket_max         INTEGER,
            PRIMARY KEY (concept_code, study_module, study_subtype)
        );
    """)
    print("  concept_study_mapping table created.")

    # ─── DRILL POSITIONS ──────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drill_positions (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            source_move_id  INTEGER REFERENCES moves(id),
            concept_code    TEXT REFERENCES concepts(code),
            fen             TEXT NOT NULL,
            correct_move    TEXT NOT NULL,
            correct_move_san TEXT,
            difficulty      FLOAT DEFAULT 0.5,

            next_review     DATE DEFAULT CURRENT_DATE,
            interval_days   INTEGER DEFAULT 1,
            ease_factor     FLOAT DEFAULT 2.5,
            review_count    INTEGER DEFAULT 0,
            last_result     TEXT,

            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    print("  drill_positions table created.")

    # ─── DRILL ATTEMPTS ───────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drill_attempts (
            id              SERIAL PRIMARY KEY,
            drill_id        INTEGER REFERENCES drill_positions(id),
            player_id       INTEGER REFERENCES players(id),
            attempted_at    TIMESTAMPTZ DEFAULT NOW(),
            move_played     TEXT,
            was_correct     BOOLEAN,
            time_spent_ms   INTEGER,
            hint_used       BOOLEAN DEFAULT FALSE,
            new_interval    INTEGER,
            new_ease_factor FLOAT
        );
    """)
    print("  drill_attempts table created.")

    # ─── STUDY SESSIONS ───────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            session_date    DATE DEFAULT CURRENT_DATE,
            module_type     TEXT,
            concept_codes   TEXT[],
            duration_mins   INTEGER,
            positions_seen  INTEGER DEFAULT 0,
            positions_solved INTEGER DEFAULT 0,
            avg_solve_time_ms INTEGER,
            difficulty_avg  FLOAT,
            completed_at    TIMESTAMPTZ
        );
    """)
    print("  study_sessions table created.")

    # ─── IMPORT LOG ───────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS import_log (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            platform        TEXT,
            imported_at     TIMESTAMPTZ DEFAULT NOW(),
            games_found     INTEGER DEFAULT 0,
            games_inserted  INTEGER DEFAULT 0,
            games_skipped   INTEGER DEFAULT 0,
            errors          INTEGER DEFAULT 0,
            last_game_date  DATE
        );
    """)
    print("  import_log table created.")

    # ─── ANALYSIS LOG ─────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analysis_log (
            id                  SERIAL PRIMARY KEY,
            started_at          TIMESTAMPTZ DEFAULT NOW(),
            completed_at        TIMESTAMPTZ,
            games_analyzed      INTEGER DEFAULT 0,
            moves_annotated     INTEGER DEFAULT 0,
            avg_depth           FLOAT,
            avg_time_per_move_ms FLOAT,
            errors              INTEGER DEFAULT 0
        );
    """)
    print("  analysis_log table created.")

    # ─── INDEXES for query performance ────────────────────────────────────
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_moves_game_id 
            ON moves(game_id);
        CREATE INDEX IF NOT EXISTS idx_moves_player_id 
            ON moves(player_id);
        CREATE INDEX IF NOT EXISTS idx_moves_mistake_class 
            ON moves(mistake_class);
        CREATE INDEX IF NOT EXISTS idx_moves_phase 
            ON moves(phase);
        CREATE INDEX IF NOT EXISTS idx_games_player_id 
            ON games(player_id);
        CREATE INDEX IF NOT EXISTS idx_games_analyzed 
            ON games(analyzed);
        CREATE INDEX IF NOT EXISTS idx_games_played_at 
            ON games(played_at);
        CREATE INDEX IF NOT EXISTS idx_games_game_type 
            ON games(game_type);
        CREATE INDEX IF NOT EXISTS idx_analysis_queue_status 
            ON analysis_queue(status);
        CREATE INDEX IF NOT EXISTS idx_analysis_queue_priority 
            ON analysis_queue(priority DESC);
        CREATE INDEX IF NOT EXISTS idx_weakness_graph_player 
            ON weakness_graph(player_id);
        CREATE INDEX IF NOT EXISTS idx_elo_history_player 
            ON elo_history(player_id, game_type);
        CREATE INDEX IF NOT EXISTS idx_drill_positions_review 
            ON drill_positions(player_id, next_review);
    """)
    print("  indexes created.")

    conn.commit()
    cur.close()
    conn.close()
    print("\nSchema update complete.")

if __name__ == "__main__":
    run_schema_update()