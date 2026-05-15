"""
generate_coaching_insights.py

Reads concept_position_pattern and generates specific coaching insights
using the Claude API. Results stored in coaching_insights table.

These replace generic client-side buildInsights() strings with
specific, data-grounded coaching text.

Run: python generate_coaching_insights.py
"""
import psycopg
import anthropic

DB = dict(host="localhost", port=5432, dbname="chess_engine",
          user="postgres", password="0088")

POSITION_TYPE_LABELS = {
    'rook_ending':           'rook endgames',
    'rook_and_minor_ending': 'rook and minor piece endings',
    'rook_imbalance_ending': 'rook imbalance endings',
    'king_pawn_ending':      'king and pawn endgames',
    'bishop_ending':         'bishop endgames',
    'knight_ending':         'knight endgames',
    'minor_piece_ending':    'minor piece endgames',
    'queen_ending':          'queen endgames',
    'double_rook_ending':    'double rook endgames',
    'queen_rook_ending':     'queen and rook positions',
    'open_middlegame':       'open middlegame positions',
    'closed_middlegame':     'closed middlegame positions',
    'semi_open_middlegame':  'semi-open middlegame positions',
    'complex_middlegame':    'complex middlegame positions',
    'simplified_middlegame': 'simplified middlegame positions',
}


def generate_insight(pattern: dict, concept_name: str) -> str:
    """Call Claude API to generate a specific coaching insight."""
    client = anthropic.Anthropic()

    pos_label = POSITION_TYPE_LABELS.get(
        pattern['position_type'],
        pattern['position_type'].replace('_', ' ')
    )

    trend_str = {
        'worsening': f"getting worse — up {pattern['months_worsening']} consecutive months",
        'improving': "improving recently",
        'stable':    "stable (not improving)",
    }.get(pattern['trend_direction'], 'stable')

    win_rate_pct  = round(pattern['win_rate_with_miss'] * 100)
    baseline_pct  = round(pattern['win_rate_baseline'] * 100)
    impact_pct    = round(abs(pattern['result_impact']) * 100)

    prompt = f"""You are a direct chess coach giving a player a specific insight about their game.

Data about this player's pattern:
- Weakness: {concept_name}
- Position type: {pos_label}
- Occurrences: {pattern['occurrence_count']} times across {pattern['game_count']} games
- Average centipawn loss when this fires: {pattern['avg_cpl']:.0f} CPL
- Maia deficit: {pattern['maia_deficit']:.3f} (how far below average 1600-rated player on finding these moves)
- Win rate when this fires: {win_rate_pct}% vs baseline {baseline_pct}%
- Result impact: losing {impact_pct}% more games when this pattern fires
- Trend: {trend_str}

Write ONE coaching insight (2-3 sentences max) that:
1. Names the specific problem with exact numbers from the data above
2. Explains why it matters specifically in {pos_label}
3. Gives one concrete thing to watch for in future games

Rules: No filler praise. Do not start with "I". Be direct and specific.
Return only the insight text, no labels."""

    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text.strip()


def main():
    conn = psycopg.connect(**DB)
    cur  = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS coaching_insights (
            id              SERIAL PRIMARY KEY,
            player_id       INTEGER NOT NULL,
            concept_code    VARCHAR(20),
            position_type   VARCHAR(40),
            insight_text    TEXT NOT NULL,
            priority_score  FLOAT,
            generated_at    TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(player_id, concept_code, position_type)
        )
    """)
    conn.commit()

    cur.execute("""
        SELECT
            cpp.concept_code, c.name,
            cpp.position_type,
            cpp.occurrence_count, cpp.game_count,
            cpp.avg_cpl, cpp.maia_deficit,
            cpp.win_rate_with_miss, cpp.win_rate_baseline,
            cpp.result_impact, cpp.trend_direction,
            cpp.months_worsening, cpp.priority_score
        FROM concept_position_pattern cpp
        JOIN concepts c ON c.code = cpp.concept_code
        WHERE cpp.player_id = 1
          AND cpp.priority_score > 0.15
          AND cpp.occurrence_count >= 10
          AND NOT EXISTS (
              SELECT 1 FROM coaching_insights ci
              WHERE ci.player_id = 1
                AND ci.concept_code = cpp.concept_code
                AND ci.position_type = cpp.position_type
          )
        ORDER BY cpp.priority_score DESC
        LIMIT 20
    """)
    patterns = cur.fetchall()
    print(f"Generating insights for {len(patterns)} patterns...")

    if not patterns:
        print("No qualifying patterns found. Run recalibrate_signals.py first.")
        cur.close()
        conn.close()
        return

    for row in patterns:
        (code, name, pos_type, occ, games, avg_cpl, maia_def,
         wr_with, wr_base, impact, trend, months_worse, priority) = row

        pattern = {
            'position_type':      pos_type,
            'occurrence_count':   occ,
            'game_count':         games,
            'avg_cpl':            avg_cpl or 0,
            'maia_deficit':       maia_def or 0,
            'win_rate_with_miss': wr_with or 0,
            'win_rate_baseline':  wr_base or 0.45,
            'result_impact':      impact or 0,
            'trend_direction':    trend or 'stable',
            'months_worsening':   months_worse or 0,
        }

        try:
            insight = generate_insight(pattern, name)
            cur.execute("""
                INSERT INTO coaching_insights
                    (player_id, concept_code, position_type, insight_text, priority_score)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (player_id, concept_code, position_type)
                DO UPDATE SET insight_text  = EXCLUDED.insight_text,
                              generated_at  = NOW()
            """, (1, code, pos_type, insight, priority))
            conn.commit()
            print(f"  [{priority:.3f}] {code} / {pos_type}:")
            print(f"    {insight[:120]}...")
        except Exception as e:
            print(f"  ERROR on {code}/{pos_type}: {e}")

    cur.close()
    conn.close()
    print("Done.")


if __name__ == '__main__':
    main()
