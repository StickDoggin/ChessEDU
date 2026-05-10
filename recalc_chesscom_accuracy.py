"""
Recalculate accuracy_chesscom for all already-analyzed moves.

Run after the full analysis completes. Uses eval_before/eval_after
already stored in the moves table — no Stockfish re-run needed.

Formula mirrors accuracy_chesscom() in analyze_games.py:
  wp = 1 / (1 + 10^(-eval/400))          [logistic, CP-based]
  raw = max(0, 1 - |wp_before - wp_after|)
  decisiveness = min(1, |wins/total - 0.5| * 2)  [WDL-based, unchanged]
  position_weight = 1 - decisiveness * 0.7
  blended = raw * position_weight + 0.85 * (1 - position_weight)
  accuracy_chesscom = clamp(blended * 100, 0, 100)
"""
from db_setup import get_connection

conn = get_connection()
cur  = conn.cursor()

cur.execute("""
    UPDATE moves SET
        accuracy_chesscom = GREATEST(0.0, LEAST(100.0,
            (
                -- raw CP-based accuracy
                GREATEST(0.0, LEAST(1.0,
                    1.0 - ABS(
                        1.0 / (1.0 + POWER(10.0, -eval_before::float / 400.0))
                      - 1.0 / (1.0 + POWER(10.0, -eval_after::float  / 400.0))
                    )
                ))
                * (1.0 - decisiveness * 0.7)
                + 0.85 * (decisiveness * 0.7)
            ) * 100.0
        ))
    FROM (
        SELECT
            id,
            CASE
                WHEN wdl_wins_before IS NULL
                  OR (wdl_wins_before + wdl_draws_before + wdl_losses_before) = 0
                THEN 0.0
                ELSE LEAST(1.0,
                    ABS(
                        wdl_wins_before::float
                        / (wdl_wins_before + wdl_draws_before + wdl_losses_before)
                        - 0.5
                    ) * 2.0
                )
            END AS decisiveness
        FROM moves
        WHERE eval_before IS NOT NULL
          AND eval_after  IS NOT NULL
          AND accuracy_wdl IS NOT NULL
    ) sub
    WHERE moves.id = sub.id
""")

updated = cur.rowcount
conn.commit()
cur.close()
conn.close()

print(f"Updated accuracy_chesscom for {updated:,} moves.")
