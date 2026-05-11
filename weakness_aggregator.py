"""
weakness_aggregator.py — Aggregate move_concepts into weakness_graph prescriptions.

Functions:
  aggregate_weakness_graph(player_id, game_type='all')
    Reads move_concepts, applies recency + Elo proximity weights, upserts weakness_graph.
  compute_study_efficiency(player_id)
    Updates weakness_graph.study_efficiency = elo_impact / estimated_study_hours.
  generate_prescription(player_id, top_n=10)
    Ranked study recommendations filtered by Elo bracket and sorted by efficiency.
  print_weakness_report(player_id)
    Human-readable console diagnosis report.
"""
import math
from collections import defaultdict
from datetime import date, datetime, timezone
from db_setup import get_connection

# ─── Constants ────────────────────────────────────────────────────────────────
HALF_LIFE_DAYS  = 90
ELO_SCALE       = 150
ELO_IMPACT_CAP  = 50.0

# Minutes per exercise by study module type
STUDY_MIN_PER_EX = {
    'tactical_drill':   3,
    'endgame_drill':    5,
    'positional_drill': 4,
    'opening_drill':    3,
    'psychological':    2,
}

# Exercise counts from Chess King University curriculum audit (May 2026)
# Used to estimate how many hours a concept takes to study adequately
EXERCISE_COUNTS = {
    '3.1.1':  80, '3.1.2':  70, '3.1.3':  60, '3.1.4':  55, '3.1.5':  50,
    '3.1.6':  45, '3.1.7': 140, '3.1.8':  65, '3.1.9':  55, '3.1.10': 120,
    '3.1.11': 115,'3.1.12':  48,'3.1.13':  40,'3.1.14':  45,'3.1.15': 138,
    '3.2.1':  90, '3.2.2':  30, '3.3.1': 100, '3.3.3':  80, '3.3.6': 200,
    '3.4.2':  60, '4.1.1':  50, '4.1.2':  40, '4.1.4':  50, '4.1.5':  55,
    '4.2.1':  70, '4.2.2':  45, '4.2.3':  50, '4.2.4':  80, '4.3.3':  60,
    '4.4.2':  55, '4.4.3':  50, '6.1':   100, '6.2':   200, '6.2.1': 120,
    '6.2.2':  80, '6.3.1': 253, '6.3.2':  90, '6.3.3': 100, '7.1.1':  45,
    '7.1.2':  40, '7.3.1':  30, '7.3.4':  30,
}
DEFAULT_EX_COUNT = 60

# Fallback study module for concepts not in concept_study_mapping
MODULE_FALLBACK = {
    '3': 'tactical_drill', '4': 'positional_drill',
    '5': 'opening_drill',  '6': 'endgame_drill',
    '7': 'psychological',  '8': 'tactical_drill',
}


# ─── Weight helpers ───────────────────────────────────────────────────────────

def recency_weight(played_at, today):
    days_ago = (today - played_at.date()).days
    return 0.5 ** (days_ago / HALF_LIFE_DAYS)


def elo_proximity_weight(game_elo, current_elo):
    if not game_elo:
        return 0.5
    return math.exp(-((game_elo - current_elo) ** 2) / (2 * ELO_SCALE ** 2))


def game_weight(played_at, game_elo, current_elo, today):
    return recency_weight(played_at, today) * elo_proximity_weight(game_elo, current_elo)


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 1 — aggregate_weakness_graph
# ══════════════════════════════════════════════════════════════════════════════

def aggregate_weakness_graph(player_id, game_type='all'):
    """
    Build or refresh weakness_graph for player_id.

    For each concept that fired as primary cause across analyzed games:
    - Applies exponential recency decay (half_life=90 days)
    - Applies Elo proximity Gaussian (scale=150 from current Elo)
    - Computes occurrence_rate, avg_cpl, trend_30_days, estimated_elo_impact
    - Also flags secondary concepts meeting diversity threshold
    - Upserts into weakness_graph
    """
    conn = get_connection()
    cur  = conn.cursor()
    today = date.today()

    # ── Current Elo per game type ──────────────────────────────────────────────
    cur.execute(
        'SELECT game_type, current_elo FROM player_ratings WHERE player_id = %s',
        (player_id,)
    )
    elo_by_type = dict(cur.fetchall())
    # Primary reference Elo: blitz > rapid > bullet > any
    primary_elo = (elo_by_type.get('blitz') or elo_by_type.get('rapid')
                   or elo_by_type.get('bullet') or next(iter(elo_by_type.values()), 1500))

    def elo_for(gtype):
        return elo_by_type.get(gtype, primary_elo)

    # ── Concept_study_mapping lookup ──────────────────────────────────────────
    cur.execute("""
        SELECT concept_code, study_module, effectiveness_score,
               elo_bracket_min, elo_bracket_max
        FROM concept_study_mapping
        ORDER BY effectiveness_score DESC
    """)
    csm_rows = cur.fetchall()

    def best_study_module(code):
        in_bracket = [
            (mod, eff) for c, mod, eff, lo, hi in csm_rows
            if c == code
            and (lo is None or lo <= primary_elo)
            and (hi is None or hi >= primary_elo)
        ]
        if in_bracket:
            return max(in_bracket, key=lambda x: x[1])[0]
        any_match = [(mod, eff) for c, mod, eff, _, _ in csm_rows if c == code]
        if any_match:
            return max(any_match, key=lambda x: x[1])[0]
        top_cat = code.split('.')[0]
        return MODULE_FALLBACK.get(top_cat, 'tactical_drill')

    # ── Fetch analyzed games ───────────────────────────────────────────────────
    gt_clause = '' if game_type == 'all' else "AND g.game_type = %(gt)s"
    base_params = {'pid': player_id, 'gt': game_type}

    cur.execute(f"""
        SELECT g.id, g.played_at, g.player_elo, g.game_type,
               COUNT(m.id) FILTER (WHERE m.eval_before IS NOT NULL) AS analyzed_moves
        FROM games g
        JOIN moves m ON m.game_id = g.id
        WHERE g.player_id = %(pid)s AND g.analyzed = TRUE {gt_clause}
        GROUP BY g.id, g.played_at, g.player_elo, g.game_type
    """, base_params)
    games = cur.fetchall()

    # Per-game weight and move count
    gw   = {}   # game_id → weight
    gm   = {}   # game_id → analyzed_move_count
    for gid, played_at, g_elo, gtype, n_moves in games:
        elo = elo_for(gtype)
        gw[gid] = game_weight(played_at, g_elo, elo, today)
        gm[gid] = n_moves or 0

    total_wm = sum(gw[g] * gm[g] for g in gw)   # total weighted analyzed moves

    # Trend window denominators (weighted analyzed moves in each period)
    cutoff_30  = today.toordinal() - 30
    cutoff_60  = today.toordinal() - 60
    recent_wm = prior_wm = 0.0
    for gid, played_at, *_ in games:
        d = played_at.date().toordinal()
        wm = gw[gid] * gm[gid]
        if d >= cutoff_30:
            recent_wm += wm
        elif d >= cutoff_60:
            prior_wm  += wm

    # ── Fetch all primary concept fires ───────────────────────────────────────
    cur.execute(f"""
        SELECT m.game_id, m.id AS move_id, c.code,
               mc.attribution_weight, m.centipawn_loss, g.played_at, g.game_type
        FROM move_concepts mc
        JOIN moves m     ON m.id   = mc.move_id
        JOIN games g     ON g.id   = m.game_id
        JOIN concepts c  ON c.id   = mc.concept_id
        WHERE g.player_id = %(pid)s
          AND mc.is_primary_cause = TRUE
          AND g.analyzed = TRUE
          {gt_clause}
        ORDER BY g.played_at ASC
    """, base_params)
    primary_rows = cur.fetchall()

    # ── Per-concept accumulators ───────────────────────────────────────────────
    PA = defaultdict(lambda: {
        'w_count': 0.0, 'occ': 0,
        'w_cpl': 0.0,   'w_attr': 0.0,
        'recent_w': 0.0, 'prior_w': 0.0,
        'game_ids': [],  'move_ids': [],
        'first': None,   'last': None,
    })

    for game_id, move_id, code, attr_w, cpl, played_at, gtype in primary_rows:
        w = gw.get(game_id, 0.0)
        if w < 1e-10:
            continue
        a = PA[code]
        a['w_count'] += w
        a['occ']     += 1
        a['w_cpl']   += w * (cpl or 0)
        a['w_attr']  += (attr_w or 0)
        d = played_at.date().toordinal()
        if d >= cutoff_30:
            a['recent_w'] += w
        elif d >= cutoff_60:
            a['prior_w']  += w
        pd = played_at.date()
        if a['first'] is None or pd < a['first']:
            a['first'] = pd
        if a['last'] is None or pd > a['last']:
            a['last'] = pd
        if game_id not in a['game_ids']:
            a['game_ids'].insert(0, game_id)  # most recent first after sort
        if len(a['move_ids']) < 3:
            a['move_ids'].append(move_id)

    # Keep only 3 most recent examples per concept
    for code, a in PA.items():
        a['game_ids'] = a['game_ids'][-3:]

    # ── Secondary concept tracking ─────────────────────────────────────────────
    cur.execute(f"""
        SELECT mc_sec.concept_id, c.code,
               COUNT(*)                           AS occ,
               COUNT(DISTINCT mc_pri.concept_id)  AS primary_div,
               COUNT(DISTINCT m.game_id)          AS game_span
        FROM move_concepts mc_sec
        JOIN moves m     ON m.id   = mc_sec.move_id
        JOIN games g     ON g.id   = m.game_id
        JOIN concepts c  ON c.id   = mc_sec.concept_id
        LEFT JOIN move_concepts mc_pri
               ON mc_pri.move_id = mc_sec.move_id AND mc_pri.is_primary_cause = TRUE
        WHERE mc_sec.is_primary_cause = FALSE
          AND g.player_id = %(pid)s
          AND g.analyzed  = TRUE
          {gt_clause}
        GROUP BY mc_sec.concept_id, c.code
        HAVING COUNT(*) >= 5
           AND COUNT(DISTINCT mc_pri.concept_id) >= 3
           AND COUNT(DISTINCT m.game_id)         >= 2
    """, base_params)
    secondary_qualifying = {row[1]: row for row in cur.fetchall()}  # code → row

    # ── Build weakness_graph rows ──────────────────────────────────────────────
    upserted = 0
    written_codes = set()

    for code, a in sorted(PA.items(), key=lambda x: -x[1]['w_count']):
        written_codes.add(code)
        if a['w_count'] < 1e-6:
            continue

        occ_rate    = a['w_count'] / total_wm * 100 if total_wm > 0 else 0.0
        avg_cpl     = a['w_cpl']  / a['w_count']    if a['w_count'] > 0 else 0.0
        avg_attr    = a['w_attr'] / a['occ']         if a['occ'] > 0 else 0.0
        recent_rate = a['recent_w'] / recent_wm * 100 if recent_wm > 0 else 0.0
        prior_rate  = a['prior_w']  / prior_wm  * 100 if prior_wm  > 0 else 0.0
        trend_30    = prior_rate - recent_rate          # positive = improving

        elo_impact  = min(ELO_IMPACT_CAP, avg_cpl * occ_rate * 0.15)
        study_mod   = best_study_module(code)
        ex_count    = EXERCISE_COUNTS.get(code, DEFAULT_EX_COUNT)
        study_hrs   = ex_count * STUDY_MIN_PER_EX.get(study_mod, 3) / 60
        efficiency  = round(elo_impact / study_hrs, 2) if study_hrs > 0 else 0.0

        days_since  = (today - a['last']).days if a['last'] else 9999
        if days_since > 60:
            status = 'resolved'
        elif trend_30 > 0.05 and a['recent_w'] > 0:
            status = 'improving'
        else:
            status = 'active'

        cur.execute("""
            INSERT INTO weakness_graph
                (player_id, concept_code, game_type,
                 occurrence_count, occurrence_rate,
                 avg_cpl_when_occurs, avg_attribution_weight,
                 trend_30_days, estimated_elo_impact,
                 primary_study_module, status,
                 first_detected, last_occurred,
                 study_efficiency, estimated_study_hours,
                 updated_at)
            VALUES
                (%(pid)s, %(code)s, %(gt)s,
                 %(occ)s, %(rate)s,
                 %(cpl)s, %(attr)s,
                 %(trend)s, %(impact)s,
                 %(mod)s, %(status)s,
                 %(first)s, %(last)s,
                 %(eff)s, %(hrs)s,
                 NOW())
            ON CONFLICT (player_id, concept_code, game_type) DO UPDATE SET
                occurrence_count       = EXCLUDED.occurrence_count,
                occurrence_rate        = EXCLUDED.occurrence_rate,
                avg_cpl_when_occurs    = EXCLUDED.avg_cpl_when_occurs,
                avg_attribution_weight = EXCLUDED.avg_attribution_weight,
                trend_30_days          = EXCLUDED.trend_30_days,
                estimated_elo_impact   = EXCLUDED.estimated_elo_impact,
                primary_study_module   = EXCLUDED.primary_study_module,
                status                 = EXCLUDED.status,
                first_detected         = EXCLUDED.first_detected,
                last_occurred          = EXCLUDED.last_occurred,
                study_efficiency       = EXCLUDED.study_efficiency,
                estimated_study_hours  = EXCLUDED.estimated_study_hours,
                updated_at             = NOW()
        """, {
            'pid': player_id, 'code': code, 'gt': game_type,
            'occ': a['occ'], 'rate': round(occ_rate, 4),
            'cpl': round(avg_cpl, 1), 'attr': round(avg_attr, 3),
            'trend': round(trend_30, 4), 'impact': round(elo_impact, 1),
            'mod': study_mod, 'status': status,
            'first': a['first'], 'last': a['last'],
            'eff': efficiency, 'hrs': round(study_hrs, 1),
        })
        upserted += 1

    # ── Secondary concepts not already primary ────────────────────────────────
    secondary_added = 0
    for code, row in secondary_qualifying.items():
        if code in written_codes:
            continue   # already has a primary entry — don't double-write
        _, _, sec_occ, sec_div, sec_games = row
        study_mod  = best_study_module(code)
        ex_count   = EXERCISE_COUNTS.get(code, DEFAULT_EX_COUNT)
        study_hrs  = ex_count * STUDY_MIN_PER_EX.get(study_mod, 3) / 60
        # Reduced elo_impact for secondary-only concepts
        sec_impact = min(ELO_IMPACT_CAP * 0.5, 5.0 * sec_div)
        efficiency = round(sec_impact / study_hrs, 2) if study_hrs > 0 else 0.0
        cur.execute("""
            INSERT INTO weakness_graph
                (player_id, concept_code, game_type,
                 occurrence_count, occurrence_rate,
                 avg_cpl_when_occurs, avg_attribution_weight,
                 estimated_elo_impact, primary_study_module, status,
                 study_efficiency, estimated_study_hours,
                 updated_at)
            VALUES
                (%(pid)s, %(code)s, %(gt)s,
                 %(occ)s, 0.0,
                 0.0, 0.5,
                 %(impact)s, %(mod)s, 'active',
                 %(eff)s, %(hrs)s,
                 NOW())
            ON CONFLICT (player_id, concept_code, game_type) DO NOTHING
        """, {
            'pid': player_id, 'code': code, 'gt': game_type,
            'occ': sec_occ, 'impact': round(sec_impact, 1),
            'mod': study_mod, 'eff': efficiency, 'hrs': round(study_hrs, 1),
        })
        secondary_added += 1

    conn.commit()
    cur.close()
    conn.close()

    print(f"weakness_graph: {upserted} primary + {secondary_added} secondary concepts "
          f"upserted for player {player_id} (game_type={game_type})")
    return upserted


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 2 — compute_study_efficiency
# ══════════════════════════════════════════════════════════════════════════════

def compute_study_efficiency(player_id):
    """
    Recalculate study_efficiency and estimated_study_hours for all
    weakness_graph rows for this player.

    study_efficiency = estimated_elo_impact / estimated_study_hours
    estimated_study_hours = exercise_count * minutes_per_exercise / 60
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT concept_code, estimated_elo_impact, primary_study_module
        FROM weakness_graph
        WHERE player_id = %s
    """, (player_id,))
    rows = cur.fetchall()

    updated = 0
    for code, elo_impact, study_mod in rows:
        ex_count  = EXERCISE_COUNTS.get(code, DEFAULT_EX_COUNT)
        min_per   = STUDY_MIN_PER_EX.get(study_mod or 'tactical_drill', 3)
        study_hrs = round(ex_count * min_per / 60, 1)
        efficiency = round((elo_impact or 0) / study_hrs, 2) if study_hrs > 0 else 0.0
        cur.execute("""
            UPDATE weakness_graph
               SET study_efficiency = %s, estimated_study_hours = %s
             WHERE player_id = %s AND concept_code = %s
        """, (efficiency, study_hrs, player_id, code))
        updated += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"study_efficiency updated for {updated} weaknesses (player {player_id})")
    return updated


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 3 — generate_prescription
# ══════════════════════════════════════════════════════════════════════════════

def generate_prescription(player_id, top_n=10):
    """
    Return ranked list of study recommendations.

    Filters to player's current Elo bracket (where concept_study_mapping exists).
    Sorts by study_efficiency (Elo gain per study hour) DESC.
    Secondary prescriptions appended after primary list.
    """
    conn = get_connection()
    cur  = conn.cursor()

    # Current Elo
    cur.execute(
        'SELECT game_type, current_elo FROM player_ratings WHERE player_id = %s',
        (player_id,)
    )
    elo_by_type = dict(cur.fetchall())
    player_elo = (elo_by_type.get('blitz') or elo_by_type.get('rapid')
                  or next(iter(elo_by_type.values()), 1500))

    # Active and improving weaknesses ordered by efficiency (all game_types)
    cur.execute("""
        SELECT wg.concept_code, c.name,
               wg.occurrence_count, wg.occurrence_rate,
               wg.avg_cpl_when_occurs, wg.estimated_elo_impact,
               wg.study_efficiency, wg.primary_study_module,
               wg.avg_attribution_weight, wg.trend_30_days,
               wg.first_detected, wg.last_occurred, wg.status,
               wg.game_type
        FROM weakness_graph wg
        JOIN concepts c ON c.code = wg.concept_code
        WHERE wg.player_id = %s AND wg.status IN ('active', 'improving')
        ORDER BY COALESCE(wg.study_efficiency, 0) DESC
    """, (player_id,))
    all_active = cur.fetchall()

    # Which codes have a bracket-matching mapping?
    cur.execute("""
        SELECT DISTINCT concept_code FROM concept_study_mapping
        WHERE (elo_bracket_min IS NULL OR elo_bracket_min <= %s)
          AND (elo_bracket_max IS NULL OR elo_bracket_max >= %s)
    """, (player_elo, player_elo))
    in_bracket = {r[0] for r in cur.fetchall()}

    primary_recs   = []
    secondary_recs = []

    for row in all_active:
        (code, name, occ_count, occ_rate, avg_cpl, elo_impact,
         efficiency, study_mod, avg_attr, trend_30,
         first_detected, last_occurred, status, game_type) = row

        # Fetch 3 most recent example game/move IDs
        cur.execute("""
            SELECT DISTINCT ON (m.game_id) m.game_id, m.id
            FROM move_concepts mc
            JOIN moves m    ON m.id  = mc.move_id
            JOIN concepts c ON c.id  = mc.concept_id
            JOIN games g    ON g.id  = m.game_id
            WHERE g.player_id = %s AND c.code = %s
              AND mc.is_primary_cause = TRUE
            ORDER BY m.game_id DESC
            LIMIT 3
        """, (player_id, code))
        examples = cur.fetchall()
        ex_games = [r[0] for r in examples]
        ex_moves = [r[1] for r in examples]

        # Trend label
        if trend_30 is None:
            trend_lbl = '~'
        elif trend_30 > 0.10:
            trend_lbl = 'improving'
        elif trend_30 < -0.10:
            trend_lbl = 'worsening'
        else:
            trend_lbl = 'stable'

        rec = {
            'concept_code':         code,
            'concept_name':         name,
            'occurrence_count':     occ_count,
            'occurrence_rate':      round(occ_rate or 0, 3),
            'avg_cpl':              round(avg_cpl or 0, 0),
            'estimated_elo_impact': round(elo_impact or 0, 1),
            'study_efficiency':     round(efficiency or 0, 2),
            'primary_study_module': study_mod,
            'avg_attribution':      round(avg_attr or 0, 3),
            'trend_30_days':        round(trend_30 or 0, 3),
            'trend_label':          trend_lbl,
            'status':               status,
            'game_type':            game_type,
            'example_game_ids':     ex_games,
            'example_move_ids':     ex_moves,
        }

        if code in in_bracket:
            primary_recs.append(rec)
        else:
            secondary_recs.append(rec)

    cur.close()
    conn.close()

    primary_recs   = primary_recs[:top_n]
    secondary_recs = secondary_recs[:max(0, top_n - len(primary_recs))]
    return primary_recs, secondary_recs


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 4 — print_weakness_report
# ══════════════════════════════════════════════════════════════════════════════

def print_weakness_report(player_id):
    """
    Human-readable weakness diagnosis for the player.
    This is the first real diagnostic output of the system.
    """
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute('SELECT username FROM players WHERE id = %s', (player_id,))
    row = cur.fetchone()
    username = row[0] if row else f'player_{player_id}'
    cur.execute("""
        SELECT game_type, current_elo FROM player_ratings
        WHERE player_id = %s ORDER BY current_elo DESC
    """, (player_id,))
    elo_rows = cur.fetchall()
    cur.execute("""
        SELECT COUNT(*) FROM games WHERE player_id = %s AND analyzed = TRUE
    """, (player_id,))
    analyzed_games = cur.fetchone()[0]
    cur.execute("""
        SELECT COUNT(DISTINCT mc.move_id)
        FROM move_concepts mc JOIN moves m ON m.id = mc.move_id
        JOIN games g ON g.id = m.game_id WHERE g.player_id = %s
    """, (player_id,))
    tagged_moves = cur.fetchone()[0]
    cur.close()
    conn.close()

    primary_recs, secondary_recs = generate_prescription(player_id, top_n=10)

    W = 70
    SEP = '-' * W

    print()
    print('=' * W)
    print(f'  CHESS WEAKNESS PROFILE — {username.upper()}')
    print('=' * W)

    # Player ratings
    rating_str = '   '.join(f'{gt.capitalize()}: {elo}' for gt, elo in elo_rows)
    print(f'  Ratings:  {rating_str}')
    print(f'  Data:     {analyzed_games:,} games analyzed   {tagged_moves:,} moves tagged')
    print()

    if not primary_recs and not secondary_recs:
        print('  No active weaknesses detected. Run aggregate_weakness_graph first.')
        print()
        return

    total_impact   = sum(r['estimated_elo_impact'] for r in primary_recs)
    total_hours    = sum(
        EXERCISE_COUNTS.get(r['concept_code'], DEFAULT_EX_COUNT)
        * STUDY_MIN_PER_EX.get(r['primary_study_module'] or 'tactical_drill', 3) / 60
        for r in primary_recs
    )

    print(f'  TOP {len(primary_recs)} WEAKNESSES BY STUDY EFFICIENCY (Elo/hour)')
    print(f'  Estimated gain if all addressed: +{total_impact:.0f} Elo')
    print(f'  Estimated study time:            {total_hours:.0f} hours')
    print()
    print(f'  {"#":<3} {"Concept":<38} {"Rate":>5} {"CPL":>5} {"Elo":>4}  {"Eff":>6}  {"Module"}')
    print(f'  {"---":<3} {"-"*38} {"-----":>5} {"-----":>5} {"----":>4}  {"------":>6}  {"-"*18}')

    for i, r in enumerate(primary_recs, 1):
        trend_sym = 'v' if r['trend_label'] == 'improving' else ('^' if r['trend_label'] == 'worsening' else '=')
        print(
            f'  {i:<3} {r["concept_name"][:38]:<38} '
            f'{r["occurrence_rate"]:>5.2f} {r["avg_cpl"]:>5.0f} '
            f'{r["estimated_elo_impact"]:>4.0f}  '
            f'{r["study_efficiency"]:>6.2f}  '
            f'{r["primary_study_module"] or "?":<18}  {trend_sym}'
        )

    print()
    print(f'  Columns: Rate=mistakes/100 weighted moves  CPL=avg centipawn loss')
    print(f'           Elo=estimated Elo impact  Eff=Elo/study-hour  ^worse vbetter')

    # Detailed cards for top 5
    print()
    print('=' * W)
    print('  TOP 5 DETAILED PRESCRIPTIONS')
    print('=' * W)

    for r in primary_recs[:5]:
        print()
        print(f'  [{r["concept_code"]}] {r["concept_name"]}')
        print(f'  {SEP}')
        is_session = r.get('game_type') == 'session'
        rate_label = 'sessions per 100' if is_session else 'mistakes per 100 moves'
        print(f'  How often:       {r["occurrence_rate"]:.2f} {rate_label}  ({r["occurrence_count"]:,} total)')
        print(f'  Average CPL:     {r["avg_cpl"]:.0f}cp {"extra during" if is_session else "when this fires"}')
        print(f'  Elo impact est:  +{r["estimated_elo_impact"]:.1f} Elo if fixed')
        print(f'  Study priority:  {r["study_efficiency"]:.2f} Elo/hour  ->  {r["primary_study_module"]}')
        if not is_session:
            print(f'  Trend (30d):     {r["trend_label"]}  (d {r["trend_30_days"]:+.3f} mistakes/100 moves)')
            print(f'  Signal quality:  avg attribution weight = {r["avg_attribution"]:.3f}')
        if r['example_game_ids']:
            print(f'  Example games:   {r["example_game_ids"]}')
            print(f'  Example moves:   {r["example_move_ids"]}')

    # Secondary prescriptions
    if secondary_recs:
        print()
        print(SEP)
        print('  SECONDARY PRESCRIPTIONS (not yet bracket-mapped — study after top 5)')
        print(SEP)
        for r in secondary_recs[:5]:
            print(
                f'  [{r["concept_code"]}] {r["concept_name"][:35]:<35}  '
                f'rate={r["occurrence_rate"]:.2f}  '
                f'impact=+{r["estimated_elo_impact"]:.0f}'
            )

    print()
    print('=' * W)
    print()


# ══════════════════════════════════════════════════════════════════════════════
# FUNCTION 5 — aggregate_session_weaknesses
# ══════════════════════════════════════════════════════════════════════════════

def aggregate_session_weaknesses(player_id):
    """
    Derive psychological weakness entries for tilt and fatigue from sessions.

    occurrence_rate here = affected_sessions / total_sessions * 100
    (reinterpreted from "per 100 moves" to "per 100 sessions" for display).
    avg_cpl_when_occurs = extra CPL above baseline during affected sessions.
    elo_impact capped at ELO_IMPACT_CAP like move-level weaknesses.
    """
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*)                                                AS total,
            COUNT(*) FILTER (WHERE tilt_detected)                  AS tilt_count,
            COUNT(*) FILTER (WHERE fatigue_detected)               AS fatigue_count,
            AVG(avg_cpl)                                           AS avg_cpl,
            AVG(tilt_coefficient) FILTER (WHERE tilt_detected
                                      AND tilt_coefficient IS NOT NULL) AS avg_tilt_coeff,
            MIN(started_at)                                        AS first_session,
            MAX(started_at)                                        AS last_session
        FROM sessions
        WHERE player_id = %s
    """, (player_id,))
    row = cur.fetchone()
    (total, tilt_count, fatigue_count,
     avg_cpl_overall, avg_tilt_coeff,
     first_session, last_session) = row

    if not total or total == 0:
        print(f"No sessions found for player {player_id}.")
        cur.close(); conn.close()
        return

    avg_cpl_overall = float(avg_cpl_overall or 80.0)
    avg_tilt_coeff  = float(avg_tilt_coeff  or 1.5)
    today = date.today()

    def _upsert(code, occ_count, occ_rate, avg_cpl_delta, study_mod, first, last):
        elo_impact = min(ELO_IMPACT_CAP, avg_cpl_delta * occ_rate * 0.15)
        ex_count   = EXERCISE_COUNTS.get(code, DEFAULT_EX_COUNT)
        study_hrs  = ex_count * STUDY_MIN_PER_EX.get(study_mod, 2) / 60
        efficiency = round(elo_impact / study_hrs, 2) if study_hrs > 0 else 0.0
        days_since = (today - last.date()).days if last else 9999
        status     = 'resolved' if days_since > 60 else 'active'
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
                (%(pid)s, %(code)s, 'session',
                 %(occ)s, %(rate)s,
                 %(cpl)s, 0.80,
                 %(impact)s, %(mod)s, %(status)s,
                 %(first)s, %(last)s,
                 %(eff)s, %(hrs)s,
                 NOW())
            ON CONFLICT (player_id, concept_code, game_type) DO UPDATE SET
                occurrence_count       = EXCLUDED.occurrence_count,
                occurrence_rate        = EXCLUDED.occurrence_rate,
                avg_cpl_when_occurs    = EXCLUDED.avg_cpl_when_occurs,
                estimated_elo_impact   = EXCLUDED.estimated_elo_impact,
                primary_study_module   = EXCLUDED.primary_study_module,
                status                 = EXCLUDED.status,
                first_detected         = EXCLUDED.first_detected,
                last_occurred          = EXCLUDED.last_occurred,
                study_efficiency       = EXCLUDED.study_efficiency,
                estimated_study_hours  = EXCLUDED.estimated_study_hours,
                updated_at             = NOW()
        """, {
            'pid': player_id, 'code': code, 'status': status,
            'occ': int(occ_count),
            'rate': round(occ_rate, 3),
            'cpl': round(avg_cpl_delta, 1),
            'impact': round(elo_impact, 1),
            'mod': study_mod,
            'eff': efficiency, 'hrs': round(study_hrs, 1),
            'first': first.date() if first else None,
            'last': last.date() if last else None,
        })

    # ── Tilt (7.3.1) ─────────────────────────────────────────────────────────
    tilt_rate      = tilt_count / total * 100
    # Extra CPL during tilt = baseline * (coeff - 1)
    cpl_delta_tilt = avg_cpl_overall * (avg_tilt_coeff - 1.0)
    _upsert('7.3.1', tilt_count, tilt_rate, cpl_delta_tilt, 'psychological', first_session, last_session)

    # ── Fatigue / clock usage (7.1.1) ─────────────────────────────────────────
    fatigue_rate      = fatigue_count / total * 100
    cpl_delta_fatigue = avg_cpl_overall * 0.30
    _upsert('7.1.1', fatigue_count, fatigue_rate, cpl_delta_fatigue, 'psychological', first_session, last_session)

    conn.commit()
    cur.close()
    conn.close()

    print(f"Session weaknesses upserted: "
          f"7.3.1 tilt ({tilt_rate:.1f}% of {total} sessions, "
          f"+{cpl_delta_tilt:.0f}cp), "
          f"7.1.1 fatigue ({fatigue_rate:.1f}%, +{cpl_delta_fatigue:.0f}cp)")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — run full pipeline on player
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    gt  = sys.argv[2] if len(sys.argv) > 2 else 'all'

    print(f'Running weakness aggregator for player_id={pid}, game_type={gt}...')
    aggregate_weakness_graph(pid, gt)
    compute_study_efficiency(pid)
    aggregate_session_weaknesses(pid)
    print_weakness_report(pid)
