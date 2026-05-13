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

    # Verify player exists
    cur.execute("SELECT username FROM players WHERE id = %s", (player_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Player not found")
    username = row[0]

    # Ratings
    cur.execute(
        "SELECT game_type, current_elo FROM player_ratings WHERE player_id = %s",
        (player_id,)
    )
    ratings = [Rating(game_type=r[0], current_elo=r[1]) for r in cur.fetchall()]

    # Single CTE: games count + top weaknesses + totals + tilt + fatigue
    cur.execute("""
        WITH
        g_count AS (
            SELECT COUNT(*) AS n
            FROM games
            WHERE player_id = %s AND analyzed = TRUE
        ),
        wg_active AS (
            SELECT wg.concept_code, c.name,
                   wg.occurrence_rate, wg.estimated_elo_impact,
                   wg.study_efficiency, wg.primary_study_module,
                   COALESCE(wg.mastery_score, 0) AS mastery_score,
                   wg.status,
                   COALESCE(wg.estimated_elo_impact,  0) AS elo_i,
                   COALESCE(wg.estimated_study_hours, 0) AS hrs_i,
                   ROW_NUMBER() OVER (ORDER BY COALESCE(wg.study_efficiency,0) DESC) AS rn
            FROM weakness_graph wg
            JOIN concepts c ON c.code = wg.concept_code
            WHERE wg.player_id = %s AND wg.status IN ('active', 'improving')
        ),
        totals AS (
            SELECT COALESCE(SUM(elo_i), 0) AS total_elo,
                   COALESCE(SUM(hrs_i), 0) AS total_hrs
            FROM wg_active
        ),
        tilt AS (
            SELECT occurrence_rate FROM weakness_graph
            WHERE player_id = %s AND concept_code = '7.3.1' AND game_type = 'session'
            LIMIT 1
        ),
        fatigue AS (
            SELECT occurrence_rate FROM weakness_graph
            WHERE player_id = %s AND concept_code = '7.1.1' AND game_type = 'session'
            LIMIT 1
        )
        SELECT
            (SELECT n          FROM g_count),
            (SELECT total_elo  FROM totals),
            (SELECT total_hrs  FROM totals),
            (SELECT occurrence_rate FROM tilt),
            (SELECT occurrence_rate FROM fatigue),
            wa.concept_code, wa.name, wa.occurrence_rate, wa.estimated_elo_impact,
            wa.study_efficiency, wa.primary_study_module, wa.mastery_score, wa.status
        FROM wg_active wa
        WHERE wa.rn <= 5
        ORDER BY wa.rn
    """, (player_id, player_id, player_id, player_id))

    rows = cur.fetchall()
    cur.close()

    if not rows:
        # No weakness data yet — return minimal profile
        return PlayerProfile(
            player_id=player_id, username=username, ratings=ratings,
            games_analyzed=0, top_weaknesses=[],
            estimated_elo_gain=0.0, study_hours_needed=0.0,
            tilt_rate=None, fatigue_rate=None,
        )

    games_analyzed  = int(rows[0][0] or 0)
    total_elo       = float(rows[0][1] or 0)
    total_hrs       = float(rows[0][2] or 0)
    tilt_rate       = float(rows[0][3]) if rows[0][3] is not None else None
    fatigue_rate    = float(rows[0][4]) if rows[0][4] is not None else None

    top_weaknesses = [
        WeaknessEntry(
            concept_code=r[5], concept_name=r[6],
            occurrence_rate=r[7] or 0, estimated_elo_impact=r[8] or 0,
            study_efficiency=r[9] or 0, primary_study_module=r[10],
            mastery_score=r[11], status=r[12],
        ) for r in rows
    ]

    return PlayerProfile(
        player_id=player_id, username=username, ratings=ratings,
        games_analyzed=games_analyzed, top_weaknesses=top_weaknesses,
        estimated_elo_gain=total_elo, study_hours_needed=total_hrs,
        tilt_rate=tilt_rate, fatigue_rate=fatigue_rate,
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
            last_occurred=str(r[11]) if r[11] else None,
        ) for r in rows
    ]
