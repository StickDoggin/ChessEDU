import psycopg
import requests
from dotenv import load_dotenv
import os

load_dotenv()

def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def create_tables():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS concepts (
            id          SERIAL PRIMARY KEY,
            code        TEXT UNIQUE NOT NULL,
            parent_code TEXT,
            name        TEXT NOT NULL,
            category    TEXT NOT NULL,
            description TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id          SERIAL PRIMARY KEY,
            username    TEXT NOT NULL,
            platform    TEXT NOT NULL,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (username, platform)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_epochs (
            id          SERIAL PRIMARY KEY,
            player_id   INTEGER REFERENCES players(id),
            game_type   TEXT NOT NULL,
            started_at  TIMESTAMPTZ,
            ended_at    TIMESTAMPTZ,
            elo_start   INTEGER,
            elo_end     INTEGER
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_ratings (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            game_type       TEXT NOT NULL,
            current_elo     INTEGER,
            fetched_at      TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (player_id, game_type)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            epoch_id        INTEGER REFERENCES player_epochs(id),
            source          TEXT NOT NULL,
            source_game_id  TEXT NOT NULL,
            played_at       TIMESTAMPTZ,
            color           TEXT,
            result          TEXT,
            result_type     TEXT,
            time_control    TEXT,
            game_type       TEXT,
            player_elo      INTEGER,
            opponent_elo    INTEGER,
            opening_eco     TEXT,
            opening_name    TEXT,
            opening_var     TEXT,
            total_moves     INTEGER,
            raw_pgn         TEXT,
            analyzed        BOOLEAN DEFAULT FALSE,
            analysis_priority INTEGER DEFAULT 5,
            analyzed_at     TIMESTAMPTZ,
            UNIQUE (source, source_game_id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS moves (
            id                          SERIAL PRIMARY KEY,
            game_id                     INTEGER REFERENCES games(id),
            player_id                   INTEGER REFERENCES players(id),
            move_number                 INTEGER,
            color                       TEXT,
            san                         TEXT,
            uci                         TEXT,
            fen_before                  TEXT,
            fen_after                   TEXT,

            clock_before_ms             INTEGER,
            clock_after_ms              INTEGER,
            time_spent_ms               INTEGER,
            increment_ms                INTEGER,
            time_pressure               TEXT,
            time_percentile             FLOAT,

            opponent_clock_before_ms    INTEGER,
            opponent_clock_after_ms     INTEGER,
            opponent_time_spent_ms      INTEGER,
            opponent_time_pressure      TEXT,

            phase                       TEXT,
            move_in_phase               INTEGER,

            eval_before                 INTEGER,
            eval_after                  INTEGER,
            best_eval                   INTEGER,
            centipawn_loss              INTEGER,
            best_move_uci               TEXT,
            best_move_san               TEXT,
            pv_line_1                   TEXT,
            pv_line_2                   TEXT,
            pv_line_3                   TEXT,
            analysis_depth              INTEGER,
            is_book_move                BOOLEAN,

            mistake_class               TEXT,
            mistake_severity            FLOAT,
            is_time_pressure_error      BOOLEAN,
            tactical_depth_required     INTEGER,
            opponent_capitalized        BOOLEAN,
            capitalization_move         INTEGER,
            capitalization_cpl_swing    INTEGER,
            exploit_window_moves        INTEGER,
            exploitability_score        FLOAT,
            pattern_tags                TEXT[]
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS move_concepts (
            move_id     INTEGER REFERENCES moves(id),
            concept_id  INTEGER REFERENCES concepts(id),
            relevance   FLOAT DEFAULT 1.0,
            PRIMARY KEY (move_id, concept_id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS time_pressure_thresholds (
            id              SERIAL PRIMARY KEY,
            game_type       TEXT NOT NULL,
            elo_bracket     TEXT NOT NULL,
            critical_pct    FLOAT NOT NULL,
            low_pct         FLOAT NOT NULL,
            normal_pct      FLOAT NOT NULL,
            computed_at     TIMESTAMPTZ DEFAULT NOW(),
            sample_size     INTEGER,
            UNIQUE (game_type, elo_bracket)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS player_snapshots (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER REFERENCES players(id),
            snapshot_date   DATE NOT NULL,
            game_type       TEXT NOT NULL,
            elo             INTEGER,
            games_analyzed  INTEGER,
            avg_cpl_overall             FLOAT,
            avg_cpl_opening             FLOAT,
            avg_cpl_middlegame          FLOAT,
            avg_cpl_endgame             FLOAT,
            blunder_rate                FLOAT,
            missed_tactic_rate          FLOAT,
            positional_error_rate       FLOAT,
            time_pressure_error_rate    FLOAT,
            avg_tactical_depth_failed   FLOAT,
            avg_tactical_depth_solved   FLOAT,
            avg_time_spent_opening_ms   FLOAT,
            avg_time_spent_middlegame_ms FLOAT,
            avg_time_spent_endgame_ms   FLOAT,
            critical_time_blunder_rate  FLOAT,
            avg_exploitability_score    FLOAT,
            opponent_capitalization_rate FLOAT,
            concept_scores              JSONB,
            top_weakness_1              TEXT,
            top_weakness_2              TEXT,
            top_weakness_3              TEXT,
            top_weakness_4              TEXT,
            top_weakness_5              TEXT,
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (player_id, snapshot_date, game_type)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS analysis_queue (
            id              SERIAL PRIMARY KEY,
            game_id         INTEGER REFERENCES games(id) UNIQUE,
            priority        INTEGER DEFAULT 5,
            status          TEXT DEFAULT 'pending',
            queued_at       TIMESTAMPTZ DEFAULT NOW(),
            started_at      TIMESTAMPTZ,
            completed_at    TIMESTAMPTZ,
            worker_id       TEXT,
            error_message   TEXT,
            retry_count     INTEGER DEFAULT 0
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("All tables created successfully.")


def add_analysis_columns():
    """Add analysis columns to games table if they don't exist yet."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        ALTER TABLE games
        ADD COLUMN IF NOT EXISTS analyzed BOOLEAN DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS analysis_priority INTEGER DEFAULT 5,
        ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMPTZ;
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Analysis columns verified.")


def fetch_and_store_current_ratings(username: str):
    """Pull current ratings directly from Chess.com player stats API."""
    url = f"https://api.chess.com/pub/player/{username}/stats"
    headers = {"User-Agent": "chess-study-engine/0.1 (personal project)"}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch ratings: HTTP {response.status_code}")
        return

    stats = response.json()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM players WHERE username = %s AND platform = 'chess.com'",
        (username.lower(),)
    )
    row = cur.fetchone()
    if not row:
        print(f"Player {username} not found in database. Run import first.")
        cur.close()
        conn.close()
        return
    player_id = row[0]

    rating_map = {
        "chess_rapid":   "rapid",
        "chess_blitz":   "blitz",
        "chess_bullet":  "bullet",
        "chess_daily":   "classical",
    }

    print("Current ratings from Chess.com:")
    for api_key, game_type in rating_map.items():
        section = stats.get(api_key, {})
        elo = section.get("last", {}).get("rating")
        if elo:
            cur.execute("""
                INSERT INTO player_ratings (player_id, game_type, current_elo, fetched_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (player_id, game_type)
                DO UPDATE SET current_elo = EXCLUDED.current_elo, fetched_at = NOW()
            """, (player_id, game_type, elo))
            print(f"  {game_type}: {elo}")

    conn.commit()
    cur.close()
    conn.close()
    print("Current ratings stored.")


def populate_analysis_queue(username: str):
    """Add all unanalyzed games to the queue with smart priority scoring."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT game_type, current_elo FROM player_ratings pr
        JOIN players p ON p.id = pr.player_id
        WHERE p.username = %s AND p.platform = 'chess.com'
    """, (username.lower(),))
    ratings = {row[0]: row[1] for row in cur.fetchall()}

    rapid_elo = ratings.get("rapid", 1500)
    blitz_elo = ratings.get("blitz", 1500)
    bracket_low  = min(rapid_elo, blitz_elo) - 150
    bracket_high = max(rapid_elo, blitz_elo) + 150

    print(f"  Using Elo bracket {bracket_low}–{bracket_high} for prioritization.")

    cur.execute("""
        INSERT INTO analysis_queue (game_id, priority)
        SELECT
            g.id,
            (
                CASE WHEN g.played_at > NOW() - INTERVAL '60 days'  THEN 5
                     WHEN g.played_at > NOW() - INTERVAL '6 months' THEN 3
                     WHEN g.played_at > NOW() - INTERVAL '18 months' THEN 1
                     ELSE 0 END
                +
                CASE WHEN g.result = 'loss' THEN 3
                     WHEN g.result = 'draw' THEN 1
                     ELSE 0 END
                +
                CASE WHEN g.game_type = 'rapid'     THEN 3
                     WHEN g.game_type = 'blitz'     THEN 2
                     WHEN g.game_type = 'bullet'    THEN 0
                     ELSE 0 END
                +
                CASE WHEN g.player_elo BETWEEN %s AND %s THEN 2
                     ELSE 0 END
            ) as priority
        FROM games g
        WHERE g.analyzed = FALSE
        ON CONFLICT (game_id) DO NOTHING;
    """, (bracket_low, bracket_high))

    count = cur.rowcount
    conn.commit()
    cur.close()
    conn.close()
    print(f"  Added {count} games to analysis queue.")


if __name__ == "__main__":
    create_tables()
    add_analysis_columns()
    fetch_and_store_current_ratings("StickDoggin")
    populate_analysis_queue("StickDoggin")