"""
drill_session.py — Serve and score spaced-repetition drill sessions.

Build a session from due drill_positions weighted toward the player's
top weaknesses, mix player game positions with Lichess puzzles (70/30),
and apply SM-2 after each solve.

PUBLIC API
----------
  build_session(player_id, concept_codes, session_length_mins, target_difficulty)
      -> list[dict]   ordered positions for the session

  update_sm2(drill_id, correct, solve_time_ms)
      -> dict         new SM-2 state

  start_session(player_id, concept_codes, session_length_mins, module_type)
      -> int          session_id

  finish_session(session_id, positions_seen, positions_solved,
                 solve_times_ms, difficulty_avg)

  top_weakness_codes(player_id, limit)
      -> list[str]    concept codes ranked by estimated_elo_impact
"""

import sys
from datetime import date, timedelta
from typing import Optional
from db_setup import get_connection

# ── SM-2 constants ─────────────────────────────────────────────────────────────
EASE_MIN       = 1.30
EASE_MAX       = 2.50
EASE_CORRECT   = +0.05   # ease bump on correct answer
EASE_INCORRECT = -0.20   # ease penalty on miss
INTERVAL_MIN   = 1       # days

# ── Session sizing ─────────────────────────────────────────────────────────────
POSITIONS_PER_MIN = 1    # rough throughput: 1 position per minute of study time
OWN_GAME_FRACTION = 0.70 # 70% player's own game positions
LICHESS_FRACTION  = 0.30 # 30% global Lichess puzzles
DIFF_WINDOW       = 0.20 # ±0.20 around target difficulty

# ── Calculation depth constants (3.3.6.c) ─────────────────────────────────────
# solution_depth for Lichess puzzles is 1 (single key move stored in correct_move).
# We use puzzle_rating as the depth proxy: depth_ceiling maps to rating range
# depth_ceiling=1 → 1000-1400, +2=3 → 1800-2200, +5=6 → 2600+
DEPTH_PROGRESSIVE_CODE  = '3.3.6.c'
DEPTH_CEILING_WINDOW    = 2   # serve puzzles from depth_ceiling to depth_ceiling+2
DEPTH_ADVANCE_STREAK    = 5   # consecutive correct at ceiling before advancing
DEPTH_RATING_BASE       = 800   # puzzle_rating = DEPTH_RATING_BASE + depth_ceiling * 400
DEPTH_RATING_WINDOW     = 400   # rating band width per depth level


# ── Internal helpers ───────────────────────────────────────────────────────────

def _target_difficulty(cur, player_id: int) -> float:
    """
    Estimate target difficulty from recently failed positions.
    Falls back to 0.50 if no data.
    """
    cur.execute("""
        SELECT AVG(difficulty)
        FROM (
            SELECT difficulty FROM drill_positions
            WHERE player_id = %s
              AND last_result = 'incorrect'
              AND review_count > 0
            ORDER BY next_review DESC
            LIMIT 100
        ) sub
    """, (player_id,))
    r = cur.fetchone()
    return float(r[0]) if r and r[0] else 0.50


def _get_depth_ceiling(cur, player_id: int, game_type: str = 'rapid') -> int:
    """Return the player's current depth_ceiling for 3.3.6.c drills (default 3)."""
    cur.execute("""
        SELECT depth_ceiling FROM player_calculation_profile
        WHERE player_id = %s AND game_type = %s
    """, (player_id, game_type))
    row = cur.fetchone()
    return int(row[0]) if row else 3


def _fetch_positions(cur, player_id_filter, concept_codes: list,
                     today: date, diff_lo: float, diff_hi: float,
                     limit: int, exclude_ids: tuple = (),
                     depth_range: tuple = None) -> list:
    """
    Fetch due drill_positions for a given player_id filter.
    player_id_filter=None → Lichess pool; otherwise → player's own positions.
    depth_range: (min_depth, max_depth) — used only for 3.3.6.c depth-progressive mode.
    """
    cols = ('id', 'concept_code', 'fen', 'correct_move', 'correct_move_san',
            'difficulty', 'source_move_id', 'lichess_puzzle_id', 'puzzle_rating',
            'solution_depth')

    depth_clause = ""
    depth_args: tuple = ()
    if depth_range:
        # depth_range is (min_rating, max_rating) — puzzle_rating proxy for depth
        depth_clause = "AND (puzzle_rating BETWEEN %s AND %s OR puzzle_rating IS NULL)"
        depth_args = depth_range

    if player_id_filter is None:
        # Lichess global pool
        exc_clause = "AND id <> ALL(%s)" if exclude_ids else ""
        exc_arg    = (list(exclude_ids),) if exclude_ids else ()
        cur.execute(f"""
            SELECT id, concept_code, fen, correct_move, correct_move_san,
                   difficulty, source_move_id, lichess_puzzle_id, puzzle_rating,
                   solution_depth
            FROM drill_positions
            WHERE player_id IS NULL
              AND concept_code = ANY(%s)
              AND next_review <= %s
              AND difficulty BETWEEN %s AND %s
              {depth_clause}
              {exc_clause}
            ORDER BY next_review ASC, RANDOM()
            LIMIT %s
        """, (concept_codes, today, diff_lo, diff_hi) + depth_args + exc_arg + (limit,))
    else:
        # Player's own game-sourced positions
        cur.execute(f"""
            SELECT id, concept_code, fen, correct_move, correct_move_san,
                   difficulty, source_move_id, lichess_puzzle_id, puzzle_rating,
                   solution_depth
            FROM drill_positions
            WHERE player_id = %s
              AND concept_code = ANY(%s)
              AND next_review <= %s
              AND difficulty BETWEEN %s AND %s
              AND source_move_id IS NOT NULL
              {depth_clause}
            ORDER BY next_review ASC, RANDOM()
            LIMIT %s
        """, (player_id_filter, concept_codes, today, diff_lo, diff_hi)
             + depth_args + (limit,))

    rows = cur.fetchall()
    result = []
    for row in rows:
        d = dict(zip(cols, row))
        d['source_type'] = 'lichess' if player_id_filter is None else 'own_game'
        result.append(d)
    return result


# ── Public API ─────────────────────────────────────────────────────────────────

def top_weakness_codes(player_id: int, limit: int = 10) -> list:
    """
    Return the player's top concept_codes from weakness_graph,
    ranked by estimated_elo_impact descending.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT concept_code
        FROM weakness_graph
        WHERE player_id = %s
          AND status IN ('active', 'improving')
        ORDER BY estimated_elo_impact DESC
        LIMIT %s
    """, (player_id, limit))
    codes = [r[0] for r in cur.fetchall()]
    cur.close(); conn.close()
    return codes


def build_session(player_id: int,
                  concept_codes: list,
                  session_length_mins: int = 20,
                  target_difficulty: Optional[float] = None,
                  game_type: str = 'rapid') -> list:
    """
    Build an ordered list of drill positions for a session.

    Returns list of position dicts, each containing:
      id, concept_code, fen, correct_move, correct_move_san,
      difficulty, source_type ('own_game' | 'lichess'),
      source_move_id, lichess_puzzle_id, puzzle_rating,
      solution_depth, visualization_mode

    Mix: 70% player own-game positions, 30% Lichess puzzles.
    Shortfall in own-game positions is filled from Lichess.

    For 3.3.6.c (deep tactical), puzzles are served from depth_ceiling to
    depth_ceiling + DEPTH_CEILING_WINDOW using progressive depth training.
    """
    conn = get_connection()
    cur  = conn.cursor()
    today = date.today()

    if target_difficulty is None:
        target_difficulty = _target_difficulty(cur, player_id)

    total    = max(5, session_length_mins * POSITIONS_PER_MIN)
    own_n    = int(total * OWN_GAME_FRACTION)
    lich_n   = total - own_n
    diff_lo  = max(0.0, target_difficulty - DIFF_WINDOW)
    diff_hi  = min(1.0, target_difficulty + DIFF_WINDOW)

    # For 3.3.6.c, compute rating range from depth_ceiling (puzzle_rating as depth proxy)
    depth_range = None
    if DEPTH_PROGRESSIVE_CODE in concept_codes:
        ceiling      = _get_depth_ceiling(cur, player_id, game_type)
        rating_lo    = DEPTH_RATING_BASE + ceiling * DEPTH_RATING_WINDOW
        rating_hi    = rating_lo + (DEPTH_CEILING_WINDOW + 1) * DEPTH_RATING_WINDOW
        depth_range  = (rating_lo, rating_hi)   # (min_rating, max_rating)

    own_rows  = _fetch_positions(cur, player_id, concept_codes,
                                 today, diff_lo, diff_hi, own_n,
                                 depth_range=depth_range)
    lich_rows = _fetch_positions(cur, None, concept_codes,
                                 today, diff_lo, diff_hi, lich_n,
                                 depth_range=depth_range)

    # If own positions are scarce, fill up from Lichess
    shortfall = own_n - len(own_rows)
    if shortfall > 0:
        seen_ids = tuple(r['id'] for r in lich_rows) if lich_rows else (0,)
        extras   = _fetch_positions(cur, None, concept_codes,
                                    today, diff_lo, diff_hi,
                                    shortfall, exclude_ids=seen_ids,
                                    depth_range=depth_range)
        lich_rows.extend(extras)

    # Interleave: alternate own and Lichess for variety
    positions = []
    oi, li = 0, 0
    while oi < len(own_rows) or li < len(lich_rows):
        if oi < len(own_rows):
            positions.append(own_rows[oi]); oi += 1
        if li < len(lich_rows):
            positions.append(lich_rows[li]); li += 1

    # Tag 3.3.6.c positions with visualization_mode hint (hard puzzles benefit from no-board mode)
    for p in positions:
        rating = p.get('puzzle_rating') or 0
        p['visualization_mode'] = (
            p['concept_code'] == DEPTH_PROGRESSIVE_CODE and rating >= 2000
        )

    cur.close(); conn.close()
    return positions


def update_sm2(drill_id: int, correct: bool,
               solve_time_ms: Optional[int] = None) -> dict:
    """
    Apply SM-2 after a single solve attempt.

    SM-2 schedule:
      Correct:   interval → 1 → 3 → round(prev * ease); ease += 0.05
      Incorrect: interval → 1;                           ease -= 0.20
    next_review = today + new interval.

    Returns dict with new SM-2 state.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT interval_days, ease_factor, review_count
        FROM drill_positions WHERE id = %s
    """, (drill_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        raise ValueError(f"drill_positions id={drill_id} not found")

    interval, ease, count = int(row[0]), float(row[1]), int(row[2])

    if correct:
        new_ease = min(EASE_MAX, ease + EASE_CORRECT)
        if count == 0:
            new_interval = 1
        elif count == 1:
            new_interval = 3
        else:
            new_interval = max(INTERVAL_MIN, round(interval * new_ease))
    else:
        new_ease     = max(EASE_MIN, ease + EASE_INCORRECT)
        new_interval = INTERVAL_MIN

    next_review = date.today() + timedelta(days=new_interval)
    result_str  = 'correct' if correct else 'incorrect'
    new_count   = count + 1

    cur.execute("""
        UPDATE drill_positions SET
            interval_days = %s,
            ease_factor   = %s,
            review_count  = %s,
            next_review   = %s,
            last_result   = %s
        WHERE id = %s
    """, (new_interval, new_ease, new_count, next_review, result_str, drill_id))
    conn.commit()
    cur.close(); conn.close()

    return {
        'drill_id':     drill_id,
        'correct':      correct,
        'interval':     new_interval,
        'ease_factor':  round(new_ease, 3),
        'review_count': new_count,
        'next_review':  next_review.isoformat(),
    }


def start_session(player_id: int,
                  concept_codes: list,
                  session_length_mins: int,
                  module_type: str = 'tactical_drill') -> int:
    """Create a study_sessions row. Returns session_id."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO study_sessions
            (player_id, session_date, module_type, concept_codes, duration_mins)
        VALUES (%s, CURRENT_DATE, %s, %s, %s)
        RETURNING id
    """, (player_id, module_type, concept_codes, session_length_mins))
    session_id = cur.fetchone()[0]
    conn.commit()
    cur.close(); conn.close()
    return session_id


def finish_session(session_id: int, positions_seen: int,
                   positions_solved: int, solve_times_ms: list,
                   difficulty_avg: float) -> None:
    """Write final stats back to study_sessions."""
    avg_time = (int(sum(solve_times_ms) / len(solve_times_ms))
                if solve_times_ms else None)
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE study_sessions SET
            positions_seen    = %s,
            positions_solved  = %s,
            avg_solve_time_ms = %s,
            difficulty_avg    = %s,
            completed_at      = NOW()
        WHERE id = %s
    """, (positions_seen, positions_solved, avg_time, difficulty_avg, session_id))
    conn.commit()
    cur.close(); conn.close()


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Build and display a drill session for a player.')
    parser.add_argument('player_id', type=int)
    parser.add_argument('--mins',   type=int,   default=20,
                        help='Session length in minutes (default: 20)')
    parser.add_argument('--diff',   type=float, default=None,
                        help='Target difficulty 0.0-1.0 (default: auto)')
    parser.add_argument('--codes',  nargs='+',  default=None,
                        help='Concept codes to drill (default: top weaknesses)')
    args = parser.parse_args()

    codes = args.codes or top_weakness_codes(args.player_id, limit=5)
    if not codes:
        print("No weakness codes found. Run weakness_aggregator.py first.")
        sys.exit(1)

    print(f"Building {args.mins}-min session for player_id={args.player_id}")
    print(f"Concept codes: {codes}")
    print(f"Target difficulty: {args.diff or 'auto'}")
    print()

    positions = build_session(args.player_id, codes, args.mins, args.diff)

    if not positions:
        print("No due positions found for these concept codes and difficulty.")
        sys.exit(0)

    own_n  = sum(1 for p in positions if p['source_type'] == 'own_game')
    lich_n = sum(1 for p in positions if p['source_type'] == 'lichess')
    avg_d  = sum(p['difficulty'] for p in positions) / len(positions)

    print(f"Session ready: {len(positions)} positions")
    print(f"  Own-game positions: {own_n}  Lichess puzzles: {lich_n}")
    print(f"  Avg difficulty: {avg_d:.3f}")
    print()
    print(f"  {'#':<4} {'Type':<10} {'Code':<8} {'Diff':>5}  FEN (first 40)")
    print(f"  {'-'*4} {'-'*10} {'-'*8} {'-'*5}  {'-'*40}")
    for i, p in enumerate(positions[:20], 1):
        src  = 'OwnGame' if p['source_type'] == 'own_game' else 'Lichess'
        fen_short = p['fen'][:40] if p['fen'] else ''
        print(f"  {i:<4} {src:<10} {p['concept_code']:<8} {p['difficulty']:>5.3f}"
              f"  {fen_short}")
    if len(positions) > 20:
        print(f"  ... and {len(positions)-20} more")
