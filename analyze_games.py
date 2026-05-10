import os
import math
import time
import chess
import chess.engine
import chess.pgn
import chess.polyglot
import chess.syzygy
import io
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing
from dotenv import load_dotenv
from db_setup import get_connection

load_dotenv()

STOCKFISH_PATH = os.getenv("STOCKFISH_PATH")

# ─── Analysis tuning ──────────────────────────────────────────────────────────
NORMAL_TIME         = 0.5
POST_BLUNDER_TIME   = 2.0
POST_MISTAKE_TIME   = 0.8
ENDGAME_TIME        = 0.4
OPENING_TIME        = 0.15
EARLY_OPENING_TIME  = 0.08
LONG_GAME_FACTOR    = 0.6
LONG_GAME_MOVES     = 80
MIN_DEPTH_OPENING   = 8
MIN_DEPTH_MIDDLE    = 14
MIN_DEPTH_ENDGAME   = 16
MAX_DEPTH           = 20
MULTIPV             = 5
MATE_SCORE          = 10000
CPL_CAP             = 500
MIN_GAME_MOVES      = 10


# ─── Load thresholds ──────────────────────────────────────────────────────────
def load_thresholds(game_type: str) -> dict:
    conn = get_connection()
    cur  = conn.cursor()
    cur.execute("""
        SELECT threshold_name, value FROM player_thresholds
        WHERE player_id IS NULL AND game_type IN (%s, 'all')
    """, (game_type,))
    t = {row[0]: row[1] for row in cur.fetchall()}
    cur.close(); conn.close()
    t.setdefault('blunder_cpl',                  200)
    t.setdefault('mistake_cpl',                  100)
    t.setdefault('inaccuracy_cpl',                50)
    t.setdefault('suboptimal_cpl',                20)
    t.setdefault('critical_time_pct',            0.08)
    t.setdefault('low_time_pct',                 0.18)
    t.setdefault('normal_time_pct',              0.40)
    t.setdefault('blunder_score_threshold',      0.85)
    t.setdefault('mistake_score_threshold',      0.60)
    t.setdefault('inaccuracy_score_threshold',   0.35)
    t.setdefault('suboptimal_score_threshold',   0.15)
    t.setdefault('resignation_mindset_eval',    -100)
    t.setdefault('complacency_eval',             200)
    t.setdefault('winning_advantage_eval',       200)
    t.setdefault('salvation_min_swing',          150)
    t.setdefault('premove_ms',                   500)
    t.setdefault('panic_ms',                    2000)
    t.setdefault('panic_clock_ms',             10000)
    t.setdefault('high_quality_depth',            18)
    t.setdefault('medium_quality_depth',          14)
    t.setdefault('high_quality_time_s',          0.8)
    t.setdefault('medium_quality_time_s',        0.4)
    return t


# ─── Score extraction ─────────────────────────────────────────────────────────
def extract_cp(score) -> int | None:
    if score is None:
        return None
    if score.is_mate():
        mate_in = score.mate()
        return (MATE_SCORE - abs(mate_in)) if mate_in > 0 else -(MATE_SCORE - abs(mate_in))
    return score.score(mate_score=MATE_SCORE)


# ─── WDL extraction (correct perspective) ────────────────────────────────────
def extract_wdl_for_player(score, player_color: str) -> tuple:
    """
    Extract WDL from white's perspective then flip if player is black.
    Returns (wins, draws, losses) from player's perspective.
    """
    try:
        wdl = score.white().wdl()
        if player_color == 'white':
            return wdl.wins, wdl.draws, wdl.losses
        else:
            return wdl.losses, wdl.draws, wdl.wins
    except Exception:
        return None, None, None


def extract_wdl_after_move(score, player_color: str) -> tuple:
    """
    After a move, it's the opponent's turn. Flip perspective accordingly.
    Returns (wins, draws, losses) from player's perspective after their move.
    """
    try:
        wdl = score.white().wdl()
        # After player moves, opponent is to move
        # white's wins from opponent's perspective = our wins if we're white
        # but since it's NOW opponent's turn, we need to flip
        if player_color == 'white':
            # White just moved, black to move. White's wins = our wins.
            return wdl.wins, wdl.draws, wdl.losses
        else:
            # Black just moved, white to move. White's wins = our losses.
            return wdl.losses, wdl.draws, wdl.wins
    except Exception:
        return None, None, None


# ─── Win probability conversion ───────────────────────────────────────────────
def wdl_to_win_prob(wins, draws, losses) -> float | None:
    if wins is None:
        return None
    total = wins + draws + losses
    if total == 0:
        return 0.5
    return wins / total


def wdl_to_cp(wins, draws, losses) -> float | None:
    if wins is None:
        return None
    wp = wdl_to_win_prob(wins, draws, losses)
    wp = max(0.0001, min(0.9999, wp))
    return 400 * math.log10(wp / (1 - wp))


def win_prob_from_cp(cp) -> float:
    if cp is None:
        return 0.5
    return 1 / (1 + 10 ** (-cp / 400))


# ─── Position decisiveness ────────────────────────────────────────────────────
def position_decisiveness(wins, draws, losses) -> float:
    """
    How decided is this position already?
    Returns 0.0 = maximally contested, 1.0 = completely decided.
    Positions that are already won/lost should have accuracy discounted.
    """
    if wins is None:
        return 0.0
    total = wins + draws + losses
    if total == 0:
        return 0.0
    wp = wins / total
    # Distance from 50% win probability = how decided the position is
    return min(1.0, abs(wp - 0.5) * 2)


# ─── Three accuracy models ────────────────────────────────────────────────────
def accuracy_wdl(
    wins_before, draws_before, losses_before,
    wins_after,  draws_after,  losses_after
) -> float | None:
    """
    Stockfish WDL accuracy — position-aware.
    Discounts accuracy scores from already-decided positions.
    A blunder from a completely lost position doesn't score 100%.
    """
    if wins_before is None or wins_after is None:
        return None

    wp_before = wdl_to_win_prob(wins_before, draws_before, losses_before)
    wp_after  = wdl_to_win_prob(wins_after,  draws_after,  losses_after)

    if wp_before is None or wp_after is None:
        return None

    # Raw accuracy: how much win probability was preserved
    raw = max(0.0, 1.0 - max(0.0, wp_before - wp_after))

    # Position weight: how much does accuracy matter here?
    # Near-equal position (50% win prob) = full weight
    # Already won/lost position = reduced weight, blend toward neutral
    decisiveness = position_decisiveness(wins_before, draws_before, losses_before)
    position_weight = 1.0 - (decisiveness * 0.7)  # 0.3 minimum weight

    neutral = 0.85  # assumed accuracy in already-decided positions
    blended = raw * position_weight + neutral * (1.0 - position_weight)

    return max(0.0, min(100.0, blended * 100))


def accuracy_lichess(cpl) -> float | None:
    """Lichess CPL-based formula. Strictest standard."""
    if cpl is None:
        return None
    return max(0.0, min(100.0,
        103.1668 * math.exp(-0.04354 * min(cpl, CPL_CAP)) - 3.1669
    ))


def accuracy_chesscom(
    wins_before, draws_before, losses_before,
    wins_after,  draws_after,  losses_after
) -> float | None:
    """
    Chess.com-style win probability delta accuracy.
    Position-aware — discounts already-decided positions.
    """
    if wins_before is None or wins_after is None:
        return None

    cp_b = wdl_to_cp(wins_before, draws_before, losses_before)
    cp_a = wdl_to_cp(wins_after,  draws_after,  losses_after)

    if cp_b is None or cp_a is None:
        return None

    wp_before = win_prob_from_cp(cp_b)
    wp_after  = win_prob_from_cp(cp_a)

    raw = max(0.0, min(1.0, 1.0 - abs(wp_before - wp_after)))

    decisiveness = position_decisiveness(wins_before, draws_before, losses_before)
    position_weight = 1.0 - (decisiveness * 0.7)

    neutral = 0.85
    blended = raw * position_weight + neutral * (1.0 - position_weight)

    return max(0.0, min(100.0, blended * 100))


def average_accuracy(values: list) -> float | None:
    valid = [v for v in values if v is not None]
    return sum(valid) / len(valid) if valid else None


# ─── Position tension ─────────────────────────────────────────────────────────
def calc_position_tension(eval_cp) -> float:
    if eval_cp is None:
        return 0.5
    return max(0.0, 1.0 - min(abs(eval_cp), 300) / 300)


# ─── Eval state ───────────────────────────────────────────────────────────────
def eval_state(eval_cp, thresholds) -> str:
    if eval_cp is None:
        return 'equal'
    w = thresholds.get('winning_advantage_eval', 200)
    if eval_cp >=  w: return 'winning'
    if eval_cp <= -w: return 'losing'
    return 'equal'


# ─── Sigmoid mistake score ────────────────────────────────────────────────────
def compute_mistake_score(cpl, eval_before, phase, thresholds) -> float:
    if cpl is None or cpl <= 0:
        return 0.0
    bt  = thresholds.get('blunder_cpl', 200)
    x   = (cpl - bt / 2) / max(1, bt / 4)
    sig = 1 / (1 + math.exp(-x))
    t   = calc_position_tension(eval_before)
    pm  = {'endgame': 1.4, 'middlegame': 1.0, 'opening': 0.6}.get(phase, 1.0)
    return min(1.0, sig * (0.4 + 0.6 * t) * pm)


# ─── Mistake classification — CPL-primary ────────────────────────────────────
def classify_mistake(score: float, cpl, thresholds) -> str | None:
    """
    Discrete label driven by raw CPL.
    310 CPL is always a blunder regardless of phase or position.
    Continuous score used for severity weighting only.
    """
    if cpl is None:
        return None
    if cpl >= thresholds.get('blunder_cpl',    200): return 'blunder'
    if cpl >= thresholds.get('mistake_cpl',    100): return 'mistake'
    if cpl >= thresholds.get('inaccuracy_cpl',  50): return 'inaccuracy'
    if cpl >= thresholds.get('suboptimal_cpl',  20) and \
       score >= thresholds.get('suboptimal_score_threshold', 0.15):
        return 'suboptimal'
    return None


# ─── Time pressure ────────────────────────────────────────────────────────────
def classify_time_pressure(clock_ms, total_time_ms, increment_ms, total_moves, move_number, thresholds) -> str | None:
    if not clock_ms or not total_time_ms or total_time_ms == 0:
        return None
    if increment_ms and total_moves and move_number:
        moves_remaining = max(1, (total_moves - move_number) / 2)
        effective_clock = clock_ms + increment_ms * moves_remaining
    else:
        effective_clock = clock_ms
    pct = effective_clock / total_time_ms
    if pct <= thresholds.get('critical_time_pct', 0.08): return 'critical'
    if pct <= thresholds.get('low_time_pct',      0.18): return 'low'
    if pct <= thresholds.get('normal_time_pct',   0.40): return 'normal'
    return 'comfortable'


# ─── Time control parsing ─────────────────────────────────────────────────────
def get_total_time_ms(tc: str) -> int | None:
    if not tc or tc == '-':
        return None
    try:
        return int(tc.split('+')[0]) * 1000
    except (ValueError, IndexError):
        return None


def get_increment_ms(tc: str) -> int:
    if not tc or '+' not in tc:
        return 0
    try:
        return int(tc.split('+')[1]) * 1000
    except (ValueError, IndexError):
        return 0


# ─── Analysis quality ─────────────────────────────────────────────────────────
def analysis_quality(depth, elapsed, thresholds) -> tuple:
    if depth   >= thresholds.get('high_quality_depth',   18) and \
       elapsed >= thresholds.get('high_quality_time_s', 0.8):
        return 'high',   0.9
    if depth   >= thresholds.get('medium_quality_depth',   14) and \
       elapsed >= thresholds.get('medium_quality_time_s', 0.4):
        return 'medium', 0.7
    return 'low', 0.4


# ─── Hybrid analysis limit ────────────────────────────────────────────────────
def get_limit_and_mindepth(phase, prev_cpl, total_moves, move_num, thresholds):
    factor  = LONG_GAME_FACTOR if total_moves > LONG_GAME_MOVES else 1.0
    blunder = thresholds.get('blunder_cpl', 200)
    mistake = thresholds.get('mistake_cpl', 100)

    if move_num <= 3:
        return chess.engine.Limit(time=EARLY_OPENING_TIME * factor, depth=MAX_DEPTH), MIN_DEPTH_OPENING
    if move_num <= 10:
        t, min_d = OPENING_TIME * factor, MIN_DEPTH_OPENING
    elif phase == 'endgame':
        t, min_d = ENDGAME_TIME * factor, MIN_DEPTH_ENDGAME
    else:
        t, min_d = NORMAL_TIME * factor, MIN_DEPTH_MIDDLE

    if prev_cpl and prev_cpl >= blunder:
        t     = max(t, POST_BLUNDER_TIME * factor)
        min_d = max(min_d, 16)
    elif prev_cpl and prev_cpl >= mistake:
        t = max(t, POST_MISTAKE_TIME * factor)

    return chess.engine.Limit(time=t, depth=MAX_DEPTH), min_d


# ─── Analyse with min depth guarantee ────────────────────────────────────────
def analyse_position(engine, board, phase, prev_cpl, total_moves, move_num, thresholds):
    limit, min_depth = get_limit_and_mindepth(phase, prev_cpl, total_moves, move_num, thresholds)
    t0   = time.time()
    info = engine.analyse(board, limit, multipv=MULTIPV)
    elapsed = time.time() - t0
    if info and info[0].get('depth', 0) < min_depth:
        info    = engine.analyse(board, chess.engine.Limit(depth=min_depth), multipv=MULTIPV)
        elapsed = time.time() - t0
    return info, elapsed


# ─── Polyglot opening book ────────────────────────────────────────────────────
def open_polyglot_book():
    path = os.getenv('POLYGLOT_BOOK_PATH')
    if path and os.path.exists(path):
        try:
            return chess.polyglot.open_reader(path)
        except Exception:
            pass
    return None


def is_book_move(book, board: chess.Board, move: chess.Move) -> bool:
    if book is None:
        return False
    try:
        return any(e.move == move for e in book.find_all(board))
    except Exception:
        return False


# ─── Syzygy tablebases ────────────────────────────────────────────────────────
def open_syzygy():
    path = os.getenv('SYZYGY_PATH')
    if path and os.path.exists(path):
        try:
            return chess.syzygy.open_tablebase(path)
        except Exception:
            pass
    return None


def get_tablebase_info(board_before, board_after, syzygy_tb) -> tuple:
    """Returns (result, dtz, deviation) from side-to-move's perspective before the move."""
    if syzygy_tb is None:
        return None, None, None
    if bin(board_before.occupied).count('1') > 5:
        return None, None, None
    try:
        dtz = syzygy_tb.get_dtz(board_before)
        if dtz is None:
            wdl = syzygy_tb.get_wdl(board_before)
            if wdl is None:
                return None, None, None
            result = {2: 'win', 1: 'win', 0: 'draw', -1: 'loss', -2: 'loss'}.get(wdl)
            return result, None, None
        if dtz > 0:   result = 'win'
        elif dtz < 0: result = 'loss'
        else:         result = 'draw'
        deviation = None
        if bin(board_after.occupied).count('1') <= 5 and dtz != 0:
            try:
                dtz_after = syzygy_tb.get_dtz(board_after)
                if dtz_after is not None:
                    expected = -(dtz - 1) if dtz > 0 else -(dtz + 1)
                    deviation = dtz_after - expected
            except Exception:
                pass
        return result, dtz, deviation
    except Exception:
        return None, None, None


# ─── Candidate count ──────────────────────────────────────────────────────────
def count_candidates(info_list, threshold=50) -> int:
    if not info_list:
        return 0
    best_cp = extract_cp(info_list[0]['score'].relative)
    if best_cp is None:
        return 1
    return sum(
        1 for info in info_list
        if info.get('pv') and
        extract_cp(info['score'].relative) is not None and
        (best_cp - extract_cp(info['score'].relative)) <= threshold
    )


# ─── Played move rank ─────────────────────────────────────────────────────────
def get_played_move_rank(info_list, played_uci: str) -> tuple:
    for i, info in enumerate(info_list):
        pv = info.get('pv', [])
        if pv and pv[0].uci() == played_uci:
            return i + 1, extract_cp(info['score'].relative)
    return None, None


# ─── Sacrifice detection ──────────────────────────────────────────────────────
def detect_sacrifice(board, move, best_move_uci, cpl) -> tuple:
    if not board.piece_at(move.to_square):
        return False, None
    if move.uci() == best_move_uci:
        return True, 'correct'
    if cpl is not None and cpl < 50:
        return True, 'reasonable'
    if cpl is not None and cpl < 150:
        return True, 'speculative'
    return False, None


# ─── Psychological patterns ───────────────────────────────────────────────────
def detect_psychological_patterns(
    best_eval_available, eval_after_player,
    prev_opp_cpl, player_eval_state,
    time_pressure, cpl, thresholds
) -> dict:
    result = {
        'missed_salvation':         False,
        'salvation_eval_swing':     None,
        'resignation_mindset_flag': False,
        'complacency_flag':         False,
    }

    if (
        player_eval_state == 'losing' and
        prev_opp_cpl is not None and prev_opp_cpl >= 150 and
        best_eval_available is not None and
        eval_after_player is not None and
        (best_eval_available - eval_after_player) >= 100 and
        time_pressure not in ('critical', 'low')
    ):
        result['missed_salvation']         = True
        result['salvation_eval_swing']     = int(best_eval_available - eval_after_player)
        result['resignation_mindset_flag'] = True

    if (
        player_eval_state == 'winning' and
        cpl is not None and
        cpl >= thresholds.get('blunder_cpl', 200) and
        time_pressure not in ('critical', 'low')
    ):
        result['complacency_flag'] = True

    return result


# ─── Main game analysis ───────────────────────────────────────────────────────
def analyze_single_game(game_id: int) -> dict:
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT raw_pgn, color, game_type, time_control, total_moves
        FROM games WHERE id = %s
    """, (game_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return {'game_id': game_id, 'error': 'Game not found'}

    raw_pgn, player_color, game_type, time_control, total_moves = row
    player_color  = (player_color or '').lower()
    game_type     = (game_type    or 'blitz').lower()
    total_time_ms = get_total_time_ms(time_control)
    increment_ms  = get_increment_ms(time_control)
    thresholds    = load_thresholds(game_type)
    poly_reader   = open_polyglot_book()
    syzygy_tb     = open_syzygy()

    if total_moves is not None and total_moves < MIN_GAME_MOVES:
        cur.execute("UPDATE analysis_queue SET status='complete', completed_at=NOW() WHERE game_id=%s", (game_id,))
        cur.execute("UPDATE games SET analyzed=TRUE, analyzed_at=NOW() WHERE id=%s", (game_id,))
        conn.commit(); cur.close(); conn.close()
        return {'game_id': game_id, 'error': f'Too short ({total_moves} moves)'}

    pgn_io = io.StringIO(raw_pgn)
    game   = chess.pgn.read_game(pgn_io)
    if not game:
        cur.close(); conn.close()
        return {'game_id': game_id, 'error': 'Could not parse PGN'}

    cur.execute("""
        SELECT id, move_number, color, fen_before,
               clock_before_ms, opponent_clock_before_ms,
               time_spent_ms, opponent_time_spent_ms, phase, uci
        FROM moves WHERE game_id = %s ORDER BY id ASC
    """, (game_id,))
    move_rows = cur.fetchall()
    if not move_rows:
        cur.close(); conn.close()
        return {'game_id': game_id, 'error': 'No moves found'}

    engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    engine.configure({'Threads': 1, 'Hash': 128})

    board            = game.board()
    annotations      = []
    prev_cpl         = None
    prev_opp_cpl     = None
    novelty_move     = None
    position_history = {}

    # Accuracy accumulators
    p_acc_wdl = []; p_acc_lichess = []; p_acc_chesscom = []
    p_cpls    = []; o_cpls = []; o_acc_wdl = []

    # Game-level tracking
    max_advantage        = None
    missed_salvations    = 0
    complacency_blunders = 0
    had_winning_pos      = False

    for i, node in enumerate(game.mainline()):
        if i >= len(move_rows):
            break

        move = node.move
        mr   = move_rows[i]
        (move_id, move_number, move_color, fen_before,
         clock_before_ms, opp_clock_before_ms,
         time_spent_ms, opp_time_spent_ms, phase, stored_uci) = mr

        move_color     = (move_color or '').lower()
        is_player_move = (move_color == player_color)

        # ── Repetition ───────────────────────────────────────────────────
        fen_key    = ' '.join(fen_before.split()[:4])
        times_seen = position_history.get(fen_key, 0) + 1
        position_history[fen_key] = times_seen

        # ── Clock ────────────────────────────────────────────────────────
        p_clock = clock_before_ms     if is_player_move else opp_clock_before_ms
        o_clock = opp_clock_before_ms if is_player_move else clock_before_ms
        p_spent = time_spent_ms       if is_player_move else opp_time_spent_ms

        tp     = classify_time_pressure(p_clock, total_time_ms, increment_ms, total_moves, move_number, thresholds)
        opp_tp = classify_time_pressure(o_clock, total_time_ms, increment_ms, total_moves, move_number, thresholds)

        is_premove = is_player_move and p_spent is not None and \
                     p_spent < int(thresholds.get('premove_ms', 500))
        is_panic   = is_player_move and p_spent is not None and \
                     p_spent  < int(thresholds.get('panic_ms',       2000)) and \
                     p_clock  is not None and \
                     p_clock  < int(thresholds.get('panic_clock_ms', 10000))

        # ── Book move ────────────────────────────────────────────────────
        book = False
        if novelty_move is None:
            book = is_book_move(poly_reader, board, move)
            if not book and i >= 4:
                novelty_move = move_number

        moves_since_novelty = (move_number - novelty_move) if novelty_move else None
        played_uci = move.uci()

        if book:
            board.push(move)
            annotations.append({
                'move_id': move_id, 'is_book_move': True,
                'time_pressure': tp, 'opponent_time_pressure': opp_tp,
                'is_likely_premove': is_premove, 'is_likely_panic': is_panic,
                'moves_since_novelty': moves_since_novelty,
                'is_repetition': times_seen > 1, 'times_position_seen': times_seen,
                'increment_ms': increment_ms, 'mistake_score': 0.0,
                'analysis_quality': 'book', 'analysis_confidence': 1.0,
                'position_eval_state': 'equal',
            })
            prev_cpl = 0
            continue

        # ── Analyse before move ──────────────────────────────────────────
        info, elapsed = analyse_position(
            engine, board, phase, prev_cpl, total_moves, i, thresholds
        )

        depth_reached = info[0].get('depth', 0) if info else 0
        best_cp       = extract_cp(info[0]['score'].relative) if info else None
        best_move_uci = info[0]['pv'][0].uci() if info and info[0].get('pv') else None
        try:
            best_move_san = board.san(info[0]['pv'][0]) if info and info[0].get('pv') else None
        except Exception:
            best_move_san = None

        # WDL before move — from player's perspective
        wdl_b_w, wdl_b_d, wdl_b_l = (None, None, None)
        if info:
            wdl_b_w, wdl_b_d, wdl_b_l = extract_wdl_for_player(
                info[0]['score'], player_color
            )

        pv_lines = []
        for pv_info in info:
            pv = pv_info.get('pv', [])
            if pv:
                pv_lines.append(' '.join(m.uci() for m in pv[:10]))

        candidate_count = count_candidates(info)
        is_only_move    = (candidate_count == 1)
        pos_tension     = calc_position_tension(best_cp)
        pos_complexity  = 1.0 - (candidate_count / MULTIPV)
        played_rank, played_cp = get_played_move_rank(info, played_uci)
        p_eval_state    = eval_state(best_cp, thresholds)

        if is_player_move and best_cp is not None:
            if max_advantage is None or best_cp > max_advantage:
                max_advantage = best_cp
            if best_cp >= thresholds.get('winning_advantage_eval', 200):
                had_winning_pos = True

        is_sac, sac_type = detect_sacrifice(board, move, best_move_uci, None)

        # ── Tablebase snapshot — capture board before push ────────────────
        pieces_now = bin(board.occupied).count('1')
        board_snap = board.copy() if pieces_now <= 5 else None

        # ── Make move ────────────────────────────────────────────────────
        board.push(move)

        # ── Tablebase lookup (5 pieces or fewer) ──────────────────────────
        if board_snap is not None:
            tb_result, tb_dtz, tb_deviation = get_tablebase_info(board_snap, board, syzygy_tb)
        else:
            tb_result = tb_dtz = tb_deviation = None

        # ── Analyse after move ───────────────────────────────────────────
        info_after = engine.analyse(
            board, chess.engine.Limit(depth=MIN_DEPTH_MIDDLE), multipv=1
        )

        # WDL after move — from player's perspective
        wdl_a_w, wdl_a_d, wdl_a_l = (None, None, None)
        if info_after:
            wdl_a_w, wdl_a_d, wdl_a_l = extract_wdl_after_move(
                info_after[0]['score'], player_color
            )

        score_after_rel = extract_cp(info_after[0]['score'].relative) if info_after else None
        eval_after      = -score_after_rel if score_after_rel is not None else None

        # ── CPL — capped before storage ──────────────────────────────────
        if is_player_move and best_cp is not None and eval_after is not None:
            cpl_raw = max(0, best_cp - eval_after)
            cpl     = min(cpl_raw, CPL_CAP)
        else:
            cpl = None

        if not is_player_move and best_cp is not None and eval_after is not None:
            opp_cpl_raw = max(0, best_cp - eval_after)
            opp_cpl     = min(opp_cpl_raw, CPL_CAP)
            o_cpls.append(opp_cpl)
        else:
            opp_cpl = None

        # ── Three accuracy models ─────────────────────────────────────────
        if is_player_move:
            acc_w = accuracy_wdl(wdl_b_w, wdl_b_d, wdl_b_l, wdl_a_w, wdl_a_d, wdl_a_l)
            acc_l = accuracy_lichess(cpl)
            acc_c = accuracy_chesscom(wdl_b_w, wdl_b_d, wdl_b_l, wdl_a_w, wdl_a_d, wdl_a_l)
            if acc_w is not None: p_acc_wdl.append(acc_w)
            if acc_l is not None: p_acc_lichess.append(acc_l)
            if acc_c is not None: p_acc_chesscom.append(acc_c)
            if cpl   is not None: p_cpls.append(cpl)
        else:
            acc_w = acc_l = acc_c = None
            if opp_cpl is not None:
                ow = accuracy_wdl(wdl_b_w, wdl_b_d, wdl_b_l, wdl_a_w, wdl_a_d, wdl_a_l)
                if ow is not None:
                    o_acc_wdl.append(ow)

        # ── Mistake score and label ───────────────────────────────────────
        m_score = compute_mistake_score(cpl, best_cp, phase, thresholds) if is_player_move else 0.0
        m_class = classify_mistake(m_score, cpl, thresholds)             if is_player_move else None

        # ── Sacrifice correction ──────────────────────────────────────────
        if is_sac:
            is_sac, sac_type = detect_sacrifice(board, move, best_move_uci, cpl)
            sac_correct = sac_type in ('correct', 'reasonable')
            if sac_correct and m_class in ('blunder', 'mistake'):
                m_class = None; m_score = 0.0
        else:
            sac_correct = None

        is_tp_error = (
            m_class in ('blunder', 'mistake') and
            tp == 'critical' and is_player_move
        )

        # ── Psychological patterns ────────────────────────────────────────
        psych = {}
        if is_player_move:
            psych = detect_psychological_patterns(
                best_eval_available = best_cp,
                eval_after_player   = eval_after,
                prev_opp_cpl        = prev_opp_cpl,
                player_eval_state   = p_eval_state,
                time_pressure       = tp,
                cpl                 = cpl,
                thresholds          = thresholds,
            )
            if psych.get('missed_salvation'):  missed_salvations    += 1
            if psych.get('complacency_flag'):  complacency_blunders += 1

        is_desperation = (
            is_player_move and p_eval_state == 'losing' and
            is_sac and not sac_correct and tp not in ('critical',)
        )
        is_swindle = (
            is_player_move and p_eval_state == 'losing' and
            played_rank is None and pos_complexity > 0.6 and
            cpl is not None and cpl < 150
        )

        a_quality, a_confidence = analysis_quality(depth_reached, elapsed, thresholds)

        if is_player_move:
            prev_cpl = cpl if cpl is not None else 0
        else:
            prev_opp_cpl = opp_cpl

        annotations.append({
            'move_id':               move_id,
            'eval_before':           best_cp,
            'eval_after':            eval_after,
            'best_eval':             best_cp,
            'centipawn_loss':        cpl,
            'best_move_uci':         best_move_uci,
            'best_move_san':         best_move_san,
            'pv_line_1':             pv_lines[0] if len(pv_lines) > 0 else None,
            'pv_line_2':             pv_lines[1] if len(pv_lines) > 1 else None,
            'pv_line_3':             pv_lines[2] if len(pv_lines) > 2 else None,
            'pv_line_4':             pv_lines[3] if len(pv_lines) > 3 else None,
            'pv_line_5':             pv_lines[4] if len(pv_lines) > 4 else None,
            'played_move_rank':      played_rank,
            'played_move_cp':        played_cp,
            'analysis_depth':        depth_reached,
            'wdl_wins_before':       wdl_b_w,
            'wdl_draws_before':      wdl_b_d,
            'wdl_losses_before':     wdl_b_l,
            'wdl_wins_after':        wdl_a_w,
            'wdl_draws_after':       wdl_a_d,
            'wdl_losses_after':      wdl_a_l,
            'accuracy_wdl':          round(acc_w, 2) if acc_w is not None else None,
            'accuracy_lichess':      round(acc_l, 2) if acc_l is not None else None,
            'accuracy_chesscom':     round(acc_c, 2) if acc_c is not None else None,
            'mistake_score':         round(m_score, 4),
            'mistake_class':         m_class,
            'mistake_severity':      round(m_score, 4),
            'contextual_severity':   round(m_score, 4),
            'position_tension':      round(pos_tension,    4),
            'position_complexity':   round(pos_complexity, 4),
            'candidate_move_count':  candidate_count,
            'is_only_move':          is_only_move,
            'time_pressure':         tp,
            'opponent_time_pressure': opp_tp,
            'is_time_pressure_error': is_tp_error,
            'is_book_move':          False,
            'is_likely_premove':     is_premove,
            'is_likely_panic':       is_panic,
            'moves_since_novelty':   moves_since_novelty,
            'is_repetition':         times_seen > 1,
            'times_position_seen':   times_seen,
            'increment_ms':          increment_ms,
            'position_eval_state':   p_eval_state,
            'is_sacrifice':          is_sac,
            'sacrifice_type':        sac_type,
            'sacrifice_correct':     sac_correct,
            'desperation_sacrifice': is_desperation,
            'swindle_attempt':       is_swindle,
            'analysis_quality':      a_quality,
            'analysis_confidence':   a_confidence,
            'tablebase_result':      tb_result,
            'tablebase_dtz':         tb_dtz,
            'tablebase_deviation':   tb_deviation,
            **psych,
        })

    engine.quit()
    if poly_reader: poly_reader.close()
    if syzygy_tb:   syzygy_tb.close()

    # ── Drift detection ────────────────────────────────────────────────────
    p_ann = [a for a in annotations if a.get('centipawn_loss') is not None]
    for idx, ann in enumerate(p_ann):
        window     = [p_ann[j]['centipawn_loss'] for j in range(max(0, idx-4), idx+1)]
        cumulative = sum(window)
        ann['cumulative_drift_5'] = cumulative
        ann['drift_flag'] = (
            cumulative > 100 and
            ann['centipawn_loss'] < thresholds.get('inaccuracy_cpl', 50)
        )

    # ── Game-level accuracy ────────────────────────────────────────────────
    game_acc_wdl      = average_accuracy(p_acc_wdl)
    game_acc_lichess  = average_accuracy(p_acc_lichess)
    game_acc_chesscom = average_accuracy(p_acc_chesscom)
    avg_player_cpl    = (sum(p_cpls) / len(p_cpls)) if p_cpls else None
    avg_opp_cpl       = (sum(o_cpls) / len(o_cpls)) if o_cpls else None
    opp_acc_avg       = average_accuracy(o_acc_wdl)

    # ── Winning conversion ─────────────────────────────────────────────────
    if had_winning_pos:
        cur.execute("SELECT result FROM games WHERE id = %s", (game_id,))
        g_result = cur.fetchone()
        winning_converted     = g_result and g_result[0] == 'win'
        advantage_surrendered = not winning_converted
    else:
        winning_converted     = None
        advantage_surrendered = False

    # ── Novelty FEN ───────────────────────────────────────────────────────
    novelty_fen = None
    if novelty_move:
        for mr in move_rows:
            if mr[1] == novelty_move:
                novelty_fen = mr[3]; break

    # ── Batch write moves ──────────────────────────────────────────────────
    for ann in annotations:
        if ann.get('analysis_quality') == 'book':
            cur.execute("""
                UPDATE moves SET
                    is_book_move=TRUE, time_pressure=%s, opponent_time_pressure=%s,
                    is_likely_premove=%s, is_likely_panic=%s, moves_since_novelty=%s,
                    is_repetition=%s, times_position_seen=%s, increment_ms=%s,
                    mistake_score=0.0, analysis_quality='book', analysis_confidence=1.0,
                    position_eval_state='equal'
                WHERE id=%s
            """, (
                ann.get('time_pressure'), ann.get('opponent_time_pressure'),
                ann.get('is_likely_premove'), ann.get('is_likely_panic'),
                ann.get('moves_since_novelty'), ann.get('is_repetition'),
                ann.get('times_position_seen'), ann.get('increment_ms'),
                ann['move_id'],
            ))
        else:
            cur.execute("""
                UPDATE moves SET
                    eval_before=%s, eval_after=%s, best_eval=%s,
                    centipawn_loss=%s, best_move_uci=%s, best_move_san=%s,
                    pv_line_1=%s, pv_line_2=%s, pv_line_3=%s, pv_line_4=%s, pv_line_5=%s,
                    played_move_rank=%s, played_move_cp=%s, analysis_depth=%s,
                    wdl_wins_before=%s, wdl_draws_before=%s, wdl_losses_before=%s,
                    wdl_wins_after=%s, wdl_draws_after=%s, wdl_losses_after=%s,
                    accuracy_wdl=%s, accuracy_lichess=%s, accuracy_chesscom=%s,
                    mistake_score=%s, mistake_class=%s, mistake_severity=%s,
                    contextual_severity=%s, position_tension=%s, position_complexity=%s,
                    candidate_move_count=%s, is_only_move=%s,
                    time_pressure=%s, opponent_time_pressure=%s, is_time_pressure_error=%s,
                    is_book_move=FALSE, is_likely_premove=%s, is_likely_panic=%s,
                    moves_since_novelty=%s, is_repetition=%s, times_position_seen=%s,
                    increment_ms=%s, position_eval_state=%s,
                    is_sacrifice=%s, sacrifice_type=%s, sacrifice_correct=%s,
                    desperation_sacrifice=%s, swindle_attempt=%s,
                    missed_salvation=%s, salvation_eval_swing=%s,
                    resignation_mindset_flag=%s, complacency_flag=%s,
                    drift_flag=%s, cumulative_drift_5=%s,
                    analysis_quality=%s, analysis_confidence=%s,
                    tablebase_result=%s, tablebase_dtz=%s, tablebase_deviation=%s
                WHERE id=%s
            """, (
                ann.get('eval_before'), ann.get('eval_after'), ann.get('best_eval'),
                ann.get('centipawn_loss'), ann.get('best_move_uci'), ann.get('best_move_san'),
                ann.get('pv_line_1'), ann.get('pv_line_2'), ann.get('pv_line_3'),
                ann.get('pv_line_4'), ann.get('pv_line_5'),
                ann.get('played_move_rank'), ann.get('played_move_cp'),
                ann.get('analysis_depth'),
                ann.get('wdl_wins_before'), ann.get('wdl_draws_before'), ann.get('wdl_losses_before'),
                ann.get('wdl_wins_after'), ann.get('wdl_draws_after'), ann.get('wdl_losses_after'),
                ann.get('accuracy_wdl'), ann.get('accuracy_lichess'), ann.get('accuracy_chesscom'),
                ann.get('mistake_score'), ann.get('mistake_class'), ann.get('mistake_severity'),
                ann.get('contextual_severity'), ann.get('position_tension'), ann.get('position_complexity'),
                ann.get('candidate_move_count'), ann.get('is_only_move'),
                ann.get('time_pressure'), ann.get('opponent_time_pressure'), ann.get('is_time_pressure_error'),
                ann.get('is_likely_premove'), ann.get('is_likely_panic'),
                ann.get('moves_since_novelty'), ann.get('is_repetition'), ann.get('times_position_seen'),
                ann.get('increment_ms'), ann.get('position_eval_state'),
                ann.get('is_sacrifice'), ann.get('sacrifice_type'), ann.get('sacrifice_correct'),
                ann.get('desperation_sacrifice'), ann.get('swindle_attempt'),
                ann.get('missed_salvation', False), ann.get('salvation_eval_swing'),
                ann.get('resignation_mindset_flag', False), ann.get('complacency_flag', False),
                ann.get('drift_flag', False), ann.get('cumulative_drift_5'),
                ann.get('analysis_quality'), ann.get('analysis_confidence'),
                ann.get('tablebase_result'), ann.get('tablebase_dtz'), ann.get('tablebase_deviation'),
                ann['move_id'],
            ))

    # ── Update game ────────────────────────────────────────────────────────
    cur.execute("""
        UPDATE games SET
            analyzed=TRUE, analyzed_at=NOW(),
            novelty_move=%s, novelty_fen=%s,
            accuracy_pct=%s, accuracy_wdl=%s, accuracy_lichess=%s, accuracy_chesscom=%s,
            opponent_avg_cpl=%s, opponent_accuracy_pct=%s,
            missed_salvations=%s, complacency_blunders=%s,
            winning_position_converted=%s, max_advantage_reached=%s, advantage_surrendered=%s
        WHERE id=%s
    """, (
        novelty_move, novelty_fen,
        round(game_acc_wdl,      2) if game_acc_wdl      is not None else None,
        round(game_acc_wdl,      2) if game_acc_wdl      is not None else None,
        round(game_acc_lichess,  2) if game_acc_lichess   is not None else None,
        round(game_acc_chesscom, 2) if game_acc_chesscom  is not None else None,
        round(avg_opp_cpl,       2) if avg_opp_cpl        is not None else None,
        round(opp_acc_avg,       2) if opp_acc_avg        is not None else None,
        missed_salvations, complacency_blunders,
        winning_converted, max_advantage, advantage_surrendered,
        game_id,
    ))
    cur.execute("UPDATE analysis_queue SET status='complete', completed_at=NOW() WHERE game_id=%s", (game_id,))
    conn.commit(); cur.close(); conn.close()

    return {
        'game_id':         game_id,
        'moves_annotated': len(annotations),
        'acc_wdl':         round(game_acc_wdl,      1) if game_acc_wdl      is not None else None,
        'acc_lichess':     round(game_acc_lichess,  1) if game_acc_lichess   is not None else None,
        'acc_chesscom':    round(game_acc_chesscom, 1) if game_acc_chesscom  is not None else None,
        'avg_cpl':         round(avg_player_cpl,    1) if avg_player_cpl     is not None else None,
    }


# ─── Queue runner ─────────────────────────────────────────────────────────────
def run_analysis_queue(batch_size: int = 20, parallel: bool = False):
    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        UPDATE analysis_queue SET status='pending'
        WHERE status='in_progress' AND started_at < NOW() - INTERVAL '15 minutes'
    """)
    conn.commit()

    cur.execute("""
        SELECT aq.game_id FROM analysis_queue aq
        JOIN games g ON g.id = aq.game_id
        WHERE aq.status='pending' AND g.total_moves >= %s
        ORDER BY aq.priority DESC, aq.queued_at ASC
        LIMIT %s
    """, (MIN_GAME_MOVES, batch_size))
    game_ids = [row[0] for row in cur.fetchall()]

    if game_ids:
        cur.execute("""
            UPDATE analysis_queue SET status='in_progress', started_at=NOW()
            WHERE game_id = ANY(%s)
        """, (game_ids,))
        conn.commit()

    cur.close(); conn.close()

    if not game_ids:
        print('No games in queue.'); return

    total      = len(game_ids)
    start_time = time.time()

    log_conn = get_connection()
    log_cur  = log_conn.cursor()
    log_cur.execute("""
        INSERT INTO analysis_log (started_at, games_analyzed, moves_annotated, errors)
        VALUES (NOW(), 0, 0, 0) RETURNING id
    """)
    log_id = log_cur.fetchone()[0]
    log_conn.commit()

    total_moves  = 0
    total_errors = 0
    workers      = max(1, multiprocessing.cpu_count() - 1)
    mode         = f'parallel ({workers} workers)' if parallel else 'sequential'
    print(f'\nAnalyzing {total} games | multipv={MULTIPV} | {mode}\n')

    def handle_result(result, idx):
        nonlocal total_moves, total_errors
        elapsed   = time.time() - start_time
        rate      = idx / (elapsed / 60) if elapsed > 0 else 0
        remaining = (total - idx) / rate  if rate   > 0 else 0

        if 'error' in result and result.get('acc_wdl') is None:
            total_errors += 1
            status = f"SKIP — {result['error']}"
        else:
            moves = result.get('moves_annotated', 0)
            total_moves += moves
            status = (
                f"{moves} moves | "
                f"wdl={result.get('acc_wdl','?')}% | "
                f"lichess={result.get('acc_lichess','?')}% | "
                f"chesscom={result.get('acc_chesscom','?')}% | "
                f"avg_cpl={result.get('avg_cpl','?')}"
            )
        print(f"  [{idx}/{total}] Game {result['game_id']}: {status} "
              f"| {rate:.1f} games/min | ETA {remaining:.0f}m")

    if parallel:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures   = {executor.submit(analyze_single_game, gid): gid for gid in game_ids}
            completed = 0
            for future in as_completed(futures):
                completed += 1
                try:
                    result = future.result()
                except Exception as e:
                    result = {'game_id': futures[future], 'error': str(e)}
                handle_result(result, completed)
    else:
        for i, game_id in enumerate(game_ids):
            try:
                result = analyze_single_game(game_id)
            except Exception as e:
                result = {'game_id': game_id, 'error': str(e)}
            handle_result(result, i + 1)

    total_time = time.time() - start_time
    log_cur.execute("""
        UPDATE analysis_log SET
            completed_at=NOW(), games_analyzed=%s,
            moves_annotated=%s, avg_time_per_move_ms=%s, errors=%s
        WHERE id=%s
    """, (
        total - total_errors, total_moves,
        (total_time / total_moves * 1000) if total_moves > 0 else 0,
        total_errors, log_id,
    ))
    log_conn.commit(); log_cur.close(); log_conn.close()

    print(f'\nDone. {total - total_errors} analyzed, '
          f'{total_errors} errors, {total_time/60:.1f} minutes total.')


if __name__ == '__main__':
    run_analysis_queue(batch_size=20, parallel=False)