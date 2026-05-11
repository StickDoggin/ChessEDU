"""
opening_prep_gap.py — Detect opening preparation gaps from game history.

A preparation gap is identified when a player spends disproportionate time
on opening moves in a specific line, relative to their recency-weighted
baseline opening speed, and/or when novelty moves occur earlier than expected.

All averages are RECENCY-WEIGHTED with a 90-day half-life so games from
3+ years ago contribute near-zero weight. A line not played in STALE_DAYS
is marked stale rather than flagged — it may have been a real gap that the
player has since resolved or abandoned.

Algorithm:
  Recency weight per game: w = 0.5 ^ (days_since_game / 90)

  For each (opening_eco, opening_name) line played >= min_games times:
    - w_avg_time_ms: recency-weighted avg of per-game opening move time
    - time_ratio = w_avg_time_ms / recency_weighted_baseline_ms
    - w_novelty: recency-weighted avg novelty move number
    - novelty_factor = min(2.0, 8 / max(w_novelty, 1))
    - gap_score = (time_ratio * 0.6) + (novelty_factor * 0.4)
    - is_stale = days since last game > STALE_DAYS
    - is_gap = not is_stale AND (gap_score >= GAP_SCORE_THRESH OR
                                 time_ratio >= TIME_RATIO_THRESH)

Writes results to weakness_graph using concept codes 5.x.
"""
import sys
from datetime import date
from db_setup import get_connection

MIN_GAMES         = 3      # minimum raw game count in a line
TIME_RATIO_THRESH = 1.8    # flag if weighted opening time >1.8x baseline
GAP_SCORE_THRESH  = 1.5    # combined gap score threshold
OPENING_MOVE_CAP  = 12     # moves 1-N considered "opening phase"
NOVELTY_EARLY_CAP = 8      # novelty before move 8 = early theory end
HALF_LIFE_DAYS    = 90     # exponential decay half-life (same as weakness_aggregator)
STALE_DAYS        = 180    # line not played in N days = stale, don't flag


def _opening_concept_code(eco: str) -> str:
    """Map ECO code to a concept code (5.x hierarchy)."""
    if not eco:
        return '5.2'
    letter = eco[0].upper()
    return {
        'A': '5.2',    # English, Indian
        'B': '5.2.2',  # Sicilian, Caro-Kann
        'C': '5.2.1',  # Ruy Lopez, French, Italian
        'D': '5.2',    # QGD, Slav
        'E': '5.2.1',  # Indian defenses (KID, Nimzo)
    }.get(letter, '5.2')


# ── SQL fragment for recency weight ──────────────────────────────────────────
# POWER(0.5, days_since / half_life) — produces 1.0 for today, 0.5 at 90 days
_WEIGHT_SQL = (
    f"POWER(0.5::float, "
    f"EXTRACT(EPOCH FROM NOW() - g.played_at)::float "
    f"/ ({HALF_LIFE_DAYS}.0 * 86400))"
)


def compute_opening_gaps(player_id: int, min_games: int = MIN_GAMES,
                         verbose: bool = True) -> list:
    """
    Compute recency-weighted prep gap scores for all opening lines.
    Returns list of gap dicts sorted by gap_score DESC.
    """
    conn = get_connection()
    cur  = conn.cursor()
    today = date.today()

    # ── Recency-weighted player baseline ─────────────────────────────────────
    # Per-game avg opening move time, weighted by game recency, across all games.
    cur.execute(f"""
        WITH game_avg AS (
            SELECT
                g.id,
                g.played_at,
                AVG(m.time_spent_ms) FILTER (WHERE m.time_spent_ms > 0) AS avg_ms,
                {_WEIGHT_SQL} AS w
            FROM moves m
            JOIN games g ON g.id = m.game_id
            WHERE g.player_id = %s
              AND g.analyzed = TRUE
              AND m.move_number <= %s
              AND m.time_spent_ms IS NOT NULL
            GROUP BY g.id, g.played_at
        )
        SELECT
            SUM(avg_ms * w) / NULLIF(SUM(w), 0)
        FROM game_avg
        WHERE avg_ms IS NOT NULL
    """, (player_id, OPENING_MOVE_CAP))
    row = cur.fetchone()
    baseline_ms = float(row[0]) if row and row[0] else None

    if not baseline_ms or baseline_ms < 100:
        if verbose:
            print("Insufficient clock data for recency-weighted baseline.")
        cur.close(); conn.close()
        return []

    if verbose:
        print(f"Recency-weighted baseline opening move time: {baseline_ms/1000:.2f}s")

    # ── Per-line recency-weighted aggregation ─────────────────────────────────
    # CTE computes per-game stats and weight; outer aggregates with weights.
    cur.execute(f"""
        WITH game_avg AS (
            SELECT
                g.id AS game_id,
                g.opening_eco,
                COALESCE(g.opening_name, 'Unknown') AS opening_name,
                COALESCE(g.opening_var, 'Main Line') AS opening_var,
                g.novelty_move,
                g.result,
                g.played_at,
                AVG(m.time_spent_ms) FILTER (WHERE m.time_spent_ms > 0) AS avg_ms,
                {_WEIGHT_SQL} AS w
            FROM moves m
            JOIN games g ON g.id = m.game_id
            WHERE g.player_id = %s
              AND g.analyzed = TRUE
              AND g.opening_eco IS NOT NULL
              AND m.move_number <= %s
              AND m.time_spent_ms IS NOT NULL
            GROUP BY g.id, g.opening_eco, g.opening_name,
                     g.opening_var, g.novelty_move, g.result, g.played_at
        )
        SELECT
            opening_eco,
            opening_name,
            opening_var,
            COUNT(*)                                                     AS game_count,
            -- Recency-weighted avg time per move
            SUM(avg_ms * w) / NULLIF(SUM(w), 0)                         AS w_avg_ms,
            -- Recency-weighted novelty move (fallback to OPENING_MOVE_CAP)
            SUM(COALESCE(novelty_move, {OPENING_MOVE_CAP})::float * w)
                / NULLIF(SUM(w), 0)                                      AS w_novelty,
            -- Recency-weighted loss rate
            SUM(CASE WHEN result='loss' THEN w ELSE 0 END)
                / NULLIF(SUM(w), 0) * 100                                AS w_loss_rate,
            SUM(w)                                                       AS total_weight,
            MIN(played_at)                                               AS first_seen,
            MAX(played_at)                                               AS last_seen
        FROM game_avg
        WHERE avg_ms IS NOT NULL
        GROUP BY opening_eco, opening_name, opening_var
        HAVING COUNT(*) >= %s
        ORDER BY total_weight DESC
    """, (player_id, OPENING_MOVE_CAP, min_games))
    line_rows = cur.fetchall()
    cur.close(); conn.close()

    if verbose:
        print(f"Opening lines with >= {min_games} games: {len(line_rows)}")

    gaps = []
    for (eco, opening_name, opening_var, game_count,
         w_avg_ms, w_novelty, w_loss_rate, total_weight,
         first_seen, last_seen) in line_rows:

        if not w_avg_ms or w_avg_ms <= 0:
            continue

        w_avg_ms   = float(w_avg_ms)
        w_novelty  = float(w_novelty) if w_novelty else float(OPENING_MOVE_CAP)
        w_loss_rate = float(w_loss_rate) if w_loss_rate else 0.0

        time_ratio     = w_avg_ms / baseline_ms
        novelty_factor = min(2.0, NOVELTY_EARLY_CAP / max(w_novelty, 1.0))
        gap_score      = round((time_ratio * 0.6) + (novelty_factor * 0.4), 3)

        last_played_days = (today - last_seen.date()).days if last_seen else 9999
        is_stale = last_played_days > STALE_DAYS
        is_gap   = (not is_stale and
                    (time_ratio >= TIME_RATIO_THRESH or gap_score >= GAP_SCORE_THRESH))

        concept_code = _opening_concept_code(eco)

        gaps.append({
            'eco':            eco,
            'opening_name':   opening_name,
            'opening_var':    opening_var,
            'game_count':     game_count,
            'total_weight':   round(float(total_weight), 2),
            'w_loss_rate':    round(w_loss_rate, 1),
            'avg_time_s':     round(w_avg_ms / 1000, 2),
            'baseline_s':     round(baseline_ms / 1000, 2),
            'time_ratio':     round(time_ratio, 3),
            'w_novelty':      round(w_novelty, 1),
            'novelty_factor': round(novelty_factor, 3),
            'gap_score':      gap_score,
            'is_stale':       is_stale,
            'is_gap':         is_gap,
            'last_played_days': last_played_days,
            'concept_code':   concept_code,
            'first_seen':     first_seen,
            'last_seen':      last_seen,
        })

    gaps.sort(key=lambda x: -x['gap_score'])
    return gaps


def upsert_gap_weaknesses(player_id: int, gaps: list) -> int:
    """
    Write flagged opening gaps to weakness_graph with game_type='opening'.
    Only writes lines where is_gap=True (not stale).
    Returns count of rows upserted.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute(
        "SELECT game_type, current_elo FROM player_ratings WHERE player_id = %s",
        (player_id,)
    )
    elo_by_type = dict(cur.fetchall())
    _           = (elo_by_type.get('blitz') or elo_by_type.get('rapid')
                   or next(iter(elo_by_type.values()), 1500))

    today      = date.today()
    upserted   = 0
    seen_codes = set()

    for g in gaps:
        if not g['is_gap']:
            continue
        code = g['concept_code']
        if code in seen_codes:
            continue
        seen_codes.add(code)

        same_code = [x for x in gaps if x['concept_code'] == code and x['is_gap']]
        # Weight occ_count by recency (total_weight = effective recent game count)
        occ_count = sum(x['game_count'] for x in same_code)
        w_count   = sum(x['total_weight'] for x in same_code)
        avg_ratio = sum(x['time_ratio'] for x in same_code) / len(same_code)
        avg_score = sum(x['gap_score'] for x in same_code) / len(same_code)

        occ_rate   = round(w_count / max(w_count, 1) * 10, 3)
        elo_impact = min(15.0, avg_score * 5.0)
        study_hrs  = occ_count * 0.05
        efficiency = round(elo_impact / study_hrs, 2) if study_hrs > 0 else 0.0

        first = min(x['first_seen'] for x in same_code if x['first_seen'])
        last  = max(x['last_seen']  for x in same_code if x['last_seen'])
        days_since = (today - last.date()).days if last else 9999
        # Stale lines already filtered out above; 'resolved' if >90 days
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
            'last':  last.date() if last else None,
        })
        upserted += 1

    conn.commit()
    cur.close(); conn.close()
    return upserted


def print_gap_report(player_id: int, gaps: list, top_n: int = 15):
    """Print a ranked opening prep gap report with recency markers."""
    W = 78
    flagged = [g for g in gaps if g['is_gap']]
    stale   = [g for g in gaps if g['is_stale']]

    print()
    print('=' * W)
    print(f'  OPENING PREPARATION GAPS (recency-weighted) player_id={player_id}')
    print('=' * W)
    print(f'  Lines analysed: {len(gaps)}   Flagged: {len(flagged)}'
          f'   Stale (>{STALE_DAYS}d): {len(stale)}')
    print(f'  Recency weight: 90-day half-life  '
          f'Baseline: {gaps[0]["baseline_s"]:.2f}s' if gaps else '')
    print()
    print(f'  {"":1} {"ECO":<5} {"Variation":<28} {"N":>4} {"Ratio":>6} '
          f'{"Nov":>5} {"Score":>6} {"Loss%":>6} {"Days":>5}')
    print(f'  {"-"} {"-"*5} {"-"*28} {"-"*4} {"-"*6} '
          f'{"-"*5} {"-"*6} {"-"*6} {"-"*5}')

    for g in gaps[:top_n]:
        if g['is_stale']:
            marker = 'S'  # stale
        elif g['is_gap']:
            marker = '*'  # active gap
        else:
            marker = ' '
        var_display = g['opening_var'] if g['opening_var'] != 'Main Line' else g['opening_name']
        print(
            f'  {marker} {g["eco"]:<5} {var_display[:28]:<28} '
            f'{g["game_count"]:>4} '
            f'{g["time_ratio"]:>6.2f} '
            f'{g["w_novelty"]:>5.1f} '
            f'{g["gap_score"]:>6.3f} '
            f'{g["w_loss_rate"]:>5.1f}% '
            f'{g["last_played_days"]:>5}'
        )

    print()
    print('  * = active gap   S = stale (not played recently, excluded from flagging)')
    print('  Ratio = weighted time vs baseline   Nov = weighted avg novelty move')
    print()

    if flagged:
        print('  TOP ACTIVE GAPS:')
        for g in flagged[:5]:
            var_display = g['opening_var'] if g['opening_var'] != 'Main Line' else ''
            print(f'    [{g["eco"]}] {g["opening_name"]}'
                  + (f' - {var_display}' if var_display else ''))
            print(f'      Weighted avg time: {g["avg_time_s"]:.2f}s  '
                  f'({g["time_ratio"]:.2f}x baseline of {g["baseline_s"]:.2f}s)')
            print(f'      Weighted novelty: move {g["w_novelty"]:.1f}  '
                  f'Gap score: {g["gap_score"]:.3f}  '
                  f'Loss rate: {g["w_loss_rate"]:.1f}%  '
                  f'N={g["game_count"]} games  '
                  f'Last played: {g["last_played_days"]}d ago')
    print()


if __name__ == '__main__':
    args    = [a for a in sys.argv[1:] if not a.startswith('--')]
    pid     = int(args[0]) if args else 1
    min_g   = int(args[1]) if len(args) > 1 else MIN_GAMES
    do_save = '--save' in sys.argv

    print(f"Computing opening prep gaps for player_id={pid} "
          f"(min_games={min_g}, half_life={HALF_LIFE_DAYS}d, stale>{STALE_DAYS}d)...")
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
        stale   = sum(1 for g in gaps if g['is_stale'])
        if flagged:
            print(f"  {flagged} active gaps, {stale} stale."
                  f" Run with --save to write to weakness_graph.")
