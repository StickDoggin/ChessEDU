"""Add missing performance indexes."""
import psycopg, time

conn = psycopg.connect(host='127.0.0.1', port=5432, dbname='chess_engine',
                       user='postgres', password='0088',
                       autocommit=True)
cur = conn.cursor()

indexes = [
    # move_concepts: concept_id lookup — used in every prescription query
    ("idx_move_concepts_concept_id",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_move_concepts_concept_id ON move_concepts(concept_id)"),
    # move_concepts: is_primary_cause filter
    ("idx_move_concepts_primary",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_move_concepts_primary ON move_concepts(concept_id, is_primary_cause) WHERE is_primary_cause = TRUE"),
    # games: composite (player_id, analyzed) for COUNT query
    ("idx_games_player_analyzed",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_games_player_analyzed ON games(player_id, analyzed)"),
    # drill_positions: (player_id, concept_code, next_review) for drill session
    ("idx_drill_player_concept_review",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_drill_player_concept_review ON drill_positions(player_id, concept_code, next_review)"),
    # drill_positions: (player_id IS NULL) for Lichess pool — use partial index
    ("idx_drill_lichess_review",
     "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_drill_lichess_review ON drill_positions(concept_code, next_review, puzzle_rating) WHERE player_id IS NULL"),
]

for name, ddl in indexes:
    print(f"Creating {name}...", end=' ', flush=True)
    t0 = time.time()
    try:
        cur.execute(ddl)
        print(f"done ({(time.time()-t0)*1000:.0f}ms)")
    except Exception as e:
        conn.rollback()
        print(f"SKIP ({e})")

# Re-benchmark after indexes
print()
codes = ['7.3.1','7.1.1','3.4.2','3.3.3','3.1.1','3.1.14','3.1.4','3.3.6','3.1.3','7.1.2']
t0 = time.time()
cur.execute("""
    WITH per_game AS (
        SELECT DISTINCT ON (c.code, m.game_id)
               c.code, m.game_id, m.id AS move_id, m.weakness_type
        FROM move_concepts mc
        JOIN moves m    ON m.id  = mc.move_id
        JOIN concepts c ON c.id  = mc.concept_id
        JOIN games g    ON g.id  = m.game_id
        WHERE g.player_id = 1 AND c.code = ANY(%s) AND mc.is_primary_cause = TRUE
        ORDER BY c.code, m.game_id DESC
    )
    SELECT code,
           array_agg(game_id ORDER BY game_id DESC) AS game_ids,
           array_agg(move_id ORDER BY game_id DESC) AS move_ids,
           COUNT(*) FILTER (WHERE weakness_type = 'personal') AS personal_count,
           COUNT(*) FILTER (WHERE weakness_type = 'bracket')  AS bracket_count
    FROM per_game
    GROUP BY code
""", (codes,))
cur.fetchall()
print(f"Batched query after indexes: {(time.time()-t0)*1000:.1f} ms")

cur.close()
conn.close()
