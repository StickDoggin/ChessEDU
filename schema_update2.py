from db_setup import get_connection

def run_schema_update2():
    conn = get_connection()
    cur = conn.cursor()

    print("Running schema update 2...")

    # ─── PLAYER THRESHOLDS ────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_thresholds (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            game_type       TEXT NOT NULL,
            threshold_name  TEXT NOT NULL,
            value           FLOAT NOT NULL,
            source          TEXT DEFAULT 'default',
            confidence      FLOAT DEFAULT 0.5,
            sample_size     INTEGER DEFAULT 0,
            version         INTEGER DEFAULT 1,
            derived_from    TEXT DEFAULT 'default_v1',
            updated_at      TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (player_id, game_type, threshold_name)
        );
    """)
    print("  player_thresholds table created.")

    # ─── EVALUATION STATE PERFORMANCE ────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_state_performance (
            id                          SERIAL PRIMARY KEY,
            player_id                   INTEGER REFERENCES players(id),
            game_type                   TEXT NOT NULL,
            eval_state                  TEXT NOT NULL,
            avg_cpl                     FLOAT,
            blunder_rate                FLOAT,
            missed_opportunity_rate     FLOAT,
            avg_time_spent_ms           FLOAT,
            winning_conversion_rate     FLOAT,
            salvation_find_rate         FLOAT,
            equality_decision_rate      FLOAT,
            sample_size                 INTEGER DEFAULT 0,
            updated_at                  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (player_id, game_type, eval_state)
        );
    """)
    print("  evaluation_state_performance table created.")

    # ─── MOVES TABLE — psychological and context columns ─────────────────
    cur.execute("""
        ALTER TABLE moves
        ADD COLUMN IF NOT EXISTS mistake_score          FLOAT,
        ADD COLUMN IF NOT EXISTS position_eval_state    TEXT,
        ADD COLUMN IF NOT EXISTS missed_salvation       BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS salvation_eval_swing   INTEGER,
        ADD COLUMN IF NOT EXISTS resignation_mindset_flag BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS complacency_flag       BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS desperation_sacrifice  BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS swindle_attempt        BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS is_sacrifice           BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS sacrifice_type         TEXT,
        ADD COLUMN IF NOT EXISTS sacrifice_correct      BOOLEAN,
        ADD COLUMN IF NOT EXISTS is_repetition          BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS times_position_seen    INTEGER,
        ADD COLUMN IF NOT EXISTS tablebase_result       TEXT,
        ADD COLUMN IF NOT EXISTS tablebase_dtz          INTEGER,
        ADD COLUMN IF NOT EXISTS tablebase_deviation    INTEGER,
        ADD COLUMN IF NOT EXISTS analysis_quality       TEXT,
        ADD COLUMN IF NOT EXISTS analysis_confidence    FLOAT,
        ADD COLUMN IF NOT EXISTS opponent_time_pressure TEXT,
        ADD COLUMN IF NOT EXISTS increment_ms           INTEGER;
    """)
    print("  moves table updated with psychological columns.")

    # ─── GAMES TABLE — psychological and context columns ─────────────────
    cur.execute("""
        ALTER TABLE games
        ADD COLUMN IF NOT EXISTS accuracy_pct               FLOAT,
        ADD COLUMN IF NOT EXISTS ended_by_repetition        BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS repetition_offered_by      TEXT,
        ADD COLUMN IF NOT EXISTS missed_salvations          INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS complacency_blunders       INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS winning_position_converted BOOLEAN,
        ADD COLUMN IF NOT EXISTS max_advantage_reached      INTEGER,
        ADD COLUMN IF NOT EXISTS advantage_surrendered      BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS time_scramble_occurred     BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS time_scramble_start_move   INTEGER,
        ADD COLUMN IF NOT EXISTS scramble_winner            TEXT,
        ADD COLUMN IF NOT EXISTS session_streak             INTEGER,
        ADD COLUMN IF NOT EXISTS streak_cpl_delta           FLOAT;
    """)
    print("  games table updated with psychological columns.")

    # ─── SESSIONS TABLE — streak tracking ────────────────────────────────
    cur.execute("""
        ALTER TABLE sessions
        ADD COLUMN IF NOT EXISTS avg_accuracy       FLOAT,
        ADD COLUMN IF NOT EXISTS peak_cpl           FLOAT,
        ADD COLUMN IF NOT EXISTS fatigue_detected   BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS fatigue_start_game INTEGER;
    """)
    print("  sessions table updated.")

    # ─── WEAKNESS GRAPH — status tracking ────────────────────────────────
    cur.execute("""
        ALTER TABLE weakness_graph
        ADD COLUMN IF NOT EXISTS status             TEXT DEFAULT 'active',
        ADD COLUMN IF NOT EXISTS first_detected     DATE,
        ADD COLUMN IF NOT EXISTS last_occurred      DATE,
        ADD COLUMN IF NOT EXISTS resolution_date    DATE,
        ADD COLUMN IF NOT EXISTS regression_count   INTEGER DEFAULT 0,
        ADD COLUMN IF NOT EXISTS mastery_score      FLOAT DEFAULT 0.0,
        ADD COLUMN IF NOT EXISTS study_efficiency   FLOAT,
        ADD COLUMN IF NOT EXISTS estimated_study_hours FLOAT;
    """)
    print("  weakness_graph table updated.")

    # ─── ANALYSIS QUEUE — resume capability ──────────────────────────────
    cur.execute("""
        ALTER TABLE analysis_queue
        ADD COLUMN IF NOT EXISTS last_move_analyzed INTEGER DEFAULT 0;
    """)
    print("  analysis_queue updated with resume capability.")

    # ─── DEFAULT THRESHOLDS ───────────────────────────────────────────────
    # player_id = NULL means global default for all players
    defaults = [
        # Blitz thresholds
        (None, 'blitz', 'blunder_cpl',           200,  'default', 0.5),
        (None, 'blitz', 'mistake_cpl',            100,  'default', 0.5),
        (None, 'blitz', 'inaccuracy_cpl',          50,  'default', 0.5),
        (None, 'blitz', 'suboptimal_cpl',          20,  'default', 0.5),
        (None, 'blitz', 'critical_time_pct',      0.08, 'default', 0.5),
        (None, 'blitz', 'low_time_pct',           0.18, 'default', 0.5),
        (None, 'blitz', 'normal_time_pct',        0.40, 'default', 0.5),
        (None, 'blitz', 'blunder_score_threshold', 0.85, 'default', 0.5),
        (None, 'blitz', 'mistake_score_threshold', 0.60, 'default', 0.5),
        (None, 'blitz', 'inaccuracy_score_threshold', 0.35, 'default', 0.5),
        (None, 'blitz', 'suboptimal_score_threshold', 0.15, 'default', 0.5),

        # Rapid thresholds
        (None, 'rapid', 'blunder_cpl',           200,  'default', 0.5),
        (None, 'rapid', 'mistake_cpl',            100,  'default', 0.5),
        (None, 'rapid', 'inaccuracy_cpl',          50,  'default', 0.5),
        (None, 'rapid', 'suboptimal_cpl',          20,  'default', 0.5),
        (None, 'rapid', 'critical_time_pct',      0.05, 'default', 0.5),
        (None, 'rapid', 'low_time_pct',           0.12, 'default', 0.5),
        (None, 'rapid', 'normal_time_pct',        0.30, 'default', 0.5),
        (None, 'rapid', 'blunder_score_threshold', 0.85, 'default', 0.5),
        (None, 'rapid', 'mistake_score_threshold', 0.60, 'default', 0.5),
        (None, 'rapid', 'inaccuracy_score_threshold', 0.35, 'default', 0.5),
        (None, 'rapid', 'suboptimal_score_threshold', 0.15, 'default', 0.5),

        # Bullet thresholds
        (None, 'bullet', 'blunder_cpl',           250,  'default', 0.5),
        (None, 'bullet', 'mistake_cpl',            120,  'default', 0.5),
        (None, 'bullet', 'inaccuracy_cpl',          60,  'default', 0.5),
        (None, 'bullet', 'suboptimal_cpl',          25,  'default', 0.5),
        (None, 'bullet', 'critical_time_pct',      0.12, 'default', 0.5),
        (None, 'bullet', 'low_time_pct',           0.25, 'default', 0.5),
        (None, 'bullet', 'normal_time_pct',        0.50, 'default', 0.5),
        (None, 'bullet', 'blunder_score_threshold', 0.85, 'default', 0.5),
        (None, 'bullet', 'mistake_score_threshold', 0.60, 'default', 0.5),
        (None, 'bullet', 'inaccuracy_score_threshold', 0.35, 'default', 0.5),
        (None, 'bullet', 'suboptimal_score_threshold', 0.15, 'default', 0.5),

        # Classical thresholds
        (None, 'classical', 'blunder_cpl',           150,  'default', 0.5),
        (None, 'classical', 'mistake_cpl',             75,  'default', 0.5),
        (None, 'classical', 'inaccuracy_cpl',          35,  'default', 0.5),
        (None, 'classical', 'suboptimal_cpl',          15,  'default', 0.5),
        (None, 'classical', 'critical_time_pct',      0.03, 'default', 0.5),
        (None, 'classical', 'low_time_pct',           0.08, 'default', 0.5),
        (None, 'classical', 'normal_time_pct',        0.20, 'default', 0.5),
        (None, 'classical', 'blunder_score_threshold', 0.85, 'default', 0.5),
        (None, 'classical', 'mistake_score_threshold', 0.60, 'default', 0.5),
        (None, 'classical', 'inaccuracy_score_threshold', 0.35, 'default', 0.5),
        (None, 'classical', 'suboptimal_score_threshold', 0.15, 'default', 0.5),

        # Analysis quality thresholds (game-type independent)
        (None, 'all', 'high_quality_depth',         18,   'default', 0.9),
        (None, 'all', 'medium_quality_depth',        14,   'default', 0.7),
        (None, 'all', 'high_quality_time_s',          0.8,  'default', 0.9),
        (None, 'all', 'medium_quality_time_s',        0.4,  'default', 0.7),

        # Psychological pattern thresholds
        (None, 'all', 'resignation_mindset_eval',   -100,  'default', 0.5),
        (None, 'all', 'complacency_eval',            200,  'default', 0.5),
        (None, 'all', 'winning_advantage_eval',      200,  'default', 0.5),
        (None, 'all', 'salvation_min_swing',         150,  'default', 0.5),
        (None, 'all', 'tilt_cpl_multiplier',         1.3,  'default', 0.5),
        (None, 'all', 'premove_ms',                  500,  'default', 0.9),
        (None, 'all', 'panic_ms',                   2000,  'default', 0.8),
        (None, 'all', 'panic_clock_ms',            10000,  'default', 0.8),

        # Recency and Elo weighting
        (None, 'all', 'recency_half_life_days',      90,   'default', 0.7),
        (None, 'all', 'elo_proximity_scale',         150,  'default', 0.7),
    ]

    inserted = 0
    for row in defaults:
        cur.execute("""
            INSERT INTO player_thresholds
                (player_id, game_type, threshold_name, value, source, confidence)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (player_id, game_type, threshold_name) DO NOTHING
        """, row)
        if cur.rowcount == 1:
            inserted += 1

    print(f"  {inserted} default thresholds seeded.")

    # ─── ADDITIONAL INDEXES ───────────────────────────────────────────────
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_moves_mistake_score
            ON moves(mistake_score);
        CREATE INDEX IF NOT EXISTS idx_moves_eval_state
            ON moves(position_eval_state);
        CREATE INDEX IF NOT EXISTS idx_moves_missed_salvation
            ON moves(missed_salvation);
        CREATE INDEX IF NOT EXISTS idx_games_accuracy
            ON games(accuracy_pct);
        CREATE INDEX IF NOT EXISTS idx_games_advantage_surrendered
            ON games(advantage_surrendered);
        CREATE INDEX IF NOT EXISTS idx_thresholds_lookup
            ON player_thresholds(player_id, game_type, threshold_name);
        CREATE INDEX IF NOT EXISTS idx_eval_state_perf
            ON evaluation_state_performance(player_id, game_type);
    """)
    print("  additional indexes created.")

    conn.commit()
    cur.close()
    conn.close()
    print("\nSchema update 2 complete.")


if __name__ == "__main__":
    run_schema_update2()