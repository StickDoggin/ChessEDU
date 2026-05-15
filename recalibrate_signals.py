"""
recalibrate_signals.py

Fixes the bracket miss over-classification and builds the concept_position_pattern
table — the strongest coaching signal in the system.

A REAL bracket miss requires ALL of:
  1. maia_probability < BRACKET_THRESHOLD (player's move was unlikely for their rating)
  2. centipawn_loss > MINOR_CPL (the miss actually cost something)
  3. complexity_estimate < MAX_COMPLEXITY (position was not extremely complex)

BRACKET_THRESHOLD calibration:
  - Set to p25 of maia_probability on mistake moves (CPL > 50)
  - Good moves cluster near 1.0; mistake moves at lower values
  - Target: 10-15% of moves flagged as bracket misses
  - Default 0.15 (update from diagnostic query 1 p25 if data exists)

Position types are inferred from FEN piece counts:
  rook_ending, queen_ending, king_pawn_ending, bishop_ending,
  knight_ending, minor_piece_ending, rook_and_minor_ending,
  double_rook_ending, open_middlegame, closed_middlegame,
  semi_open_middlegame, complex_middlegame, simplified_middlegame

Run: python recalibrate_signals.py
"""
import psycopg
import chess
from collections import defaultdict
from datetime import date
import math

DB = dict(host="localhost", port=5432, dbname="chess_engine",
          user="postgres", password="0088")

# ── THRESHOLDS ───────────────────────────────────────────────────────────────
# Set BRACKET_THRESHOLD from diagnostic query 1 p25 of mistake moves.
# Default 0.15 targets ~10-15% bracket miss rate.
# If rate > 20% after running, lower by multiplying by 0.6 and rerun.
BRACKET_THRESHOLD = 0.15

CRITICAL_CPL    = 150
SIGNIFICANT_CPL = 75
MINOR_CPL       = 30
MAX_COMPLEXITY  = 0.75   # skip flagging in very complex positions
RECENCY_DAYS    = 90


def infer_position_type(fen: str) -> str:
    """Classify a chess position by its material signature."""
    try:
        board = chess.Board(fen)
    except Exception:
        return 'unknown'

    def c(pt, col):
        return len(board.pieces(pt, col))

    wq = c(chess.QUEEN,  chess.WHITE); bq = c(chess.QUEEN,  chess.BLACK)
    wr = c(chess.ROOK,   chess.WHITE); br = c(chess.ROOK,   chess.BLACK)
    wb = c(chess.BISHOP, chess.WHITE); bb = c(chess.BISHOP, chess.BLACK)
    wn = c(chess.KNIGHT, chess.WHITE); bn = c(chess.KNIGHT, chess.BLACK)
    mw = wb + wn; mb = bb + bn
    total = wq + bq + wr + br + wb + bb + wn + bn

    # No queens
    if wq == 0 and bq == 0:
        if wr == 0 and br == 0:
            if mw == 0 and mb == 0:
                return 'king_pawn_ending'
            if wb == 1 and bb == 1 and mw == 1 and mb == 1:
                return 'bishop_ending'
            if wn == 1 and bn == 1 and mw == 1 and mb == 1:
                return 'knight_ending'
            return 'minor_piece_ending'
        if wr == 1 and br == 1:
            return 'rook_ending' if mw == 0 and mb == 0 else 'rook_and_minor_ending'
        if wr == 2 and br == 2:
            return 'double_rook_ending'
        if (wr == 2 and br == 1) or (wr == 1 and br == 2):
            return 'rook_imbalance_ending'
        return 'rook_ending'

    # No rooks or minors, only queens
    if wq >= 1 and bq >= 1 and wr == 0 and br == 0 and mw == 0 and mb == 0:
        return 'queen_ending'

    if wq >= 1 and bq >= 1 and (wr >= 1 or br >= 1):
        if total >= 10:
            return 'complex_middlegame'
        return 'queen_rook_ending'

    # Middlegame by pawn structure
    if total >= 12:
        center_pawns = sum(
            1 for sq in [chess.E4, chess.E5, chess.D4, chess.D5]
            if board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN
        )
        if center_pawns == 0:
            return 'open_middlegame'
        if center_pawns >= 3:
            return 'closed_middlegame'
        return 'semi_open_middlegame'

    if total >= 6:
        return 'simplified_middlegame'

    return 'other'


def compute_trend(monthly_rates: list) -> tuple:
    """
    Given [(month_str, rate)] sorted oldest-first, return
    (direction, confidence_r2, months_worsening).
    Uses linear regression slope.
    """
    if len(monthly_rates) < 3:
        return 'stable', 0.0, 0

    months = list(range(len(monthly_rates)))
    rates  = [r[1] for r in monthly_rates]
    n      = len(months)
    xb     = sum(months) / n
    yb     = sum(rates) / n

    num   = sum((months[i] - xb) * (rates[i] - yb) for i in range(n))
    denom = sum((months[i] - xb) ** 2 for i in range(n))
    slope = num / denom if denom else 0

    ss_tot = sum((r - yb) ** 2 for r in rates)
    ss_res = sum((rates[i] - (yb + slope * (months[i] - xb))) ** 2 for i in range(n))
    r2 = max(0.0, 1.0 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

    months_worsening = sum(1 for i in range(1, n) if rates[i] > rates[i - 1])

    if slope > 0.005 and r2 > 0.3:
        direction = 'worsening'
    elif slope < -0.005 and r2 > 0.3:
        direction = 'improving'
    else:
        direction = 'stable'

    return direction, round(r2, 3), months_worsening


def compute_priority(occurrence_count, avg_cpl, maia_deficit,
                     result_impact, trend_direction, months_worsening,
                     recency_weight):
    """
    Composite priority score (0-1). Higher = more important to study.

    Weights:
      30% frequency  — log-normalized occurrence count
      25% severity   — avg CPL normalized (200 CPL = 1.0)
      20% maia deficit — how far below bracket average
      15% result impact — win rate difference when concept fires
      10% trend bonus — worsening trends get boosted
    """
    freq_score    = min(1.0, math.log1p(occurrence_count) / math.log1p(5000))
    sev_score     = min(1.0, (avg_cpl or 0) / 200.0)
    deficit_score = min(1.0, max(0.0, maia_deficit or 0.0))
    impact_score  = min(1.0, max(0.0, result_impact or 0.0))
    trend_bonus   = 0.2 if trend_direction == 'worsening' else 0.0
    trend_bonus  += min(0.1, months_worsening * 0.02)

    score = (
        0.30 * freq_score    +
        0.25 * sev_score     +
        0.20 * deficit_score +
        0.15 * impact_score  +
        0.10 * trend_bonus
    ) * recency_weight

    return round(score, 4)


def main():
    conn = psycopg.connect(**DB)
    cur  = conn.cursor()

    # ── Step 1: Recalibrate bracket miss flags ───────────────────────────────
    print("Step 1: Recalibrating bracket miss flags...")
    print(f"  Using BRACKET_THRESHOLD={BRACKET_THRESHOLD}, "
          f"MINOR_CPL={MINOR_CPL}, MAX_COMPLEXITY={MAX_COMPLEXITY}")

    cur.execute("""
        UPDATE maia_move_delta
        SET
            is_bracket_miss = (
                actual_maia_prob < %s
                AND centipawn_loss > %s
                AND (complexity_estimate IS NULL OR complexity_estimate < %s)
            ),
            is_personal_miss = (
                actual_maia_prob >= %s
                AND actual_maia_prob < 0.60
                AND centipawn_loss > %s
                AND wp_delta > 0.05
            ),
            miss_severity = CASE
                WHEN centipawn_loss >= %s THEN 'critical'
                WHEN centipawn_loss >= %s THEN 'significant'
                WHEN centipawn_loss >= %s THEN 'minor'
                ELSE NULL
            END
        WHERE player_id = 1
    """, (
        BRACKET_THRESHOLD, MINOR_CPL, MAX_COMPLEXITY,
        BRACKET_THRESHOLD, MINOR_CPL,
        CRITICAL_CPL, SIGNIFICANT_CPL, MINOR_CPL,
    ))
    conn.commit()

    cur.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN is_bracket_miss  THEN 1 ELSE 0 END) as bracket,
            SUM(CASE WHEN is_personal_miss THEN 1 ELSE 0 END) as personal,
            ROUND(100.0 * SUM(CASE WHEN is_bracket_miss THEN 1 ELSE 0 END)
                  / NULLIF(COUNT(*), 0), 1) as bracket_pct
        FROM maia_move_delta WHERE player_id = 1
    """)
    r = cur.fetchone()
    total, bracket, personal, bracket_pct = r
    print(f"  Total: {total:,}  bracket misses: {bracket or 0:,} ({bracket_pct or 0}%)  "
          f"personal misses: {personal or 0:,}")

    bracket_pct_val = float(bracket_pct or 0)
    if bracket_pct_val > 20 and (total or 0) > 0:
        new_threshold = BRACKET_THRESHOLD * 0.6
        print(f"\n  WARNING: {bracket_pct_val}% bracket miss rate still too high.")
        print(f"  Lower BRACKET_THRESHOLD from {BRACKET_THRESHOLD} to {new_threshold:.3f} and rerun.")
    elif (total or 0) == 0:
        print("  No data in maia_move_delta yet. Run maia_pass.py and then rerun this script.")

    # ── Step 2: Classify position types ─────────────────────────────────────
    print("\nStep 2: Classifying position types...")

    cur.execute("""
        SELECT md.id, m.fen_before, m.phase
        FROM maia_move_delta md
        JOIN moves m ON md.move_id = m.id
        WHERE md.player_id = 1
          AND md.position_type IS NULL
        ORDER BY md.id
    """)
    rows = cur.fetchall()
    print(f"  Classifying {len(rows):,} positions...")

    batch = []
    for delta_id, fen, phase in rows:
        pos_type = infer_position_type(fen) if fen else f"{phase or 'unknown'}_unknown"
        batch.append((pos_type, delta_id))

    if batch:
        cur.executemany(
            "UPDATE maia_move_delta SET position_type = %s WHERE id = %s",
            batch
        )
        conn.commit()

    # Distribution report
    cur.execute("""
        SELECT position_type, COUNT(*) as cnt,
               AVG(centipawn_loss) as avg_cpl,
               AVG(wp_delta) as avg_wpd
        FROM maia_move_delta
        WHERE player_id = 1
        GROUP BY position_type
        ORDER BY cnt DESC
        LIMIT 15
    """)
    print(f"\n  {'Position Type':<30} {'Count':>7} {'Avg CPL':>8} {'Avg WPd':>8}")
    print("  " + "-" * 57)
    for r in cur.fetchall():
        print(f"  {r[0]:<30} {r[1]:>7,} {(r[2] or 0):>8.1f} {(r[3] or 0):>8.4f}")

    # ── Step 3: Build concept_position_pattern ───────────────────────────────
    print("\nStep 3: Building concept_position_pattern table...")
    cur.execute("DELETE FROM concept_position_pattern WHERE player_id = 1")
    conn.commit()

    cur.execute("""
        SELECT DISTINCT c.code, c.name
        FROM move_concepts mc
        JOIN concepts c ON c.id = mc.concept_id
        JOIN moves m ON m.id = mc.move_id
        JOIN games g ON m.game_id = g.id
        WHERE g.player_id = 1
          AND (mc.is_noise IS NULL OR mc.is_noise = FALSE)
    """)
    concepts = cur.fetchall()
    print(f"  Processing {len(concepts)} concepts...")

    # Baseline win rate
    cur.execute("""
        SELECT AVG(CASE WHEN result = 'win' THEN 1.0 ELSE 0.0 END)
        FROM games WHERE player_id = 1 AND analyzed = TRUE
    """)
    baseline_wr = float(cur.fetchone()[0] or 0.45)

    # Total games per month for normalization
    cur.execute("""
        SELECT TO_CHAR(played_at, 'YYYY-MM') AS month, COUNT(*) AS total
        FROM games WHERE player_id = 1 AND analyzed = TRUE
        GROUP BY month
    """)
    games_by_month = {r[0]: int(r[1]) for r in cur.fetchall()}

    today      = date.today()
    rows_built = 0

    for concept_code, concept_name in concepts:
        cur.execute("""
            SELECT
                md.position_type,
                m.phase,
                m.centipawn_loss,
                md.wp_delta,
                m.maia_probability,
                md.is_bracket_miss,
                g.result,
                g.played_at,
                m.game_id
            FROM move_concepts mc
            JOIN concepts c ON c.id = mc.concept_id AND c.code = %s
            JOIN moves m ON m.id = mc.move_id
            JOIN games g ON m.game_id = g.id
            LEFT JOIN maia_move_delta md ON md.move_id = mc.move_id
            WHERE g.player_id = 1
              AND (mc.is_noise IS NULL OR mc.is_noise = FALSE)
        """, (concept_code,))
        tagged = cur.fetchall()

        if not tagged:
            continue

        by_pos = defaultdict(list)
        for row in tagged:
            pos_type = row[0] or f"{row[1] or 'unknown'}_general"
            by_pos[pos_type].append(row)

        for pos_type, moves in by_pos.items():
            if len(moves) < 5:
                continue

            avg_cpl  = sum(m[2] or 0 for m in moves) / len(moves)
            avg_wpd  = sum(m[3] or 0 for m in moves) / len(moves)
            avg_maia = sum(m[4] or 0.5 for m in moves) / len(moves)
            maia_def = max(0.0, 0.50 - avg_maia)

            win_rate   = sum(1 for m in moves if m[6] == 'win') / len(moves)
            result_imp = baseline_wr - win_rate

            # Recency weight: recent games count more
            recency_scores = []
            for m in moves:
                if m[7]:
                    days = (today - m[7].date()).days
                    recency_scores.append(max(0.3, 1.0 - (days / 365)))
                else:
                    recency_scores.append(0.5)
            recency_weight = sum(recency_scores) / len(recency_scores)

            # Monthly trend: occurrence rate normalized by total games that month
            monthly = defaultdict(int)
            for m in moves:
                if m[7]:
                    monthly[m[7].strftime('%Y-%m')] += 1

            monthly_rates = sorted([
                (month, count / max(games_by_month.get(month, 1), 1))
                for month, count in monthly.items()
            ])  # oldest-first

            trend_dir, trend_conf, months_worse = compute_trend(monthly_rates)
            priority = compute_priority(
                len(moves), avg_cpl, maia_def,
                result_imp, trend_dir, months_worse, recency_weight
            )

            cur.execute("""
                INSERT INTO concept_position_pattern (
                    player_id, concept_code, position_type, phase,
                    occurrence_count, game_count, miss_rate,
                    avg_cpl, avg_wp_delta,
                    avg_maia_prob, bracket_avg_prob, maia_deficit,
                    win_rate_with_miss, win_rate_baseline, result_impact,
                    trend_direction, trend_confidence, months_worsening,
                    priority_score, updated_at
                ) VALUES (
                    1, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, NOW()
                )
                ON CONFLICT (player_id, concept_code, position_type)
                DO UPDATE SET
                    occurrence_count  = EXCLUDED.occurrence_count,
                    game_count        = EXCLUDED.game_count,
                    miss_rate         = EXCLUDED.miss_rate,
                    avg_cpl           = EXCLUDED.avg_cpl,
                    avg_wp_delta      = EXCLUDED.avg_wp_delta,
                    avg_maia_prob     = EXCLUDED.avg_maia_prob,
                    maia_deficit      = EXCLUDED.maia_deficit,
                    win_rate_with_miss= EXCLUDED.win_rate_with_miss,
                    win_rate_baseline = EXCLUDED.win_rate_baseline,
                    result_impact     = EXCLUDED.result_impact,
                    trend_direction   = EXCLUDED.trend_direction,
                    trend_confidence  = EXCLUDED.trend_confidence,
                    months_worsening  = EXCLUDED.months_worsening,
                    priority_score    = EXCLUDED.priority_score,
                    updated_at        = NOW()
            """, (
                concept_code, pos_type, moves[0][1],
                len(moves), len({m[8] for m in moves}),
                len(moves) / max(len({m[8] for m in moves}), 1),
                avg_cpl, avg_wpd,
                avg_maia, 0.50, maia_def,
                win_rate, baseline_wr, result_imp,
                trend_dir, trend_conf, months_worse,
                priority
            ))
            rows_built += 1

        if rows_built % 100 == 0 and rows_built > 0:
            conn.commit()
            print(f"  Built {rows_built} patterns...")

    conn.commit()
    print(f"\n  Built {rows_built} concept-position patterns")

    # ── Step 4: Print top 20 patterns ────────────────────────────────────────
    print("\nTop 20 highest-priority concept-position patterns:")
    cur.execute("""
        SELECT
            cpp.concept_code, cpp.position_type,
            cpp.occurrence_count, cpp.avg_cpl,
            cpp.maia_deficit, cpp.result_impact,
            cpp.trend_direction, cpp.months_worsening,
            cpp.priority_score
        FROM concept_position_pattern cpp
        WHERE cpp.player_id = 1
        ORDER BY cpp.priority_score DESC
        LIMIT 20
    """)
    print(f"\n{'Concept':<14} {'Position Type':<28} {'Occ':>5} {'CPL':>6} "
          f"{'MaiaDef':>8} {'Impact':>7} {'Trend':<11} {'Wrs':>4} {'Pri':>7}")
    print("-" * 97)
    for r in cur.fetchall():
        print(f"{r[0]:<14} {r[1]:<28} {r[2]:>5} {(r[3] or 0):>6.0f} "
              f"{(r[4] or 0):>8.3f} {(r[5] or 0):>7.3f} "
              f"{r[6]:<11} {r[7]:>4} {r[8]:>7.4f}")

    cur.close()
    conn.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
