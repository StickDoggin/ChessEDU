"""Add concept_code index to drill_positions for EXISTS lookups."""
import psycopg

conn = psycopg.connect(host='127.0.0.1', port=5432, dbname='chess_engine',
                       user='postgres', password='0088', autocommit=True)
cur = conn.cursor()

cur.execute("""
    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_drill_concept_code
    ON drill_positions(concept_code)
""")
print("Created idx_drill_concept_code")

# Warm the index
cur.execute("SELECT COUNT(*) FROM drill_positions WHERE concept_code = '7.3.1'")
print(f"7.3.1 count: {cur.fetchone()[0]}")
cur.execute("SELECT COUNT(*) FROM drill_positions WHERE concept_code = '3.4.2'")
print(f"3.4.2 count: {cur.fetchone()[0]}")

cur.close()
conn.close()
