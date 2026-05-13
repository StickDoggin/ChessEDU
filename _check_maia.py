"""Check remaining NULL maia_probability moves."""
import psycopg

conn = psycopg.connect(host='127.0.0.1', port=5432, dbname='chess_engine',
                       user='postgres', password='0088')
cur = conn.cursor()

cur.execute("""
    SELECT COUNT(*) FROM moves m
    JOIN games g ON g.id = m.game_id
    WHERE g.player_id = 1
      AND m.color = g.color
      AND m.maia_probability IS NULL
      AND g.analyzed = TRUE
""")
null_count = cur.fetchone()[0]
print(f'Remaining NULL maia_probability (analyzed games): {null_count:,}')

cur.execute("""
    SELECT COUNT(*) FROM moves m
    JOIN games g ON g.id = m.game_id
    WHERE g.player_id = 1
      AND m.color = g.color
      AND m.maia_probability IS NOT NULL
""")
done_count = cur.fetchone()[0]
print(f'Processed maia moves: {done_count:,}')

cur.close()
conn.close()
