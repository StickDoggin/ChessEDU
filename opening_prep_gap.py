"""
opening_prep_gap.py — Detect opening preparation gaps from game history.

A preparation gap is identified when a player spends disproportionate time
on opening moves in a specific line, relative to their baseline opening speed,
and/or when novelty moves occur earlier than expected.

Algorithm:
  For each (opening_eco, opening_var) line played >= 3 times:
    - avg_opening_time_ms: mean time_spent_ms on moves 1-12
    - time_ratio = avg_opening_time_ms / player_baseline_opening_time_ms
    - novelty_ratio = if avg_novelty_move < 8, signal is stronger
    - gap_score = (time_ratio * 0.6) + ((8 / max(avg_novelty_move, 1)) * 0.4)
    - Flag if gap_score >= threshold OR time_ratio >= 1.8

Writes results to weakness_graph using concept code 5.2 (main_openings)
or more specific opening codes when available.
"""
import sys
from collections import defaultdict
from db_setup import get_connection

MIN_GAMES         = 3      # minimum games in a line to score
TIME_RATIO_THRESH = 1.8    # flag if opening time >1.8x baseline
GAP_SCORE_THRESH  = 1.5    # combined gap score threshold
OPENING_MOVE_CAP  = 12     # moves 1-N considered "opening phase"
NOVELTY_EARLY_CAP = 8      # novelty before move 8 = early theory end


def _opening_concept_code(eco: str) -> str:
    """Map ECO code to a concept code (5.x hierarchy)."""
    if not eco:
        return '5.2'
    letter = eco[0].upper()
    return {
        'A': '5.2',   # English, Indian
        'B': '5.2.2', # Sicilian, Caro-Kann
        'C': '5.2.1', # Ruy Lopez, French, Italian
        'D': '5.2',   # QGD, Slav
        'E': '5.2.1', # Indian defenses (KID, Nimzo)
    }.get(letter, '5.2')


def compute_opening_gaps(player_id: int, min_games: int = MIN_GAMES,
                         verbose: bool = True) -> list[dict]:
    """
    Compute prep gap scores for all opening lines for player_id.
    Returns list of gap dicts sorted by gap_score DESC.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # ── Player baseline: avg time on opening moves across ALL games ───────────
    cur.execute("""
        SELECT AVG(m.time_spent_ms)
        FROM moves m
        JOIN games g ON g.id = m.game_id
        WHERE g.player_id = %s
          AND m.move_number <= %s
          AND m.time_spent_ms IS NOT NULL
          AND m.time_spent_ms > 0
          AND g.analyzed = TRUE
    """, (player_id, OPENING_MOVE_CAP))
    row = cur.fetchone()
    baseline_ms = float(row[0]) if row and row[0] else None

    if not baseline_ms or baseline_ms < 100:
        if verbose:
            print("Insufficient clock data for baseline computation.")
        cur.close(); conn.close()
        return []

    if verbose:
        print(f"Player baseline opening move time: {baseline_ms/1000:.2f}s")

    # ── Per-line aggregation ──────────────────────────────────────────────────
    cur.execute("""
        SELECT
            g.opening_eco,
            COALESCE(g.opening_var, g.opening_name, 'Unknown') AS line_name,
            COUNT(DISTINCT g.id)                                AS game_count,
            AVG(m.time_spent_ms)
                FILTER (WHERE m.time_spent_ms > 0)             AS avg_move_time_ms,
            AVG(g.novelty_move)
                FILTER (WHERE g.novelty_move IS NOT NULL)       AS avg_novelty_move,
            MIN(g.played_at)                                    AS first_seen,
            MAX(g.played_at)                                    AS last_seen,
            COUNT(DISTINCT g.id) FILTER (WHERE g.result='loss') AS loss_count
        FROM games g
        JOIN moves m ON m.game_id = g.id
        WHERE g.player_id = %s
          AND g.opening_eco IS NOT NULL
          AND m.move_number <= %s
          AND g.analyzed = TRUE
        GROUP BY g.opening_eco, line_name
        HAVING COUNT(DISTINCT g.id) >= %s
        ORDER BY game_count DESC
    """, (player_id, OPENING_MOVE_CAP, min_games))
    line_rows = cur.fetchall()

    if verbose:
        print(f"Opening lines with >= {min_games} games: {len(line_rows)}")

    gaps = []
    for (eco, line_name, game_count, avg_ms, avg_novelty, first_seen,
         last_seen, loss_count) in line_rows:

        if not avg_ms or avg_ms <= 0:
            continue

        avg_ms = float(avg_ms)
        avg_novelty = float(avg_novelty) if avg_novelty else OPENING_MOVE_CAP

        time_ratio = avg_ms / baseline_ms

        # Early novelty → less theory known → stronger prep gap signal
        novelty_factor = min(2.0, NOVELTY_EARLY_CAP / max(avg_novelty, 1.0))

        gap_score = round((time_ratio * 0.6) + (novelty_factor * 0.4), 3)

        is_gap = (time_ratio >= TIME_RATIO_THRESH or
                  gap_score >= GAP_SCORE_THRESH)

        concept_code = _opening_concept_code(eco)
        loss_rate    = round(loss_count / game_count * 100, 1) if game_count else 0.0

        gaps.append({
            'eco':          eco,
            'line_name':    line_name,
            'game_count':   game_count,
            'loss_rate':    loss_rate,
            'avg_time_s':   round(avg_ms / 1000, 2),
            'baseline_s':   round(baseline_ms / 1000, 2),
            'time_ratio':   round(time_ratio, 3),
            'avg_novelty':  round(avg_novelty, 1),
            'novelty_factor': round(novelty_factor, 3),
            'gap_score':    gap_score,
            'is_gap':       is_gap,
            'concept_code': concept_code,
            'first_seen':   first_seen,
            'last_seen':    last_seen,
        })

    cur.close(); conn.close()

    gaps.sort(key=lambda x: -x['gap_score'])
    return gaps


def upsert_gap_weaknesses(player_id: int, gaps: list[dict]) -> int:
    """
    Write flagged opening gaps to weakness_graph with game_type='opening'.
    Only writes lines where is_gap=True.
    Returns count of rows upserted.
    """
    from datetime import date
    conn = get_connection()
    cur  = conn.cursor()

    # Current Elo
    cur.execute(
        "SELECT game_type, current_elo FROM player_ratings WHERE player_id = %s",
        (player_id,)
    )
    elo_by_type = dict(cur.fetchall())
    player_elo  = (elo_by_type.get('blitz') or elo_by_type.get('rapid')
                   or next(iter(elo_by_type.values()), 1500))

    today      = date.today()
    upserted   = 0
    seen_codes = set()

    for g in gaps:
        if not g['is_gap']:
            continue
        code = g['concept_code']

        # Aggregate across lines sharing the same concept_code
        if code in seen_codes:
            continue
        seen_codes.add(code)

        # Collect all gaps for this concept code
        same_code = [x for x in gaps if x['concept_code'] == code and x['is_gap']]
        occ_count = sum(x['game_count'] for x in same_code)
        avg_ratio = sum(x['time_ratio'] for x in same_code) / len(same_code)
        avg_score = sum(x['gap_score'] for x in same_code) / len(same_code)

        occ_rate   = round(occ_count / max(occ_count, 1) * 10, 3)  # % of flagged games
        elo_impact = min(15.0, avg_score * 5.0)   # modest: max 15 Elo per opening gap
        study_hrs  = occ_count * 0.05             # ~3 min per game line reviewed
        efficiency = round(elo_impact / study_hrs, 2) if study_hrs > 0 else 0.0

        first = min(x['first_seen'] for x in same_code if x['first_seen'])
        last  = max(x['last_seen']  for x in same_code if x['last_seen'])
        days_since = (today - last.date()).days if last else 9999
        status = 'resolved' if days_since > 90 else 'active'

        cur.execute("""
            INSERT INTO weakness_graph
                (player_id, concept_code, game_type,
                 occurrence_count, occurrence_rate,
                 avg_cpl_when_occurs, avg_attribution_weight,
                 estimated_elo_impact, primary_study_module, status,
                 first_detected, last_occurred,
                 study_efficiency, estimated_study_hours,
                 updated_at)
            VALUES
                (%(pid)s, %(code)s, 'opening',
                 %(occ)s, %(rate)s,
                 0.0, %(score)s,
                 %(impact)s, 'opening_drill', %(status)s,
                 %(first)s, %(last)s,
                 %(eff)s, %(hrs)s, NOW())
            ON CONFLICT (player_id, concept_code, game_type) DO UPDATE SET
                occurrence_count       = EXCLUDED.occurrence_count,
                occurrence_rate        = EXCLUDED.occurrence_rate,
                avg_attribution_weight = EXCLUDED.avg_attribution_weight,
                estimated_elo_impact   = EXCLUDED.estimated_elo_impact,
                status                 = EXCLUDED.status,
                first_detected         = EXCLUDED.first_detected,
                last_occurred          = EXCLUDED.last_occurred,
                study_efficiency       = EXCLUDED.study_efficiency,
                estimated_study_hours  = EXCLUDED.estimated_study_hours,
                updated_at             = NOW()
        """, {
            'pid': player_id, 'code': code, 'status': status,
            'occ': occ_count, 'rate': occ_rate, 'score': round(avg_score, 3),
            'impact': round(elo_impact, 1), 'eff': efficiency,
            'hrs': round(study_hrs, 1),
            'first': first.date() if first else None,
            'last': last.date() if last else None,
        })
        upserted += 1

    conn.commit()
    cur.close(); conn.close()
    return upserted


def print_gap_report(player_id: int, gaps: list[dict], top_n: int = 15):
    """Print a ranked opening prep gap report."""
    W = 70
    flagged = [g for g in gaps if g['is_gap']]

    print()
    print('=' * W)
    print(f'  OPENING PREPARATION GAPS — player_id={player_id}')
    print('=' * W)
    print(f'  Lines analysed:  {len(gaps)}   Flagged:  {len(flagged)}')
    print()
    print(f'  {"ECO":<5} {"Line":<30} {"N":>4} {"Ratio":>6} {"Nov":>5} {"Score":>6} {"Loss%":>6}')
    print(f'  {"-"*5} {"-"*30} {"-"*4} {"-"*6} {"-"*5} {"-"*6} {"-"*6}')

    shown = 0
    for g in gaps[:top_n]:
        flag = '*' if g['is_gap'] else ' '
        print(
            f'  {flag}{g["eco"]:<4} {g["line_name"][:30]:<30} '
            f'{g["game_count"]:>4} '
            f'{g["time_ratio"]:>6.2f} '
            f'{g["avg_novelty"]:>5.1f} '
            f'{g["gap_score"]:>6.3f} '
            f'{g["loss_rate"]:>5.1f}%'
        )
        shown += 1

    print()
    print(f'  * = prep gap flagged  '
          f'Ratio=time vs baseline  Nov=avg novelty move  Score=gap score')
    print()

    if flagged:
        print('  TOP FLAGGED LINES:')
        for g in flagged[:5]:
            print(f'    [{g["eco"]}] {g["line_name"]}')
            print(f'      Avg time: {g["avg_time_s"]:.2f}s  '
                  f'({g["time_ratio"]:.2f}x baseline of {g["baseline_s"]:.2f}s)')
            print(f'      Avg novelty: move {g["avg_novelty"]:.1f}  '
                  f'Gap score: {g["gap_score"]:.3f}  '
                  f'Loss rate: {g["loss_rate"]:.1f}%  '
                  f'N={g["game_count"]} games')
    print()


if __name__ == '__main__':
    pid     = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    min_g   = int(sys.argv[2]) if len(sys.argv) > 2 else MIN_GAMES
    do_save = '--save' in sys.argv

    print(f"Computing opening prep gaps for player_id={pid} "
          f"(min_games={min_g})...")
    gaps = compute_opening_gaps(pid, min_games=min_g)

    if not gaps:
        print("No opening data found. Ensure games are analyzed with clock data.")
        sys.exit(0)

    print_gap_report(pid, gaps)

    if do_save:
        n = upsert_gap_weaknesses(pid, gaps)
        print(f"Upserted {n} opening weakness entries to weakness_graph.")
    else:
        flagged = sum(1 for g in gaps if g['is_gap'])
        if flagged:
            print(f"  {flagged} gaps found. Run with --save to write to weakness_graph.")
