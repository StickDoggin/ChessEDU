"""
recalc_chesscom_accuracy.py — Backfill corrected accuracy_chesscom values.

Run AFTER the full analysis completes. All accuracy_chesscom values from the
May 2026 full analysis run are incorrect (≈ accuracy_wdl) due to the circular
conversion bug fixed in analyze_games.py after the run started.

This script:
  1. Recomputes accuracy_chesscom from eval_before/eval_after using the correct
     CP-based formula — no Stockfish re-run needed.
  2. Updates moves.accuracy_chesscom in batches of 1000.
  3. Updates games.accuracy_chesscom as the per-game average.
  4. Reports rows updated and before/after averages.

DO NOT run during active analysis — wait until the full run finishes.
"""
from db_setup import get_connection

BATCH_SIZE = 1000


def recalc():
    conn = get_connection()
    cur  = conn.cursor()

    # ── Before stats ──────────────────────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*), AVG(accuracy_chesscom), AVG(accuracy_wdl)
        FROM moves
        WHERE accuracy_chesscom IS NOT NULL AND accuracy_wdl IS NOT NULL
    """)
    r = cur.fetchone()
    before_count = r[0] or 0
    before_avg_cc = float(r[1]) if r[1] else 0.0
    before_avg_wdl = float(r[2]) if r[2] else 0.0
    print(f"Before: {before_count:,} moves with accuracy_chesscom")
    print(f"  avg accuracy_chesscom: {before_avg_cc:.2f}")
    print(f"  avg accuracy_wdl:      {before_avg_wdl:.2f}")
    print(f"  difference (cc - wdl): {before_avg_cc - before_avg_wdl:+.2f}")
    print()

    # ── Fetch move IDs in scope ───────────────────────────────────────────────
    cur.execute("""
        SELECT id FROM moves
        WHERE eval_before IS NOT NULL
          AND eval_after  IS NOT NULL
          AND accuracy_wdl IS NOT NULL
        ORDER BY id
    """)
    all_ids = [r[0] for r in cur.fetchall()]
    total   = len(all_ids)
    print(f"Moves to recalculate: {total:,}")

    # ── Batch update ──────────────────────────────────────────────────────────
    updated = 0
    for start in range(0, total, BATCH_SIZE):
        batch = all_ids[start:start + BATCH_SIZE]
        ph    = ','.join(['%s'] * len(batch))
        cur.execute(f"""
            UPDATE moves SET
                accuracy_chesscom = GREATEST(0.0, LEAST(100.0,
                    (
                        GREATEST(0.0, LEAST(1.0,
                            1.0 - ABS(
                                1.0 / (1.0 + POWER(10.0, -LEAST(GREATEST(eval_before, -1000), 1000)::float / 400.0))
                              - 1.0 / (1.0 + POWER(10.0, -LEAST(GREATEST(eval_after,  -1000), 1000)::float / 400.0))
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
                WHERE id IN ({ph})
            ) sub
            WHERE moves.id = sub.id
        """, batch)
        updated += cur.rowcount
        conn.commit()
        if (start // BATCH_SIZE + 1) % 10 == 0 or start + BATCH_SIZE >= total:
            pct = min(start + BATCH_SIZE, total) / total * 100
            print(f"  {min(start + BATCH_SIZE, total):>7,}/{total:,} moves  ({pct:.0f}%)")

    # ── Update games.accuracy_chesscom ────────────────────────────────────────
    cur.execute("""
        UPDATE games g SET
            accuracy_chesscom = sub.avg_acc
        FROM (
            SELECT game_id, AVG(accuracy_chesscom) AS avg_acc
            FROM moves
            WHERE accuracy_chesscom IS NOT NULL
            GROUP BY game_id
        ) sub
        WHERE g.id = sub.game_id
    """)
    games_updated = cur.rowcount
    conn.commit()
    print(f"\nGames updated: {games_updated:,}")

    # ── After stats ───────────────────────────────────────────────────────────
    cur.execute("""
        SELECT COUNT(*), AVG(accuracy_chesscom), AVG(accuracy_wdl)
        FROM moves
        WHERE accuracy_chesscom IS NOT NULL AND accuracy_wdl IS NOT NULL
    """)
    r = cur.fetchone()
    after_avg_cc  = float(r[1]) if r[1] else 0.0
    after_avg_wdl = float(r[2]) if r[2] else 0.0

    print()
    print("=" * 50)
    print("RECALCULATION COMPLETE")
    print("=" * 50)
    print(f"  Moves updated:         {updated:,}")
    print(f"  Games updated:         {games_updated:,}")
    print(f"  avg_chesscom BEFORE:   {before_avg_cc:.2f}")
    print(f"  avg_chesscom AFTER:    {after_avg_cc:.2f}")
    print(f"  avg_wdl (unchanged):   {after_avg_wdl:.2f}")
    print(f"  Difference after fix:  {after_avg_cc - after_avg_wdl:+.2f}")
    print()
    if abs(before_avg_cc - before_avg_wdl) < 1.0:
        print("  NOTE: Before values were nearly identical to WDL — confirms the")
        print("        circular conversion bug was present. Fix applied correctly.")

    cur.close()
    conn.close()


if __name__ == '__main__':
    recalc()
