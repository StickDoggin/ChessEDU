"""
test_drill_session.py — Simulate a drill session: 5 correct, 2 incorrect.

Shows how SM-2 fields evolve after each solve, then logs the session
to study_sessions and resets the affected rows so the DB stays clean.

Usage:
  python test_drill_session.py [player_id]   (default: 1)
"""

import sys
import random
from datetime import date
from drill_session import (
    build_session, update_sm2,
    start_session, finish_session,
    top_weakness_codes,
)
from db_setup import get_connection

PLAYER_ID    = int(sys.argv[1]) if len(sys.argv) > 1 else 1
SESSION_MINS = 7    # enough for 7 positions
TARGET_DIFF  = 0.45 # mid-range puzzles for the test

# 5 correct then 2 incorrect (0-indexed positions 5 and 6 are wrong)
INCORRECT_INDICES = {5, 6}
SOLVE_TIMES_MS    = [8200, 12400, 6100, 15800, 9700, 22000, 18500]


def _reset_positions(drill_ids: list) -> None:
    """Undo SM-2 updates on the test rows so they stay as fresh puzzles."""
    if not drill_ids:
        return
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE drill_positions SET
            interval_days = 1,
            ease_factor   = 2.5,
            review_count  = 0,
            next_review   = CURRENT_DATE,
            last_result   = NULL
        WHERE id = ANY(%s)
    """, (drill_ids,))
    conn.commit()
    cur.close(); conn.close()


def run_test():
    print("=" * 65)
    print("  DRILL SESSION SIMULATION")
    print(f"  player_id={PLAYER_ID}  session={SESSION_MINS} min  target_diff={TARGET_DIFF}")
    print("=" * 65)

    # ── Build session ──────────────────────────────────────────────────────────
    codes = top_weakness_codes(PLAYER_ID, limit=6)
    if not codes:
        # Fallback: common tactical codes guaranteed to have Lichess puzzles
        codes = ['3.1.1', '3.1.2', '3.2.1', '3.3.6', '3.1.7', '3.1.4']
    print(f"\nConcept codes: {codes}")

    positions = build_session(PLAYER_ID, codes, SESSION_MINS, TARGET_DIFF)
    if len(positions) < 7:
        print(f"\nWARNING: Only {len(positions)} positions found "
              f"(need 7 for this test). Widening difficulty window...")
        positions = build_session(PLAYER_ID, codes, SESSION_MINS,
                                  target_difficulty=0.5)

    if not positions:
        print("No due positions found. Verify drill_positions is seeded.")
        sys.exit(1)

    # Trim to exactly 7 for the simulation
    positions = positions[:7]
    drill_ids = [p['id'] for p in positions]

    own_n  = sum(1 for p in positions if p['source_type'] == 'own_game')
    lich_n = sum(1 for p in positions if p['source_type'] == 'lichess')
    avg_d  = sum(p['difficulty'] for p in positions) / len(positions)

    print(f"\nSession: {len(positions)} positions  "
          f"(OwnGame={own_n}  Lichess={lich_n}  "
          f"avg_diff={avg_d:.3f})")
    print()

    # ── Log session start ──────────────────────────────────────────────────────
    session_id = start_session(PLAYER_ID, codes, SESSION_MINS)

    # ── Simulate solves ────────────────────────────────────────────────────────
    print(f"  {'#':<3} {'Code':<8} {'Diff':>5}  {'Result':<10} "
          f"{'Time':>6}  {'Int':>5}  {'Ease':>5}  {'NextReview':<12}")
    print(f"  {'-'*3} {'-'*8} {'-'*5}  {'-'*10} "
          f"{'-'*6}  {'-'*5}  {'-'*5}  {'-'*12}")

    solved       = 0
    solve_times  = []
    difficulties = []

    for i, pos in enumerate(positions):
        correct   = i not in INCORRECT_INDICES
        t_ms      = SOLVE_TIMES_MS[i]
        result    = 'CORRECT  ' if correct else 'INCORRECT'

        sm2 = update_sm2(pos['id'], correct=correct, solve_time_ms=t_ms)

        if correct:
            solved += 1
        solve_times.append(t_ms)
        difficulties.append(pos['difficulty'])

        print(f"  {i+1:<3} {pos['concept_code']:<8} {pos['difficulty']:>5.3f}  "
              f"{result}  {t_ms/1000:>5.1f}s  "
              f"{sm2['interval']:>5}d  "
              f"{sm2['ease_factor']:>5.3f}  "
              f"{sm2['next_review']}")

    # ── Session summary ────────────────────────────────────────────────────────
    avg_diff = sum(difficulties) / len(difficulties)
    finish_session(session_id,
                   positions_seen=len(positions),
                   positions_solved=solved,
                   solve_times_ms=solve_times,
                   difficulty_avg=avg_diff)

    avg_time_s = sum(solve_times) / len(solve_times) / 1000
    print()
    print("=" * 65)
    print("  SESSION COMPLETE")
    print("=" * 65)
    print(f"  Session ID:        {session_id}")
    print(f"  Positions seen:    {len(positions)}")
    print(f"  Solved correctly:  {solved}/{len(positions)}")
    print(f"  Avg solve time:    {avg_time_s:.1f}s")
    print(f"  Avg difficulty:    {avg_diff:.3f}")
    print()

    # ── SM-2 explanation ───────────────────────────────────────────────────────
    print("  SM-2 SCHEDULE LOGIC:")
    print("    Correct   -> ease +0.05; interval: 1 -> 3 -> round(prev*ease)")
    print("    Incorrect -> ease -0.20 (min 1.30); interval reset to 1 day")
    print()
    print("  EXAMPLE TRAJECTORY (position #1, correct 3 times):")
    ease, interval = 2.5, 1
    for n in range(1, 4):
        ease = min(2.50, ease + 0.05)
        if n == 1: interval = 1
        elif n == 2: interval = 3
        else: interval = round(interval * ease)
        rev = date.today().toordinal() + interval
        print(f"    Review #{n}: interval={interval}d  ease={ease:.3f}  "
              f"next={date.fromordinal(rev)}")
    print()

    # ── Cleanup: reset test rows so they stay fresh ────────────────────────────
    _reset_positions(drill_ids)
    print(f"  [Test cleanup: reset {len(drill_ids)} drill_positions rows to fresh state]")
    print()


if __name__ == '__main__':
    run_test()
