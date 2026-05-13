"""
maia_pass.py — Post-processing pass: Maia-2 human accuracy model.

For each player move in the database, computes:
  maia_probability  — P(player_move | position, elo_self, elo_oppo) via Maia-2
  maia_top_move_uci — Maia's most-likely move for this position/rating
  maia_agreement    — True if maia_top_move == player's actual move
  maia_bracket_rank — Rank of player's move in Maia's distribution (1 = most likely)
  maia_win_prob     — Human win probability at player's Elo (0-1, from player's perspective)
  weakness_type     — 'personal' | 'bracket' | NULL
                      personal: CPL >= BLUNDER_CPL and maia_prob < PERSONAL_THRESHOLD
                                (you specifically miss this; others at your Elo find it)
                      bracket:  CPL >= BLUNDER_CPL and maia_prob >= PERSONAL_THRESHOLD
                                (everyone at your Elo misses this; normal for your level)

After processing all moves per game:
  games.avg_maia_win_prob = AVG(maia_win_prob) for that game

Model selection:
  rapid / classical / unknown -> rapid_model
  blitz / bullet              -> blitz_model

Models are downloaded on first run (~200MB each) to ./maia2_models/.

USAGE:
  python maia_pass.py                # process all unprocessed moves
  python maia_pass.py --limit 10     # process first 10 games (for testing)
  python maia_pass.py --player 1     # restrict to player_id=1
"""

import sys
import time
from datetime import timedelta
from db_setup import get_connection

# ── Constants ──────────────────────────────────────────────────────────────────
BATCH_SIZE         = 500    # moves fetched per DB round-trip
BLUNDER_CPL        = 150    # CPL threshold to classify weakness_type
PERSONAL_THRESHOLD = 0.15   # maia_prob below this = 'personal' weakness
MODEL_SAVE_ROOT    = './maia2_models'


def _load_models():
    """Load both rapid and blitz Maia-2 models (downloads weights if needed)."""
    from maia2 import model as maia_model, inference
    print("Loading Maia-2 models (downloading if not cached)...")
    rapid = maia_model.from_pretrained('rapid', device='cpu',
                                       save_root=MODEL_SAVE_ROOT)
    blitz = maia_model.from_pretrained('blitz', device='cpu',
                                       save_root=MODEL_SAVE_ROOT)
    prepared = inference.prepare()
    print("Models ready.")
    return rapid, blitz, prepared


def _select_model(game_type: str, rapid_model, blitz_model):
    """Return the appropriate model for the game type."""
    if game_type in ('blitz', 'bullet'):
        return blitz_model
    return rapid_model  # rapid, classical, unknown


def _weakness_type(cpl, maia_prob) -> str | None:
    """Classify the move as 'personal', 'bracket', or None."""
    if cpl is None or cpl < BLUNDER_CPL:
        return None
    if maia_prob < PERSONAL_THRESHOLD:
        return 'personal'
    return 'bracket'


def _fetch_batch(cur, player_id: int | None, limit_games: int | None) -> list:
    """
    Fetch a batch of unprocessed player moves.
    Returns list of dicts with move and game fields.

    No OFFSET is used: after each batch is committed the processed rows
    have maia_probability IS NOT NULL and vanish from the WHERE clause,
    so the next LIMIT query naturally returns the next fresh batch.
    Using OFFSET here would skip rows equal to the batch size on every
    iteration because the filtered set shrinks after each commit.
    """
    pid_filter   = "AND g.player_id = %s" if player_id else ""
    pid_arg      = (player_id,) if player_id else ()

    # If limit_games set, restrict to first N game IDs
    game_limit_clause = ""
    game_limit_args   = ()
    if limit_games:
        cur.execute(f"""
            SELECT DISTINCT m.game_id
            FROM moves m
            JOIN games g ON g.id = m.game_id
            WHERE m.maia_probability IS NULL
              AND m.fen_before IS NOT NULL
              AND m.uci IS NOT NULL
              AND m.color = g.color
              {pid_filter}
            ORDER BY m.game_id
            LIMIT %s
        """, pid_arg + (limit_games,))
        game_ids = [r[0] for r in cur.fetchall()]
        if not game_ids:
            return []
        game_limit_clause = "AND m.game_id = ANY(%s)"
        game_limit_args   = (game_ids,)

    cur.execute(f"""
        SELECT
            m.id          AS move_id,
            m.game_id,
            m.uci         AS move_uci,
            m.fen_before,
            m.centipawn_loss,
            g.game_type,
            g.player_elo,
            g.opponent_elo
        FROM moves m
        JOIN games g ON g.id = m.game_id
        WHERE m.maia_probability IS NULL
          AND m.fen_before IS NOT NULL
          AND m.uci IS NOT NULL
          AND m.color = g.color
          {pid_filter}
          {game_limit_clause}
        ORDER BY m.game_id, m.id
        LIMIT %s
    """, pid_arg + game_limit_args + (BATCH_SIZE,))

    cols = ('move_id', 'game_id', 'move_uci', 'fen_before',
            'centipawn_loss', 'game_type', 'player_elo', 'opponent_elo')
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _process_move(row: dict, rapid_model, blitz_model, prepared,
                  inference_fn) -> dict:
    """Run Maia-2 inference for one move. Returns fields to write."""
    from maia2.inference import inference_each

    model = _select_model(row['game_type'], rapid_model, blitz_model)
    elo_self = row['player_elo'] or 1500
    elo_oppo = row['opponent_elo'] or 1500

    try:
        move_probs, win_prob = inference_each(
            model, prepared,
            fen=row['fen_before'],
            elo_self=elo_self,
            elo_oppo=elo_oppo,
        )
    except Exception as e:
        # Invalid FEN or other inference error — skip gracefully
        return None

    player_uci = row['move_uci']
    maia_prob  = move_probs.get(player_uci, 0.0)

    # Rank: 1 = Maia's top choice (move_probs is already sorted desc)
    moves_ranked = list(move_probs.keys())
    try:
        rank = moves_ranked.index(player_uci) + 1
    except ValueError:
        rank = len(moves_ranked) + 1  # move not in legal set (rare edge case)

    top_move = moves_ranked[0] if moves_ranked else None
    agreement = (top_move == player_uci) if top_move else False

    w_type = _weakness_type(row['centipawn_loss'], maia_prob)

    return {
        'move_id':         row['move_id'],
        'game_id':         row['game_id'],
        'maia_probability':  round(maia_prob, 4),
        'maia_top_move_uci': top_move,
        'maia_agreement':    agreement,
        'maia_bracket_rank': rank,
        'maia_win_prob':     win_prob,
        'weakness_type':     w_type,
    }


def _flush_moves(cur, results: list) -> int:
    """Batch-update moves with Maia results. Returns number of rows updated."""
    if not results:
        return 0
    for r in results:
        cur.execute("""
            UPDATE moves SET
                maia_probability  = %(maia_probability)s,
                maia_top_move_uci = %(maia_top_move_uci)s,
                maia_agreement    = %(maia_agreement)s,
                maia_bracket_rank = %(maia_bracket_rank)s,
                maia_win_prob     = %(maia_win_prob)s,
                weakness_type     = %(weakness_type)s
            WHERE id = %(move_id)s
        """, r)
    return len(results)


def _update_game_win_prob(cur, game_ids: list) -> None:
    """Update games.avg_maia_win_prob for each finished game."""
    if not game_ids:
        return
    cur.execute("""
        UPDATE games g SET
            avg_maia_win_prob = sub.avg_wp
        FROM (
            SELECT game_id, AVG(maia_win_prob) AS avg_wp
            FROM moves
            WHERE game_id = ANY(%s)
              AND maia_win_prob IS NOT NULL
            GROUP BY game_id
        ) sub
        WHERE g.id = sub.game_id
    """, (game_ids,))


def run(player_id: int | None = None, limit_games: int | None = None):
    """Main processing loop."""
    rapid_model, blitz_model, prepared = _load_models()
    from maia2.inference import inference_each  # noqa: F401 (imported to warm up)

    conn = get_connection()
    cur  = conn.cursor()

    # Total moves to process
    pid_filter = "AND g.player_id = %s" if player_id else ""
    pid_arg    = (player_id,) if player_id else ()
    cur.execute(f"""
        SELECT COUNT(*)
        FROM moves m JOIN games g ON g.id = m.game_id
        WHERE m.maia_probability IS NULL
          AND m.fen_before IS NOT NULL
          AND m.uci IS NOT NULL
          AND m.color = g.color
          {pid_filter}
    """, pid_arg)
    total_unprocessed = cur.fetchone()[0]

    if limit_games:
        print(f"Processing first {limit_games} games (test mode).")
    print(f"Unprocessed player moves: {total_unprocessed:,}")
    print()

    processed   = 0
    games_done  = set()
    games_batch = []   # game_ids whose moves we just finished
    t_start     = time.time()

    while True:
        batch = _fetch_batch(cur, player_id, limit_games)
        if not batch:
            break

        results  = []
        seen_gids = {r['game_id'] for r in batch}

        for row in batch:
            res = _process_move(row, rapid_model, blitz_model,
                                prepared, inference_each)
            if res:
                results.append(res)

        updated = _flush_moves(cur, results)
        conn.commit()
        processed += updated

        # Identify games where ALL player moves are now processed
        for gid in seen_gids:
            if gid in games_done:
                continue
            cur.execute("""
                SELECT COUNT(*) FROM moves m
                JOIN games g ON g.id = m.game_id
                WHERE m.game_id = %s
                  AND m.color = g.color
                  AND m.maia_probability IS NULL
            """, (gid,))
            remaining = cur.fetchone()[0]
            if remaining == 0:
                games_done.add(gid)
                games_batch.append(gid)

        if games_batch:
            _update_game_win_prob(cur, games_batch)
            conn.commit()
            games_batch = []

        # Progress
        elapsed   = time.time() - t_start
        rate      = processed / elapsed if elapsed > 0 else 0  # moves/sec
        remaining = total_unprocessed - processed
        eta_s     = remaining / rate if rate > 0 else 0

        print(f"  {processed:>8,} moves  "
              f"{len(games_done):>5} games  "
              f"{rate * 60:>6.0f} moves/min  "
              f"ETA: {str(timedelta(seconds=int(eta_s)))}")

        if limit_games and len(games_done) >= limit_games:
            break

        # If batch was smaller than BATCH_SIZE, all unprocessed moves are done
        if len(batch) < BATCH_SIZE:
            break

    # Final game win prob update for any stragglers
    remaining_gids = list(games_done)
    if remaining_gids:
        _update_game_win_prob(cur, remaining_gids)
        conn.commit()

    elapsed = time.time() - t_start
    print()
    print("=" * 55)
    print("MAIA-2 PASS COMPLETE")
    print("=" * 55)
    print(f"  Moves processed:  {processed:,}")
    print(f"  Games updated:    {len(games_done):,}")
    print(f"  Elapsed:          {str(timedelta(seconds=int(elapsed)))}")
    if processed and elapsed:
        print(f"  Rate:             {processed/elapsed*60:.0f} moves/min")

    cur.close()
    conn.close()


def print_sample(n_games: int = 3):
    """Print sample results for spot-checking model output."""
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            m.fen_before,
            m.uci AS player_move,
            m.maia_top_move_uci,
            m.maia_probability,
            m.maia_win_prob,
            m.weakness_type,
            m.centipawn_loss,
            g.game_type,
            g.player_elo
        FROM moves m
        JOIN games g ON g.id = m.game_id
        WHERE m.maia_probability IS NOT NULL
          AND m.color = g.color
        ORDER BY g.id, m.id
        LIMIT %s
    """, (n_games * 3,))
    rows = cur.fetchall()
    cur.close(); conn.close()

    if not rows:
        print("No processed moves found.")
        return

    print()
    print("Sample Maia-2 results:")
    print(f"  {'FEN (40)':<40} {'Played':<6} {'MaiaTop':<7} "
          f"{'Prob':>5} {'WinP':>5} {'CPL':>5}  Type")
    print(f"  {'-'*40} {'-'*6} {'-'*7} {'-'*5} {'-'*5} {'-'*5}  ----")
    for r in rows:
        fen_short = (r[0] or '')[:40]
        w_type    = r[5] or '-'
        print(f"  {fen_short:<40} {r[1]:<6} {(r[2] or '-'):<7} "
              f"{r[3]:>5.3f} {r[4]:>5.3f} {(r[6] or 0):>5}  {w_type}")


if __name__ == '__main__':
    args        = sys.argv[1:]
    limit_games = None
    player_id   = None

    if '--limit' in args:
        idx         = args.index('--limit')
        limit_games = int(args[idx + 1])

    if '--player' in args:
        idx       = args.index('--player')
        player_id = int(args[idx + 1])

    if '--sample' in args:
        print_sample()
        sys.exit(0)

    print("=" * 55)
    print("MAIA-2 POST-PROCESSING PASS")
    print("=" * 55)
    if limit_games:
        print(f"  Mode: TEST ({limit_games} games)")
    if player_id:
        print(f"  Player: {player_id}")
    print()

    run(player_id=player_id, limit_games=limit_games)

    if limit_games:
        print()
        print_sample(n_games=limit_games)
