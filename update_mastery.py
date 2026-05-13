"""
update_mastery.py — Close the feedback loop: drill performance → mastery → prescription.

Weakness detected → drill prescribed → player solves drill →
mastery score updates → prescription priority adjusts

FUNCTIONS:
  update_mastery_from_drills(player_id)   — drill attempts → mastery delta
  update_mastery_from_games(player_id)    — new games → check for regressions
  generate_mastery_report(player_id)      — print mastery summary
"""
import sys
from datetime import date
from db_setup import get_connection


def update_mastery_from_drills(player_id):
    """
    Update weakness_graph.mastery_score from drill_attempts in the last 30 days.

    correct_rate >= 0.80: +0.10  correct_rate >= 0.60: +0.05  else: -0.05
    mastery_score clamped to [0.0, 1.0].
    status escalates to 'improving' / 'resolved' when threshold crossed.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT dp.concept_code,
               COUNT(*) FILTER (WHERE da.was_correct) AS correct_count,
               COUNT(*)                               AS total_count,
               AVG(da.time_spent_ms)                 AS avg_time_ms
        FROM drill_attempts da
        JOIN drill_positions dp ON dp.id = da.drill_id
        WHERE da.player_id = %s
          AND da.attempted_at >= NOW() - INTERVAL '30 days'
        GROUP BY dp.concept_code
    """, (player_id,))
    drill_rows = cur.fetchall()

    updated = 0
    for code, correct, total, avg_time_ms in drill_rows:
        if not total:
            continue
        correct_rate = correct / total
        if correct_rate >= 0.80:
            delta = +0.10
        elif correct_rate >= 0.60:
            delta = +0.05
        else:
            delta = -0.05

        cur.execute("""
            SELECT game_type, mastery_score, status, last_occurred
            FROM weakness_graph
            WHERE player_id = %s AND concept_code = %s
        """, (player_id, code))
        wg_rows = cur.fetchall()

        for game_type, mastery_score, status, last_occurred in wg_rows:
            mastery_score = mastery_score or 0.0
            new_mastery   = max(0.0, min(1.0, mastery_score + delta))

            days_since = (date.today() - last_occurred).days if last_occurred else 9999
            new_status = status
            if new_mastery >= 0.95:
                new_status = 'resolved'
            elif new_mastery >= 0.80 and days_since > 30:
                new_status = 'improving'

            cur.execute("""
                UPDATE weakness_graph
                SET mastery_score = %s, status = %s, updated_at = NOW()
                WHERE player_id = %s AND concept_code = %s AND game_type = %s
            """, (new_mastery, new_status, player_id, code, game_type))
            updated += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Mastery from drills: {updated} rows updated (player {player_id})")
    return updated


def update_mastery_from_games(player_id):
    """
    After new games are analyzed, check whether improving/resolved concepts
    are still appearing in recent games. Regress mastery if weakness resurfaces.

    Triggers regression if concept appears in > 3 of last 20 games AND
    avg CPL in those games exceeds the mistake threshold.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT value FROM player_thresholds
        WHERE player_id IS NULL AND threshold_name = 'mistake_cpl'
        LIMIT 1
    """)
    row = cur.fetchone()
    cpl_threshold = float(row[0]) if row else 100.0

    cur.execute("""
        SELECT concept_code, game_type, mastery_score, status, regression_count
        FROM weakness_graph
        WHERE player_id = %s AND status IN ('improving', 'resolved')
    """, (player_id,))
    wg_rows = cur.fetchall()

    # Last 20 game IDs for this player
    cur.execute("""
        SELECT id FROM games
        WHERE player_id = %s AND analyzed = TRUE
        ORDER BY played_at DESC
        LIMIT 20
    """, (player_id,))
    recent_game_ids = [r[0] for r in cur.fetchall()]

    if not recent_game_ids:
        cur.close(); conn.close()
        print("No analyzed games found.")
        return 0

    regressed = 0
    for code, game_type, mastery_score, status, regression_count in wg_rows:
        mastery_score    = mastery_score or 0.0
        regression_count = regression_count or 0

        gt_clause = "AND g.game_type = %s" if game_type != 'all' else ""
        gt_args   = (player_id, code, game_type) if game_type != 'all' else (player_id, code)

        cur.execute(f"""
            SELECT COUNT(DISTINCT m.game_id),
                   AVG(m.centipawn_loss)
            FROM move_concepts mc
            JOIN moves m    ON m.id   = mc.move_id
            JOIN games g    ON g.id   = m.game_id
            JOIN concepts c ON c.id   = mc.concept_id
            WHERE g.player_id = %s
              AND c.code = %s
              AND mc.is_primary_cause = TRUE
              {gt_clause}
              AND m.game_id = ANY(%s)
        """, gt_args + (recent_game_ids,))
        result = cur.fetchone()
        recent_games = result[0] or 0
        avg_cpl      = float(result[1]) if result[1] else 0.0

        if recent_games > 3 and avg_cpl > cpl_threshold:
            new_mastery = max(0.0, mastery_score - 0.20)
            cur.execute("""
                UPDATE weakness_graph
                SET mastery_score    = %s,
                    status           = 'active',
                    regression_count = %s,
                    updated_at       = NOW()
                WHERE player_id = %s AND concept_code = %s AND game_type = %s
            """, (new_mastery, regression_count + 1, player_id, code, game_type))
            regressed += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Mastery from games: {regressed} regressions detected (player {player_id})")
    return regressed


def generate_mastery_report(player_id):
    """Print full mastery status for all concepts."""
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute('SELECT username FROM players WHERE id = %s', (player_id,))
    row = cur.fetchone()
    username = row[0] if row else f'player_{player_id}'

    cur.execute("""
        SELECT wg.concept_code, c.name,
               wg.mastery_score, wg.status, wg.regression_count,
               wg.game_type, wg.estimated_elo_impact, wg.primary_study_module
        FROM weakness_graph wg
        JOIN concepts c ON c.code = wg.concept_code
        WHERE wg.player_id = %s
        ORDER BY COALESCE(wg.mastery_score, 0) DESC
    """, (player_id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("No weakness_graph data. Run weakness_aggregator.py first.")
        return

    mastered  = [r for r in rows if (r[2] or 0) >= 0.80]
    improving = [r for r in rows if 0.50 <= (r[2] or 0) < 0.80]
    active    = [r for r in rows if (r[2] or 0) < 0.50]
    regressed = [r for r in rows if (r[4] or 0) > 0]

    W = 72
    print()
    print('=' * W)
    print(f'  MASTERY REPORT — {username.upper()}')
    print('=' * W)
    print(f'  Mastered  (>= 80%): {len(mastered):>3}')
    print(f'  Improving (50-80%): {len(improving):>3}')
    print(f'  Active    (<  50%): {len(active):>3}')
    print(f'  Regressed concepts: {len(regressed):>3}')
    print()

    # Top 3 next drills (active, highest Elo impact)
    drill_candidates = sorted(
        [r for r in active if r[6]],
        key=lambda r: r[6], reverse=True
    )[:3]

    print('  RECOMMENDED NEXT DRILL SESSION:')
    if drill_candidates:
        for code, name, mastery, status, reg, gt, elo_impact, study_mod in drill_candidates:
            pct = int((mastery or 0) * 100)
            print(f'    [{code}] {name[:35]:<35}  mastery={pct:>3}%  '
                  f'+{elo_impact:.0f} Elo  {study_mod}')
    else:
        print('    No active concepts with Elo impact data.')

    print()
    print(f'  {"Code":<12} {"Name":<35} {"Mastery":>8} {"Status":<12} {"Reg":>4}')
    print('  ' + '-' * 74)
    for code, name, mastery, status, reg, gt, *_ in rows:
        pct     = int((mastery or 0) * 100)
        reg_str = f'  *{reg}' if reg else ''
        print(f'  {code:<12} {name[:35]:<35} {pct:>7}%  {status:<12}{reg_str}')
    print()


if __name__ == '__main__':
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    mode = sys.argv[2] if len(sys.argv) > 2 else 'report'
    if mode == 'drills':
        update_mastery_from_drills(pid)
    elif mode == 'games':
        update_mastery_from_games(pid)
    else:
        update_mastery_from_drills(pid)
        update_mastery_from_games(pid)
        generate_mastery_report(pid)
