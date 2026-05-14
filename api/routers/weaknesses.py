"""Prescription and opening-gap endpoints."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import psycopg
from api.dependencies import get_db

router = APIRouter(prefix="/players", tags=["weaknesses"])
Db = Annotated[psycopg.Connection, Depends(get_db)]


class WeaknessTypeSplit(BaseModel):
    personal_count: int
    bracket_count: int
    personal_rate: float
    bracket_rate: float


class PrescriptionItem(BaseModel):
    rank: int
    concept_code: str
    concept_name: str
    occurrence_count: int
    occurrence_rate: float
    pct_games_affected: float
    avg_pawns_lost: float | None
    total_games: int
    estimated_elo_impact: float
    study_efficiency: float
    study_module: str | None
    study_subtype: str | None
    example_game_ids: list[int]
    example_move_ids: list[int]
    mastery_score: float
    status: str
    trend_label: str
    weakness_type_breakdown: WeaknessTypeSplit | None


class OpeningGap(BaseModel):
    eco: str
    opening_name: str
    gap_score: float
    games_seen: int
    avg_time_vs_expected: float | None
    deviation_count: int


@router.get("/{player_id}/prescription", response_model=list[PrescriptionItem])
def get_prescription(player_id: int, db: Db):
    cur = db.cursor()

    # Total analyzed games for pct_games_affected
    cur.execute(
        "SELECT COUNT(*) FROM games WHERE player_id = %s AND analyzed = TRUE",
        (player_id,)
    )
    total_games = int(cur.fetchone()[0] or 0)

    # ELO for bracket lookup
    cur.execute(
        "SELECT game_type, current_elo FROM player_ratings WHERE player_id = %s",
        (player_id,)
    )
    elo_rows = dict(cur.fetchall())
    player_elo = (elo_rows.get('blitz') or elo_rows.get('rapid')
                  or next(iter(elo_rows.values()), 1500))

    # Weakness graph rows — exclude broad parent codes (use subtypes instead)
    cur.execute("""
        SELECT wg.concept_code, c.name,
               wg.occurrence_rate, wg.estimated_elo_impact,
               wg.study_efficiency, wg.primary_study_module,
               COALESCE(wg.mastery_score, 0), wg.status,
               COALESCE(wg.trend_30_days, 0),
               COALESCE(wg.occurrence_count, 0),
               wg.avg_cpl_when_occurs
        FROM weakness_graph wg
        JOIN concepts c ON c.code = wg.concept_code
        WHERE wg.player_id = %s AND wg.status IN ('active', 'improving')
          AND wg.concept_code NOT IN ('3.4.2', '3.3.6')
        ORDER BY COALESCE(wg.occurrence_count, 0) DESC
        LIMIT 15
    """, (player_id,))
    wg_rows = cur.fetchall()
    if not wg_rows:
        cur.close()
        return []

    codes = [r[0] for r in wg_rows]

    # Study subtypes — single query
    cur.execute("""
        SELECT concept_code, study_subtype
        FROM concept_study_mapping
        WHERE (elo_bracket_min IS NULL OR elo_bracket_min <= %s)
          AND (elo_bracket_max IS NULL OR elo_bracket_max >= %s)
        ORDER BY effectiveness_score DESC
    """, (player_elo, player_elo))
    subtypes_map: dict[str, str] = {}
    for code, subtype in cur.fetchall():
        if code not in subtypes_map:
            subtypes_map[code] = subtype

    # Examples + breakdown — single batched query
    cur.execute("""
        WITH concept_ids AS (
            SELECT id, code FROM concepts WHERE code = ANY(%s)
        ),
        mc_filtered AS (
            SELECT mc.move_id, ci.code
            FROM concept_ids ci
            JOIN move_concepts mc ON mc.concept_id = ci.id
            WHERE mc.is_primary_cause = TRUE
        ),
        with_game AS (
            SELECT mcf.code, m.game_id, m.id AS move_id, m.weakness_type
            FROM mc_filtered mcf
            JOIN moves m ON m.id  = mcf.move_id
            JOIN games g ON g.id  = m.game_id
            WHERE g.player_id = %s
        ),
        per_game AS (
            SELECT DISTINCT ON (code, game_id)
                   code, game_id, move_id, weakness_type
            FROM with_game
            ORDER BY code, game_id DESC
        )
        SELECT code,
               array_agg(game_id ORDER BY game_id DESC) AS game_ids,
               array_agg(move_id ORDER BY game_id DESC) AS move_ids,
               COUNT(*) FILTER (WHERE weakness_type = 'personal') AS personal_count,
               COUNT(*) FILTER (WHERE weakness_type = 'bracket')  AS bracket_count
        FROM per_game
        GROUP BY code
    """, (codes, player_id))

    batch: dict[str, dict] = {}
    for row in cur.fetchall():
        code, game_ids, move_ids, personal, bracket = row
        batch[code] = {
            'game_ids':  (game_ids or [])[:3],
            'move_ids':  (move_ids or [])[:3],
            'personal':  personal or 0,
            'bracket':   bracket or 0,
        }

    cur.close()

    result = []
    for rank, row in enumerate(wg_rows, 1):
        (code, name, occ_rate, elo_impact, efficiency,
         study_mod, mastery, status, trend_30, occ_count, avg_cpl) = row

        b = batch.get(code, {})
        personal_count = b.get('personal', 0)
        bracket_count  = b.get('bracket', 0)
        total_w = personal_count + bracket_count
        breakdown = WeaknessTypeSplit(
            personal_count=personal_count,
            bracket_count=bracket_count,
            personal_rate=round(personal_count / total_w, 3) if total_w else 0.0,
            bracket_rate=round(bracket_count  / total_w, 3) if total_w else 0.0,
        ) if total_w else None

        trend_lbl = ('improving' if (trend_30 or 0) > 0.10
                     else 'worsening' if (trend_30 or 0) < -0.10 else 'stable')

        pct_games = min(round(occ_count / total_games * 100, 1), 100.0) if total_games else 0.0
        avg_pawns = round(avg_cpl / 100, 1) if avg_cpl is not None else None

        result.append(PrescriptionItem(
            rank=rank, concept_code=code, concept_name=name,
            occurrence_count=occ_count,
            occurrence_rate=occ_rate or 0,
            pct_games_affected=pct_games,
            avg_pawns_lost=avg_pawns,
            total_games=total_games,
            estimated_elo_impact=elo_impact or 0,
            study_efficiency=efficiency or 0, study_module=study_mod,
            study_subtype=subtypes_map.get(code),
            example_game_ids=b.get('game_ids', []),
            example_move_ids=b.get('move_ids', []),
            mastery_score=mastery, status=status,
            trend_label=trend_lbl,
            weakness_type_breakdown=breakdown,
        ))

    return result


@router.get("/{player_id}/opening-gaps", response_model=list[OpeningGap])
def get_opening_gaps(player_id: int, db: Db):
    cur = db.cursor()
    try:
        cur.execute("""
            SELECT eco, opening_name, gap_score, games_seen,
                   avg_time_vs_expected, deviation_count
            FROM opening_prep_gaps
            WHERE player_id = %s AND gap_score > 0.3
            ORDER BY gap_score DESC
            LIMIT 20
        """, (player_id,))
        rows = cur.fetchall()
        cur.close()
        return [
            OpeningGap(
                eco=r[0], opening_name=r[1], gap_score=r[2],
                games_seen=r[3] or 0, avg_time_vs_expected=r[4],
                deviation_count=r[5] or 0
            ) for r in rows
        ]
    except Exception:
        cur.close()
        return []


# ── Detail / summary / resolve endpoints ────────────────────────────────────

class WeaknessDetail(BaseModel):
    concept_code: str
    concept_name: str
    status: str
    mastery_score: float
    trend_label: str
    estimated_elo_impact: float | None
    total_game_appearances: int
    total_games: int
    pct_games_affected: float
    loss_rate: float | None
    avg_pawns_lost: float | None
    personal_context: str | None
    monthly_trend: list[dict]
    instruction: str | None
    why_it_works: str | None
    example: str | None
    recent_examples: list[dict]


@router.get("/{player_id}/weakness/{code}/detail", response_model=WeaknessDetail)
def get_weakness_detail(player_id: int, code: str, db: Db):
    cur = db.cursor()

    # Core weakness_graph row (includes avg_cpl_when_occurs)
    cur.execute("""
        SELECT c.name,
               COALESCE(wg.status, 'active'),
               COALESCE(wg.mastery_score, 0),
               COALESCE(wg.trend_30_days, 0),
               COALESCE(wg.occurrence_count, 0),
               wg.estimated_elo_impact,
               wg.avg_cpl_when_occurs
        FROM concepts c
        LEFT JOIN weakness_graph wg
               ON wg.concept_code = c.code AND wg.player_id = %s
        WHERE c.code = %s
    """, (player_id, code))
    row = cur.fetchone()
    if not row:
        cur.close()
        raise HTTPException(status_code=404, detail="Concept not found")

    name, status, mastery, trend_30, occ_count, elo_impact, avg_cpl = row
    trend_lbl = ('improving' if (trend_30 or 0) > 0.10
                 else 'worsening' if (trend_30 or 0) < -0.10 else 'stable')
    avg_pawns = round(avg_cpl / 100, 1) if avg_cpl is not None else None

    # Total analyzed games
    cur.execute(
        "SELECT COUNT(*) FROM games WHERE player_id = %s AND analyzed = TRUE",
        (player_id,)
    )
    total_games = int(cur.fetchone()[0] or 0)

    # Unique games where this concept appeared + loss rate
    cur.execute("""
        SELECT COUNT(DISTINCT g.id)                                          AS game_appearances,
               AVG(CASE WHEN g.result = 'loss' THEN 1.0 ELSE 0.0 END)      AS loss_rate
        FROM move_concepts mc
        JOIN concepts      c ON c.id = mc.concept_id AND c.code = %s
        JOIN moves         m ON m.id = mc.move_id
        JOIN games         g ON g.id = m.game_id
        WHERE g.player_id = %s
    """, (code, player_id))
    apps_row = cur.fetchone()
    total_game_appearances = int(apps_row[0] or 0) if apps_row else 0
    loss_rate = float(apps_row[1]) if (apps_row and apps_row[1] is not None) else None

    pct_games = min(round(total_game_appearances / total_games * 100, 1), 100.0) if total_games else 0.0

    # Monthly trend — count of games per month where concept appeared
    cur.execute("""
        SELECT DATE_TRUNC('month', g.played_at)::date AS month,
               COUNT(DISTINCT g.id)                    AS count
        FROM move_concepts mc
        JOIN concepts      c ON c.id = mc.concept_id AND c.code = %s
        JOIN moves         m ON m.id = mc.move_id
        JOIN games         g ON g.id = m.game_id
        WHERE g.player_id = %s AND g.played_at IS NOT NULL
        GROUP BY 1
        ORDER BY 1 DESC
        LIMIT 12
    """, (code, player_id))
    monthly_trend = [
        {'month': str(r[0])[:7], 'count': int(r[1])}
        for r in cur.fetchall()
    ]

    # Instructions
    cur.execute("""
        SELECT instruction, why_it_works, example
        FROM concept_instructions WHERE concept_code = %s LIMIT 1
    """, (code,))
    inst_row = cur.fetchone()
    instruction, why_it_works, example = inst_row if inst_row else (None, None, None)

    # Recent examples with game result
    cur.execute("""
        SELECT g.played_at, g.opening_name, m.centipawn_loss, g.result
        FROM moves         m
        JOIN move_concepts mc ON mc.move_id = m.id
        JOIN concepts      c  ON c.id = mc.concept_id AND c.code = %s
        JOIN games         g  ON g.id = m.game_id
        WHERE g.player_id = %s AND m.centipawn_loss IS NOT NULL
        ORDER BY g.played_at DESC NULLS LAST
        LIMIT 3
    """, (code, player_id))
    recent = [
        {
            'played_at': str(r[0]) if r[0] else None,
            'opening_name': r[1],
            'centipawn_loss': r[2],
            'result': r[3],
        }
        for r in cur.fetchall()
    ]

    cur.close()

    # Build warm personal context string
    personal_ctx = None
    if total_game_appearances > 0:
        loss_pct = round((loss_rate or 0) * 100)
        personal_ctx = (
            f"This pattern appeared in {total_game_appearances} of your games — "
            f"about {pct_games:.1f}% of all your analyzed games. "
            f"When it came up, you lost {loss_pct}% of those games."
        )

    return WeaknessDetail(
        concept_code=code, concept_name=name,
        status=status, mastery_score=mastery, trend_label=trend_lbl,
        estimated_elo_impact=round(elo_impact, 1) if elo_impact is not None else None,
        total_game_appearances=total_game_appearances,
        total_games=total_games,
        pct_games_affected=pct_games,
        loss_rate=round(loss_rate, 4) if loss_rate is not None else None,
        avg_pawns_lost=avg_pawns,
        personal_context=personal_ctx,
        monthly_trend=monthly_trend,
        instruction=instruction, why_it_works=why_it_works, example=example,
        recent_examples=recent,
    )


@router.post("/{player_id}/weakness/{code}/resolve")
def resolve_weakness(player_id: int, code: str, db: Db):
    cur = db.cursor()
    cur.execute("""
        UPDATE weakness_graph SET status = 'resolved'
        WHERE player_id = %s AND concept_code = %s
    """, (player_id, code))
    db.commit()
    cur.close()
    return {"ok": True}


class MasterySummary(BaseModel):
    active_count: int
    improving_count: int
    resolved_count: int
    top_priority: list[str]


@router.get("/{player_id}/mastery-summary", response_model=MasterySummary)
def get_mastery_summary(player_id: int, db: Db):
    cur = db.cursor()
    cur.execute("""
        SELECT status, COUNT(*), array_agg(concept_code ORDER BY COALESCE(study_efficiency,0) DESC)
        FROM weakness_graph WHERE player_id = %s
        GROUP BY status
    """, (player_id,))
    rows = cur.fetchall()
    cur.close()

    counts = {'active': 0, 'improving': 0, 'resolved': 0}
    top_codes: list[str] = []
    for status, cnt, codes in rows:
        if status in counts:
            counts[status] = cnt
        if status in ('active', 'improving') and not top_codes:
            top_codes = (codes or [])[:5]

    return MasterySummary(
        active_count=counts['active'],
        improving_count=counts['improving'],
        resolved_count=counts['resolved'],
        top_priority=top_codes,
    )


class AvgMoveTime(BaseModel):
    opening_ms: float | None
    middlegame_ms: float | None
    endgame_ms: float | None
    overall_ms: float | None


@router.get("/{player_id}/avg-move-time", response_model=AvgMoveTime)
def get_avg_move_time(player_id: int, db: Db):
    cur = db.cursor()
    cur.execute("""
        SELECT
            AVG(time_spent_ms) FILTER (WHERE move_number <= 15)                    AS opening_ms,
            AVG(time_spent_ms) FILTER (WHERE move_number BETWEEN 16 AND 40)        AS mid_ms,
            AVG(time_spent_ms) FILTER (WHERE move_number > 40)                     AS end_ms,
            AVG(time_spent_ms)                                                      AS overall_ms
        FROM moves m
        JOIN games g ON g.id = m.game_id
        WHERE g.player_id = %s AND m.time_spent_ms IS NOT NULL AND m.time_spent_ms > 0
    """, (player_id,))
    row = cur.fetchone()
    cur.close()
    if not row:
        return AvgMoveTime(opening_ms=None, middlegame_ms=None, endgame_ms=None, overall_ms=None)
    return AvgMoveTime(
        opening_ms=round(row[0], 1) if row[0] else None,
        middlegame_ms=round(row[1], 1) if row[1] else None,
        endgame_ms=round(row[2], 1) if row[2] else None,
        overall_ms=round(row[3], 1) if row[3] else None,
    )
