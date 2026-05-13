"""Player profile and weakness-graph endpoints."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import psycopg
from api.dependencies import get_db

router = APIRouter(prefix="/players", tags=["players"])
Db = Annotated[psycopg.Connection, Depends(get_db)]


class Rating(BaseModel):
    game_type: str
    current_elo: int


class WeaknessEntry(BaseModel):
    concept_code: str
    concept_name: str
    occurrence_rate: float
    estimated_elo_impact: float
    study_efficiency: float
    primary_study_module: str | None
    mastery_score: float
    status: str


class PlayerProfile(BaseModel):
    player_id: int
    username: str
    ratings: list[Rating]
    games_analyzed: int
    top_weaknesses: list[WeaknessEntry]
    estimated_elo_gain: float
    study_hours_needed: float
    tilt_rate: float | None
    fatigue_rate: float | None


class WeaknessGraphEntry(BaseModel):
    concept_code: str
    concept_name: str
    game_type: str
    occurrence_count: int
    occurrence_rate: float
    avg_cpl_when_occurs: float | None
    estimated_elo_impact: float
    study_efficiency: float | None
    primary_study_module: str | None
    mastery_score: float
    status: str
    last_occurred: str | None


@router.get("/{player_id}/profile", response_model=PlayerProfile)
def get_player_profile(player_id: int, db: Db):
    cur = db.cursor()

    cur.execute("SELECT username FROM players WHERE id = %s", (player_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Player not found")
    username = row[0]

    cur.execute(
        "SELECT game_type, current_elo FROM player_ratings WHERE player_id = %s",
        (player_id,)
    )
    ratings = [Rating(game_type=r[0], current_elo=r[1]) for r in cur.fetchall()]

    cur.execute(
        "SELECT COUNT(*) FROM games WHERE player_id = %s AND analyzed = TRUE",
        (player_id,)
    )
    games_analyzed = cur.fetchone()[0]

    cur.execute("""
        SELECT wg.concept_code, c.name,
               wg.occurrence_rate, wg.estimated_elo_impact,
               wg.study_efficiency, wg.primary_study_module,
               COALESCE(wg.mastery_score, 0), wg.status
        FROM weakness_graph wg
        JOIN concepts c ON c.code = wg.concept_code
        WHERE wg.player_id = %s AND wg.status IN ('active', 'improving')
        ORDER BY COALESCE(wg.study_efficiency, 0) DESC
        LIMIT 5
    """, (player_id,))
    top_weaknesses = [
        WeaknessEntry(
            concept_code=r[0], concept_name=r[1],
            occurrence_rate=r[2] or 0, estimated_elo_impact=r[3] or 0,
            study_efficiency=r[4] or 0, primary_study_module=r[5],
            mastery_score=r[6], status=r[7]
        ) for r in cur.fetchall()
    ]

    cur.execute("""
        SELECT COALESCE(SUM(estimated_elo_impact), 0),
               COALESCE(SUM(estimated_study_hours), 0)
        FROM weakness_graph
        WHERE player_id = %s AND status IN ('active', 'improving')
    """, (player_id,))
    elo_gain, study_hours = cur.fetchone()

    cur.execute("""
        SELECT occurrence_rate, status
        FROM weakness_graph
        WHERE player_id = %s AND concept_code = '7.3.1' AND game_type = 'session'
    """, (player_id,))
    tilt_row = cur.fetchone()
    tilt_rate = tilt_row[0] if tilt_row else None

    cur.execute("""
        SELECT occurrence_rate
        FROM weakness_graph
        WHERE player_id = %s AND concept_code = '7.1.1' AND game_type = 'session'
    """, (player_id,))
    fat_row = cur.fetchone()
    fatigue_rate = fat_row[0] if fat_row else None

    cur.close()
    return PlayerProfile(
        player_id=player_id, username=username, ratings=ratings,
        games_analyzed=games_analyzed, top_weaknesses=top_weaknesses,
        estimated_elo_gain=float(elo_gain or 0),
        study_hours_needed=float(study_hours or 0),
        tilt_rate=tilt_rate, fatigue_rate=fatigue_rate
    )


@router.get("/{player_id}/weakness-graph", response_model=list[WeaknessGraphEntry])
def get_weakness_graph(player_id: int, db: Db):
    cur = db.cursor()
    cur.execute("""
        SELECT wg.concept_code, c.name, wg.game_type,
               wg.occurrence_count, wg.occurrence_rate,
               wg.avg_cpl_when_occurs, wg.estimated_elo_impact,
               wg.study_efficiency, wg.primary_study_module,
               COALESCE(wg.mastery_score, 0), wg.status,
               wg.last_occurred
        FROM weakness_graph wg
        JOIN concepts c ON c.code = wg.concept_code
        WHERE wg.player_id = %s
        ORDER BY COALESCE(wg.study_efficiency, 0) DESC
    """, (player_id,))
    rows = cur.fetchall()
    cur.close()
    return [
        WeaknessGraphEntry(
            concept_code=r[0], concept_name=r[1], game_type=r[2],
            occurrence_count=r[3] or 0, occurrence_rate=r[4] or 0,
            avg_cpl_when_occurs=r[5], estimated_elo_impact=r[6] or 0,
            study_efficiency=r[7], primary_study_module=r[8],
            mastery_score=r[9], status=r[10],
            last_occurred=str(r[11]) if r[11] else None
        ) for r in rows
    ]
