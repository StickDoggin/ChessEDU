"""
session_detector.py — Group games into sessions and compute session-level stats.

A session is a consecutive sequence of games by the same player where
each game starts within 2 hours of the previous game ending.

Writes to:
  sessions table  — one row per session
  games.session_id — updated for every game

Also computes:
  tilt_detected      — CPL in games 3-5 is >30% higher than games 1-2
  fatigue_detected   — CPL is monotonically increasing across the session
"""
import sys
from datetime import timedelta
from db_setup import get_connection

SESSION_GAP_HOURS = 2       # New session if gap > this many hours
MIN_GAMES_FOR_STATS = 2     # Need at least N games to compute CPL stats
TILT_THRESHOLD = 0.30       # 30% CPL increase triggers tilt flag


def _game_avg_cpl(cur, game_id):
    """Average CPL for a game (from analyzed moves only)."""
    cur.execute("""
        SELECT AVG(centipawn_loss)
        FROM moves
        WHERE game_id = %s AND centipawn_loss IS NOT NULL
    """, (game_id,))
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


def _game_peak_cpl(cur, game_id):
    """Max CPL for a game (from analyzed moves only)."""
    cur.execute("""
        SELECT MAX(centipawn_loss)
        FROM moves
        WHERE game_id = %s AND centipawn_loss IS NOT NULL
    """, (game_id,))
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


def _game_avg_accuracy(cur, game_id):
    """Average accuracy_wdl for a game."""
    cur.execute("""
        SELECT AVG(accuracy_wdl)
        FROM moves
        WHERE game_id = %s AND accuracy_wdl IS NOT NULL
    """, (game_id,))
    row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else None


def _detect_tilt(game_cpls):
    """
    Return (tilt_detected, tilt_coefficient) for a sequence of per-game avg CPLs.
    tilt_detected: True if CPL in games 3-5 is >30% higher than games 1-2.
    tilt_coefficient: ratio of late/early CPL (None if not enough data).
    """
    # Filter None values by index
    early = [c for c in game_cpls[:2] if c is not None]
    late  = [c for c in game_cpls[2:5] if c is not None]
    if not early or not late:
        return False, None
    early_avg = sum(early) / len(early)
    late_avg  = sum(late) / len(late)
    if early_avg <= 0:
        return False, None
    coeff = late_avg / early_avg
    return coeff > (1.0 + TILT_THRESHOLD), round(coeff, 3)


def _detect_fatigue(game_cpls):
    """
    Return (fatigue_detected, fatigue_start_game_index).
    Fatigue: CPL is monotonically increasing for 3+ consecutive games.
    fatigue_start_game_index: 0-based index in game_cpls where the run starts.
    """
    valid = [(i, c) for i, c in enumerate(game_cpls) if c is not None]
    if len(valid) < 3:
        return False, None
    # Find longest monotonically increasing run
    best_start = None
    best_len   = 0
    run_start  = 0
    run_len    = 1
    for i in range(1, len(valid)):
        if valid[i][1] > valid[i-1][1]:
            run_len += 1
        else:
            if run_len >= 3 and run_len > best_len:
                best_len   = run_len
                best_start = valid[run_start][0]
            run_start = i
            run_len   = 1
    if run_len >= 3 and run_len > best_len:
        best_len   = run_len
        best_start = valid[run_start][0]
    if best_start is not None:
        return True, best_start
    return False, None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def detect_sessions(player_id=None, clear_existing=False):
    """
    Group all games into sessions and persist results.

    Args:
        player_id: restrict to one player (None = all players)
        clear_existing: if True, delete existing sessions and reset game.session_id
    """
    conn = get_connection()
    cur  = conn.cursor()

    if clear_existing:
        if player_id:
            cur.execute("DELETE FROM sessions WHERE player_id = %s", (player_id,))
            cur.execute("UPDATE games SET session_id = NULL WHERE player_id = %s", (player_id,))
        else:
            cur.execute("DELETE FROM sessions")
            cur.execute("UPDATE games SET session_id = NULL")
        conn.commit()

    # Fetch all games ordered by player_id and played_at
    pid_clause = "WHERE player_id = %s" if player_id else ""
    params     = (player_id,) if player_id else ()
    cur.execute(f"""
        SELECT id, player_id, played_at, game_type, analyzed
        FROM games
        {pid_clause}
        ORDER BY player_id, played_at
    """, params)
    all_games = cur.fetchall()

    if not all_games:
        print("No games found.")
        cur.close(); conn.close()
        return

    # ── Group games into sessions ─────────────────────────────────────────────
    sessions_raw = []   # list of (player_id, [game_rows])
    current_pid  = None
    current_sess = []
    gap          = timedelta(hours=SESSION_GAP_HOURS)

    for game in all_games:
        gid, gpid, played_at, gtype, analyzed = game
        if current_pid != gpid:
            if current_sess:
                sessions_raw.append((current_pid, current_sess))
            current_pid  = gpid
            current_sess = [game]
            continue
        prev_played = current_sess[-1][2]
        if (played_at - prev_played) > gap:
            sessions_raw.append((current_pid, current_sess))
            current_sess = [game]
        else:
            current_sess.append(game)
    if current_sess:
        sessions_raw.append((current_pid, current_sess))

    # ── Persist each session ──────────────────────────────────────────────────
    total_sessions = 0
    tilt_count     = 0
    fatigue_count  = 0
    session_lens   = []

    for sess_pid, games_in_sess in sessions_raw:
        game_ids   = [g[0] for g in games_in_sess]
        started_at = games_in_sess[0][2]
        ended_at   = games_in_sess[-1][2]
        game_count = len(games_in_sess)
        session_lens.append(game_count)

        # Dominant game_type in session
        type_counts = {}
        for g in games_in_sess:
            t = g[3] or 'unknown'
            type_counts[t] = type_counts.get(t, 0) + 1
        dominant_type = max(type_counts, key=type_counts.get)

        # Per-game CPL (only for analyzed games)
        game_cpls  = []
        all_cpls   = []
        all_acc    = []
        all_peaks  = []
        for gid in game_ids:
            avg  = _game_avg_cpl(cur, gid)
            peak = _game_peak_cpl(cur, gid)
            acc  = _game_avg_accuracy(cur, gid)
            game_cpls.append(avg)
            if avg  is not None: all_cpls.append(avg)
            if peak is not None: all_peaks.append(peak)
            if acc  is not None: all_acc.append(acc)

        sess_avg_cpl  = round(sum(all_cpls)  / len(all_cpls),  1) if all_cpls  else None
        sess_peak_cpl = round(max(all_peaks),                   1) if all_peaks else None
        sess_avg_acc  = round(sum(all_acc)   / len(all_acc),    4) if all_acc   else None

        tilt_det, tilt_coeff  = _detect_tilt(game_cpls)
        fatigue_det, fat_start = _detect_fatigue(game_cpls)

        if tilt_det:    tilt_count    += 1
        if fatigue_det: fatigue_count += 1

        # Insert session
        cur.execute("""
            INSERT INTO sessions
                (player_id, started_at, ended_at, game_count, game_type,
                 avg_cpl, peak_cpl, avg_accuracy, tilt_detected, tilt_coefficient,
                 fatigue_detected, fatigue_start_game, created_at)
            VALUES
                (%s, %s, %s, %s, %s,
                 %s, %s, %s, %s, %s,
                 %s, %s, NOW())
            RETURNING id
        """, (
            sess_pid, started_at, ended_at, game_count, dominant_type,
            sess_avg_cpl, sess_peak_cpl, sess_avg_acc,
            tilt_det, tilt_coeff,
            fatigue_det, fat_start,
        ))
        sess_id = cur.fetchone()[0]

        # Update games
        if game_ids:
            ph = ','.join(['%s'] * len(game_ids))
            cur.execute(
                f"UPDATE games SET session_id = %s WHERE id IN ({ph})",
                [sess_id] + game_ids
            )

        total_sessions += 1
        if total_sessions % 500 == 0:
            conn.commit()
            print(f"  {total_sessions:,} sessions written...")

    conn.commit()

    # ── Summary ───────────────────────────────────────────────────────────────
    avg_len = sum(session_lens) / len(session_lens) if session_lens else 0
    max_len = max(session_lens) if session_lens else 0

    print()
    print("=" * 60)
    print("SESSION DETECTION SUMMARY")
    print("=" * 60)
    print(f"  Total sessions:          {total_sessions:,}")
    print(f"  Total games grouped:     {len(all_games):,}")
    print(f"  Avg games per session:   {avg_len:.1f}")
    print(f"  Max games in session:    {max_len}")
    print(f"  Tilt detected:           {tilt_count:,}  ({100*tilt_count/total_sessions:.1f}%)")
    print(f"  Fatigue detected:        {fatigue_count:,}  ({100*fatigue_count/total_sessions:.1f}%)")
    print()

    # Session length histogram
    buckets = {1: 0, 2: 0, '3-5': 0, '6-10': 0, '11+': 0}
    for l in session_lens:
        if   l == 1:   buckets[1]    += 1
        elif l == 2:   buckets[2]    += 1
        elif l <= 5:   buckets['3-5']  += 1
        elif l <= 10:  buckets['6-10'] += 1
        else:          buckets['11+']  += 1
    print("  Session length distribution:")
    for k, v in buckets.items():
        bar = '#' * (v * 30 // max(buckets.values()) if max(buckets.values()) else 0)
        print(f"    {str(k):<6}  {v:>5,}  {bar}")
    print()

    cur.close()
    conn.close()
    return total_sessions


if __name__ == '__main__':
    args  = sys.argv[1:]
    clear = '--clear' in args
    args  = [a for a in args if not a.startswith('--')]
    pid   = int(args[0]) if args else None

    target = f'player_id={pid}' if pid else 'ALL players'
    print(f"Detecting sessions for {target}  (gap={SESSION_GAP_HOURS}h)...")
    if clear:
        print("  Clearing existing sessions first...")
    detect_sessions(player_id=pid, clear_existing=clear)
