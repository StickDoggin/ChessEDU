"""Seed drill_positions from own game history.

Selects moves where:
  - maia_probability < 0.15  (genuinely hard for 1650 Elo to find)
  - centipawn_loss >= 100     (significant mistake)
  - weakness_type = 'personal'

Each qualifying move becomes one drill_positions row (player-specific).
Uses DISTINCT ON (move_id) to pick one concept per move — highest-priority
concept from weakness_graph, falling back to the first concept found.
Skips moves already seeded (source_move_id deduplicated).
"""
import psycopg
from datetime import date

PLAYER_ID = 1
MAIA_THRESHOLD = 0.15
CPL_THRESHOLD = 100

conn = psycopg.connect(host='127.0.0.1', port=5432, dbname='chess_engine',
                       user='postgres', password='0088')
cur = conn.cursor()

# Find qualifying moves with their best concept (prefer weakness_graph active codes)
cur.execute("""
    WITH qualifying AS (
        SELECT m.id AS move_id, m.fen_before, m.best_move_uci, m.best_move_san,
               m.centipawn_loss
        FROM moves m
        JOIN games g ON g.id = m.game_id
        WHERE g.player_id = %s
          AND m.maia_probability < %s
          AND m.centipawn_loss >= %s
          AND m.best_move_uci IS NOT NULL
          AND m.fen_before IS NOT NULL
          AND m.weakness_type = 'personal'
    ),
    with_concept AS (
        SELECT DISTINCT ON (q.move_id)
               q.move_id, q.fen_before, q.best_move_uci, q.best_move_san,
               q.centipawn_loss,
               c.code AS concept_code
        FROM qualifying q
        JOIN move_concepts mc ON mc.move_id = q.move_id AND mc.is_primary_cause = TRUE
        JOIN concepts c ON c.id = mc.concept_id
        LEFT JOIN weakness_graph wg ON wg.concept_code = c.code
                                   AND wg.player_id = %s
                                   AND wg.status IN ('active', 'improving')
        ORDER BY q.move_id,
                 (wg.study_efficiency IS NOT NULL) DESC,
                 COALESCE(wg.study_efficiency, 0) DESC
    )
    SELECT wc.move_id, wc.fen_before, wc.best_move_uci, wc.best_move_san,
           wc.centipawn_loss, wc.concept_code
    FROM with_concept wc
    -- Skip moves already seeded
    WHERE NOT EXISTS (
        SELECT 1 FROM drill_positions dp
        WHERE dp.source_move_id = wc.move_id AND dp.player_id = %s
    )
""", (PLAYER_ID, MAIA_THRESHOLD, CPL_THRESHOLD, PLAYER_ID, PLAYER_ID))

rows = cur.fetchall()
print(f"Qualifying moves to seed: {len(rows):,}")

if not rows:
    print("Nothing to seed.")
    cur.close()
    conn.close()
    exit()

# Bulk insert
inserted = 0
skipped = 0
today = date.today()

for move_id, fen, best_uci, best_san, cpl, concept_code in rows:
    difficulty = min(1.0, (cpl or 100) / 500.0)
    try:
        cur.execute("""
            INSERT INTO drill_positions
                (player_id, source_move_id, concept_code, fen,
                 correct_move, correct_move_san,
                 difficulty, next_review, interval_days, ease_factor,
                 review_count, source)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, 2.5, 0, 'own_game')
        """, (PLAYER_ID, move_id, concept_code, fen,
              best_uci, best_san,
              difficulty, today))
        inserted += 1
    except Exception as e:
        skipped += 1
        if skipped <= 3:
            print(f"  Skip move_id={move_id}: {e}")

conn.commit()
print(f"Inserted: {inserted:,}  Skipped: {skipped:,}")

# Breakdown by concept code
cur.execute("""
    SELECT concept_code, COUNT(*)
    FROM drill_positions
    WHERE player_id = %s AND source = 'own_game'
    GROUP BY concept_code
    ORDER BY COUNT(*) DESC
""", (PLAYER_ID,))
print("\nOwn-game positions by concept code:")
for r in cur.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

cur.close()
conn.close()
