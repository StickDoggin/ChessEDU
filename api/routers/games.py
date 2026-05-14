"""Game list and per-game move endpoints."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import psycopg
from api.dependencies import get_db

router = APIRouter(prefix="/players", tags=["games"])
Db = Annotated[psycopg.Connection, Depends(get_db)]


class GameSummary(BaseModel):
    game_id: int
    played_at: str | None
    result: str | None
    result_type: str | None
    game_type: str | None
    time_control: str | None
    player_elo: int | None
    opponent_elo: int | None
    opening_eco: str | None
    opening_name: str | None
    accuracy_pct: float | None
    avg_maia_win_prob: float | None
    analyzed: bool


class MoveDetail(BaseModel):
    move_id: int
    move_number: int
    color: str | None
    san: str | None
    uci: str | None
    fen_before: str | None
    fen_after: str | None
    eval_before: int | None
    eval_after: int | None
    centipawn_loss: int | None
    mistake_class: str | None
    best_move_san: str | None
    best_move_uci: str | None
    maia_probability: float | None
    maia_win_prob: float | None
    weakness_type: str | None
    phase: str | None
    time_pressure: str | None
    pattern_tags: list[str] | None


@router.get("/{player_id}/games", response_model=list[GameSummary])
def get_games(
    player_id: int, db: Db,
    limit: int = 20,
    offset: int = 0,
    game_type: str | None = None,
):
    cur = db.cursor()
    gt_clause = "AND game_type = %s" if game_type else ""
    gt_arg    = (game_type,) if game_type else ()

    cur.execute(f"""
        SELECT id, played_at, result, result_type, game_type, time_control,
               player_elo, opponent_elo, opening_eco, opening_name,
               accuracy_pct, avg_maia_win_prob, analyzed
        FROM games
        WHERE player_id = %s {gt_clause}
        ORDER BY played_at DESC NULLS LAST
        LIMIT %s OFFSET %s
    """, (player_id,) + gt_arg + (limit, offset))

    rows = cur.fetchall()
    cur.close()
    return [
        GameSummary(
            game_id=r[0], played_at=str(r[1]) if r[1] else None,
            result=r[2], result_type=r[3], game_type=r[4],
            time_control=r[5], player_elo=r[6], opponent_elo=r[7],
            opening_eco=r[8], opening_name=r[9],
            accuracy_pct=r[10], avg_maia_win_prob=r[11],
            analyzed=r[12] or False
        ) for r in rows
    ]


@router.get("/{player_id}/games/{game_id}", response_model=GameSummary)
def get_game(player_id: int, game_id: int, db: Db):
    cur = db.cursor()
    cur.execute("""
        SELECT id, played_at, result, result_type, game_type, time_control,
               player_elo, opponent_elo, opening_eco, opening_name,
               accuracy_pct, avg_maia_win_prob, analyzed
        FROM games WHERE id = %s AND player_id = %s
    """, (game_id, player_id))
    row = cur.fetchone()
    cur.close()
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")
    return GameSummary(
        game_id=row[0], played_at=str(row[1]) if row[1] else None,
        result=row[2], result_type=row[3], game_type=row[4],
        time_control=row[5], player_elo=row[6], opponent_elo=row[7],
        opening_eco=row[8], opening_name=row[9],
        accuracy_pct=row[10], avg_maia_win_prob=row[11],
        analyzed=row[12] or False
    )


@router.get("/{player_id}/games/{game_id}/moves", response_model=list[MoveDetail])
def get_game_moves(player_id: int, game_id: int, db: Db):
    cur = db.cursor()

    cur.execute(
        "SELECT player_id FROM games WHERE id = %s",
        (game_id,)
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Game not found")
    if row[0] != player_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    cur.execute("""
        SELECT m.id, m.move_number, m.color, m.san, m.uci,
               m.fen_before, m.fen_after,
               m.eval_before, m.eval_after, m.centipawn_loss,
               m.mistake_class, m.best_move_san, m.best_move_uci,
               m.maia_probability, m.maia_win_prob, m.weakness_type,
               m.phase, m.time_pressure, m.pattern_tags
        FROM moves m
        WHERE m.game_id = %s
        ORDER BY m.move_number, m.color
    """, (game_id,))

    rows = cur.fetchall()
    cur.close()
    return [
        MoveDetail(
            move_id=r[0], move_number=r[1], color=r[2],
            san=r[3], uci=r[4], fen_before=r[5], fen_after=r[6],
            eval_before=r[7], eval_after=r[8], centipawn_loss=r[9],
            mistake_class=r[10], best_move_san=r[11], best_move_uci=r[12],
            maia_probability=r[13], maia_win_prob=r[14], weakness_type=r[15],
            phase=r[16], time_pressure=r[17],
            pattern_tags=list(r[18]) if r[18] else None
        ) for r in rows
    ]
