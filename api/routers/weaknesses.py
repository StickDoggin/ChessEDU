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
    occurrence_rate: float
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

    cur.execute(
        "SELECT game_type, current_elo FROM player_ratings WHERE player_id = %s",
        (player_id,)
    )
    elo_rows = dict(cur.fetchall())
    player_elo = (elo_rows.get('blitz') or elo_rows.get('rapid')
                  or next(iter(elo_rows.values()), 1500))

    cur.execute("""
        SELECT wg.concept_code, c.name,
               wg.occurrence_rate, wg.estimated_elo_impact,
               wg.study_efficiency, wg.primary_study_module,
               COALESCE(wg.mastery_score, 0), wg.status,
               COALESCE(wg.trend_30_days, 0)
        FROM weakness_graph wg
        JOIN concepts c ON c.code = wg.concept_code
        WHERE wg.player_id = %s AND wg.status IN ('active', 'improving')
        ORDER BY COALESCE(wg.study_efficiency, 0) DESC
        LIMIT 10
    """, (player_id,))
    wg_rows = cur.fetchall()

    # Best study subtype per concept within Elo bracket
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

    result = []
    for rank, row in enumerate(wg_rows, 1):
        (code, name, occ_rate, elo_impact, efficiency,
         study_mod, mastery, status, trend_30) = row

        # Example games/moves
        cur.execute("""
            SELECT DISTINCT ON (m.game_id) m.game_id, m.id
            FROM move_concepts mc
            JOIN moves m    ON m.id  = mc.move_id
            JOIN concepts c ON c.id  = mc.concept_id
            JOIN games g    ON g.id  = m.game_id
            WHERE g.player_id = %s AND c.code = %s AND mc.is_primary_cause = TRUE
            ORDER BY m.game_id DESC
            LIMIT 3
        """, (player_id, code))
        examples = cur.fetchall()

        # Personal vs bracket breakdown
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE m.weakness_type = 'personal') AS personal,
                COUNT(*) FILTER (WHERE m.weakness_type = 'bracket')  AS bracket
            FROM move_concepts mc
            JOIN moves m    ON m.id  = mc.move_id
            JOIN concepts c ON c.id  = mc.concept_id
            JOIN games g    ON g.id  = m.game_id
            WHERE g.player_id = %s AND c.code = %s AND mc.is_primary_cause = TRUE
        """, (player_id, code))
        wb = cur.fetchone()
        personal_count = wb[0] or 0
        bracket_count  = wb[1] or 0
        total_w        = personal_count + bracket_count
        breakdown = WeaknessTypeSplit(
            personal_count=personal_count,
            bracket_count=bracket_count,
            personal_rate=round(personal_count / total_w, 3) if total_w else 0.0,
            bracket_rate=round(bracket_count / total_w, 3) if total_w else 0.0,
        ) if total_w else None

        trend_lbl = ('improving' if (trend_30 or 0) > 0.10
                     else 'worsening' if (trend_30 or 0) < -0.10 else 'stable')

        result.append(PrescriptionItem(
            rank=rank, concept_code=code, concept_name=name,
            occurrence_rate=occ_rate or 0, estimated_elo_impact=elo_impact or 0,
            study_efficiency=efficiency or 0, study_module=study_mod,
            study_subtype=subtypes_map.get(code),
            example_game_ids=[r[0] for r in examples],
            example_move_ids=[r[1] for r in examples],
            mastery_score=mastery, status=status,
            trend_label=trend_lbl,
            weakness_type_breakdown=breakdown
        ))

    cur.close()
    return result


@router.get("/{player_id}/opening-gaps", response_model=list[OpeningGap])
def get_opening_gaps(player_id: int, db: Db):
    cur = db.cursor()

    # Opening prep gaps are stored as weakness_graph entries with specific ECO concept codes
    # Also check opening_prep_gaps table if it exists
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
