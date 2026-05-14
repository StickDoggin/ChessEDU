"""Drill session and attempt endpoints."""
from datetime import date
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import psycopg
from api.dependencies import get_db

router = APIRouter(prefix="/players", tags=["drills"])
Db = Annotated[psycopg.Connection, Depends(get_db)]


DEPTH_ADVANCE_STREAK = 5   # consecutive correct at ceiling before advancing

class DrillPosition(BaseModel):
    drill_id: int
    concept_code: str
    concept_name: str
    fen: str
    correct_move: str
    correct_move_san: str | None
    difficulty: float
    next_review: str
    review_count: int
    source_move_id: int | None
    solution_depth: int | None = None
    visualization_mode: bool = False


class DrillSession(BaseModel):
    player_id: int
    concept_codes: list[str]
    positions: list[DrillPosition]
    session_minutes: int


class DrillAttemptRequest(BaseModel):
    drill_id: int
    was_correct: bool
    time_spent_ms: int
    move_played: str | None = None
    solution_depth: int | None = None   # for 3.3.6.c depth tracking


class DrillAttemptResponse(BaseModel):
    drill_id: int
    was_correct: bool
    next_review_date: str
    new_interval_days: int
    new_ease_factor: float
    mastery_score_delta: float
    depth_ceiling_advanced: bool = False


@router.get("/{player_id}/drill-session", response_model=DrillSession)
def get_drill_session(
    player_id: int, db: Db,
    concept_codes: str | None = None,
    length_mins: int = 10,
):
    cur = db.cursor()

    codes = [c.strip() for c in concept_codes.split(',')] if concept_codes else []

    # Determine puzzle_rating range for 3.3.6.c progressive mode
    # puzzle_rating is the depth proxy: ceiling=3 → rating 2000-2800
    depth_clause = ""
    depth_args: tuple = ()
    if codes and '3.3.6.c' in codes:
        cur.execute("""
            SELECT depth_ceiling FROM player_calculation_profile
            WHERE player_id = %s AND game_type = 'rapid'
        """, (player_id,))
        pr = cur.fetchone()
        ceiling = int(pr[0]) if pr else 3
        rating_lo = 800 + ceiling * 400
        rating_hi = rating_lo + 3 * 400   # 3 depth levels wide
        depth_clause = "AND (dp.puzzle_rating BETWEEN %s AND %s OR dp.puzzle_rating IS NULL OR dp.concept_code <> '3.3.6.c')"
        depth_args = (rating_lo, rating_hi)

    limit = length_mins * 3
    own_limit  = max(1, round(limit * 0.7))   # 70% from own-game positions
    lich_limit = limit - own_limit             # 30% from Lichess pool

    # When no concept codes given, pull top weakness codes that actually have
    # drill positions (filters out psychological codes like 7.3.1/7.1.1 that
    # have no drill positions, avoiding slow 0-result scans).
    if not codes:
        cur.execute("""
            SELECT wg.concept_code FROM weakness_graph wg
            WHERE wg.player_id = %s AND wg.status IN ('active', 'improving')
              AND EXISTS (
                SELECT 1 FROM drill_positions dp
                WHERE dp.concept_code = wg.concept_code
              )
            ORDER BY COALESCE(wg.study_efficiency, 0) DESC
            LIMIT 5
        """, (player_id,))
        codes = [r[0] for r in cur.fetchall()]

    # UNION ALL: split own-game and Lichess arms so each uses its own index.
    # (OR player_id IS NULL on a single query forces a 5M-row seq scan.)
    # Own arm   → idx_drill_player_concept_review
    # Lichess arm → idx_drill_lichess_review partial index
    # Hard limits on each arm implement the 70/30 own/Lichess mix.
    cur.execute(f"""
        SELECT id, concept_code, name, fen, correct_move, correct_move_san,
               difficulty, next_review, review_count, source_move_id,
               solution_depth, puzzle_rating
        FROM (
            (
                SELECT dp.id, dp.concept_code, c.name, dp.fen,
                       dp.correct_move, dp.correct_move_san, dp.difficulty,
                       dp.next_review, dp.review_count, dp.source_move_id,
                       dp.solution_depth, dp.puzzle_rating
                FROM drill_positions dp
                JOIN concepts c ON c.code = dp.concept_code
                WHERE dp.player_id = %s
                  AND dp.concept_code = ANY(%s)
                  AND dp.next_review <= %s
                ORDER BY dp.next_review ASC, dp.id ASC
                LIMIT %s
            )
            UNION ALL
            (
                SELECT dp.id, dp.concept_code, c.name, dp.fen,
                       dp.correct_move, dp.correct_move_san, dp.difficulty,
                       dp.next_review, dp.review_count, dp.source_move_id,
                       dp.solution_depth, dp.puzzle_rating
                FROM drill_positions dp TABLESAMPLE SYSTEM(5)
                JOIN concepts c ON c.code = dp.concept_code
                WHERE dp.player_id IS NULL
                  AND dp.concept_code = ANY(%s)
                  AND dp.next_review <= %s
                  {depth_clause}
                LIMIT %s
            )
        ) pool
        ORDER BY RANDOM()
        LIMIT %s
    """, (player_id, codes, date.today(), own_limit,
          codes, date.today()) + depth_args + (lich_limit, limit))

    rows = cur.fetchall()
    cur.close()

    positions = [
        DrillPosition(
            drill_id=r[0], concept_code=r[1], concept_name=r[2],
            fen=r[3], correct_move=r[4], correct_move_san=r[5],
            difficulty=r[6] or 0.5, next_review=str(r[7]),
            review_count=r[8] or 0, source_move_id=r[9],
            solution_depth=r[10],
            visualization_mode=(r[1] == '3.3.6.c' and (r[11] or 0) >= 2000)
        ) for r in rows
    ]

    used_codes = list({p.concept_code for p in positions})
    return DrillSession(
        player_id=player_id, concept_codes=used_codes,
        positions=positions, session_minutes=length_mins
    )


@router.post("/{player_id}/drill-attempt", response_model=DrillAttemptResponse)
def record_drill_attempt(player_id: int, body: DrillAttemptRequest, db: Db):
    cur = db.cursor()

    cur.execute("""
        SELECT ease_factor, interval_days, review_count, concept_code
        FROM drill_positions WHERE id = %s AND player_id = %s
    """, (body.drill_id, player_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Drill not found")

    ease, interval, count, code = row
    ease     = ease or 2.5
    interval = interval or 1
    count    = count or 0

    # SM-2 update
    if body.was_correct:
        if count == 0:
            new_interval = 1
        elif count == 1:
            new_interval = 6
        else:
            new_interval = round(interval * ease)
        new_ease = max(1.3, ease + 0.1)
    else:
        new_interval = 1
        new_ease = max(1.3, ease - 0.20)

    from datetime import timedelta
    next_review = date.today() + timedelta(days=new_interval)
    last_result = 'correct' if body.was_correct else 'incorrect'

    cur.execute("""
        UPDATE drill_positions
        SET ease_factor = %s, interval_days = %s,
            next_review = %s, review_count = review_count + 1,
            last_result = %s
        WHERE id = %s
    """, (new_ease, new_interval, next_review, last_result, body.drill_id))

    cur.execute("""
        INSERT INTO drill_attempts
            (drill_id, player_id, move_played, was_correct,
             time_spent_ms, new_interval, new_ease_factor)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (body.drill_id, player_id, body.move_played, body.was_correct,
          body.time_spent_ms, new_interval, new_ease))

    # Mastery delta preview (not persisted here — update_mastery.py does the full pass)
    cur.execute("""
        SELECT COALESCE(mastery_score, 0) FROM weakness_graph
        WHERE player_id = %s AND concept_code = %s
        LIMIT 1
    """, (player_id, code))
    mrow = cur.fetchone()
    old_mastery = float(mrow[0]) if mrow else 0.0
    mastery_delta = 0.10 if body.was_correct else -0.05

    # 3.3.6.c: advance depth_ceiling after DEPTH_ADVANCE_STREAK correct at ceiling
    depth_ceiling_advanced = False
    if code == '3.3.6.c' and body.was_correct and body.solution_depth is not None:
        cur.execute("""
            SELECT depth_ceiling FROM player_calculation_profile
            WHERE player_id = %s AND game_type = 'rapid'
        """, (player_id,))
        pr = cur.fetchone()
        if pr:
            ceiling = int(pr[0])
            if body.solution_depth >= ceiling:
                # Count recent correct attempts at or above ceiling
                cur.execute("""
                    SELECT COUNT(*) FROM drill_attempts da
                    JOIN drill_positions dp ON dp.id = da.drill_id
                    WHERE da.player_id = %s
                      AND dp.concept_code = '3.3.6.c'
                      AND da.was_correct = TRUE
                      AND da.attempted_at >= NOW() - INTERVAL '7 days'
                """, (player_id,))
                streak = cur.fetchone()[0] or 0
                if streak >= DEPTH_ADVANCE_STREAK:
                    cur.execute("""
                        UPDATE player_calculation_profile
                        SET depth_ceiling = depth_ceiling + 1,
                            sessions_count = sessions_count + 1,
                            updated_at = NOW()
                        WHERE player_id = %s AND game_type = 'rapid'
                    """, (player_id,))
                    depth_ceiling_advanced = True

    # Update avg/max depth solved in profile
    if code == '3.3.6.c' and body.was_correct and body.solution_depth is not None:
        cur.execute("""
            UPDATE player_calculation_profile
            SET max_depth_solved = GREATEST(max_depth_solved, %s),
                avg_depth_solved = (avg_depth_solved * sessions_count + %s)
                                   / NULLIF(sessions_count + 1, 0),
                updated_at = NOW()
            WHERE player_id = %s AND game_type = 'rapid'
        """, (body.solution_depth, body.solution_depth, player_id))

    db.commit()
    cur.close()

    return DrillAttemptResponse(
        drill_id=body.drill_id,
        was_correct=body.was_correct,
        next_review_date=str(next_review),
        new_interval_days=new_interval,
        new_ease_factor=round(new_ease, 2),
        mastery_score_delta=mastery_delta,
        depth_ceiling_advanced=depth_ceiling_advanced,
    )


@router.get("/{player_id}/drill/{drill_id}/explain")
def explain_drill(player_id: int, drill_id: int, db: Db):
    """Return a cached AI explanation for a drill position, generating if needed."""
    import json

    cur = db.cursor()

    # Create cache table on first use
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drill_explanations (
            drill_id      INTEGER PRIMARY KEY REFERENCES drill_positions(id),
            idea          TEXT,
            problem       TEXT,
            solution      TEXT,
            pay_attention JSONB,
            generated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)
    db.commit()

    # Return cached explanation if available
    cur.execute(
        "SELECT idea, problem, solution, pay_attention FROM drill_explanations WHERE drill_id = %s",
        (drill_id,)
    )
    cached = cur.fetchone()
    if cached:
        cur.close()
        return {
            'idea': cached[0], 'problem': cached[1],
            'solution': cached[2], 'pay_attention': cached[3] or [],
        }

    # Fetch position + concept name
    cur.execute("""
        SELECT dp.fen, dp.correct_move, dp.correct_move_san, c.name
        FROM drill_positions dp
        JOIN concepts c ON c.code = dp.concept_code
        WHERE dp.id = %s
    """, (drill_id,))
    pos = cur.fetchone()
    if not pos:
        cur.close()
        raise HTTPException(status_code=404, detail="Drill not found")

    fen, correct_move, correct_move_san, concept_name = pos
    best_move = correct_move_san or correct_move

    # Call Claude API
    try:
        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=400,
            system=(
                "You are a chess coach. Give specific position explanations naming actual "
                "pieces and squares. 2 sentences max per section. Return only JSON."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"FEN: {fen}\nBest move: {best_move}\nConcept: {concept_name}\n\n"
                    "Return JSON:\n"
                    '{"idea": "...", "problem": "...", "solution": "...", '
                    '"pay_attention": ["...", "...", "..."]}'
                ),
            }],
        )

        text = message.content[0].text.strip()
        # Strip markdown fences if present
        if '```' in text:
            parts = text.split('```')
            text = parts[1] if len(parts) > 1 else text
            if text.startswith('json'):
                text = text[4:].strip()

        data = json.loads(text)
        idea          = data.get('idea', '')
        problem       = data.get('problem', '')
        solution      = data.get('solution', '')
        pay_attention = data.get('pay_attention', [])

        cur.execute("""
            INSERT INTO drill_explanations (drill_id, idea, problem, solution, pay_attention)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (drill_id) DO NOTHING
        """, (drill_id, idea, problem, solution, json.dumps(pay_attention)))
        db.commit()
        cur.close()

        return {
            'idea': idea, 'problem': problem,
            'solution': solution, 'pay_attention': pay_attention,
        }

    except ImportError:
        cur.close()
        raise HTTPException(status_code=503, detail="Anthropic package not installed. Run: pip install anthropic")
    except Exception as e:
        cur.close()
        raise HTTPException(status_code=500, detail=f"Explanation failed: {str(e)}")
