"""
pattern_detector.py — Layer 1: Mechanically detectable chess patterns.

Processes analyzed moves and writes to move_concepts + moves.pattern_tags.
Run after analysis completes (or incrementally as games finish).

Layer 2 (TODO): Prophylaxis failure (3.4.5) — needs 3-5 move lookahead window.
Layer 2 (TODO): Plan inconsistency — needs move-direction categorization across windows.
Layer 3 (TODO): Tilt detection (7.3.1) — needs session grouping across games.
Layer 3 (TODO): Rating anxiety (7.3.2) — needs cross-game opponent-elo aggregation.
Layer 3 (TODO): Opening prep gap (7.1.1) — needs time vs phase baseline comparison.
"""
import sys
import chess
from db_setup import get_connection

# ─── Piece values (centipawns) ────────────────────────────────────────────────
PV = {
    chess.PAWN:   100,
    chess.KNIGHT: 300,
    chess.BISHOP: 320,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:   20000,
}

ROOK_DIRS   = [(1,0),(-1,0),(0,1),(0,-1)]
BISHOP_DIRS = [(1,1),(1,-1),(-1,1),(-1,-1)]
ALL_DIRS    = ROOK_DIRS + BISHOP_DIRS

def _slider_dirs(pt):
    if pt == chess.ROOK:   return ROOK_DIRS
    if pt == chess.BISHOP: return BISHOP_DIRS
    if pt == chess.QUEEN:  return ALL_DIRS
    return []

def _ray_pieces(board, sq, dx, dy, limit=2):
    """First `limit` pieces along ray from sq in direction (dx, dy)."""
    found, f, r = [], chess.square_file(sq) + dx, chess.square_rank(sq) + dy
    while 0 <= f <= 7 and 0 <= r <= 7 and len(found) < limit:
        s = chess.square(f, r)
        p = board.piece_at(s)
        if p is not None:
            found.append((s, p))
        f += dx; r += dy
    return found

def _cc(color_str):
    return chess.WHITE if color_str == 'white' else chess.BLACK


# ══════════════════════════════════════════════════════════════════════════════
# TACTICAL DETECTORS (analyse what best_move creates = what player MISSED)
# ══════════════════════════════════════════════════════════════════════════════

def detect_fork(board, bm, pc_str):
    """3.1.1 — Best move creates a fork (attacks 2+ non-pawn opponent pieces)."""
    b = board.copy(); b.push(bm)
    opp = not _cc(pc_str)
    to = bm.to_square
    attacked = [sq for sq in b.attacks(to)
                if b.piece_at(sq) and b.piece_at(sq).color == opp
                and b.piece_at(sq).piece_type != chess.PAWN]
    # King counts even though it's excluded from pawn filter
    all_opp = [sq for sq in b.attacks(to)
               if b.piece_at(sq) and b.piece_at(sq).color == opp]
    if len(attacked) >= 2 or (len(all_opp) >= 2 and
            any(b.piece_at(s).piece_type == chess.KING for s in all_opp)):
        return [('3.1.1', 0.85, None, 'mathematical')]
    return []


def detect_pin(board, pm, pc_str):
    """3.1.2 — Player broke a pin (moved pinned piece) or moved into a pin."""
    pc = _cc(pc_str)
    results = []
    if board.is_pinned(pc, pm.from_square):
        results.append(('3.1.2', 0.80, None, 'mathematical'))
    b = board.copy(); b.push(pm)
    if b.piece_at(pm.to_square) and b.is_pinned(pc, pm.to_square) and not results:
        results.append(('3.1.2', 0.70, None, 'mathematical'))
    return results


def detect_skewer(board, bm, pc_str):
    """3.1.3 — Best move skewers (slider hits valuable piece, lesser piece behind)."""
    b = board.copy(); b.push(bm)
    moved = b.piece_at(bm.to_square)
    if not moved or moved.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return []
    opp = not _cc(pc_str)
    for dx, dy in _slider_dirs(moved.piece_type):
        ray = _ray_pieces(b, bm.to_square, dx, dy, limit=2)
        if len(ray) == 2:
            (_, p1), (_, p2) = ray
            if (p1.color == opp and p2.color == opp and
                    PV.get(p1.piece_type, 0) > PV.get(p2.piece_type, 0)):
                return [('3.1.3', 0.80, None, 'mathematical')]
    return []


def detect_discovered_attack(board, bm, pc_str):
    """3.1.4 — Best move reveals slider attack from a non-moving piece."""
    pc = _cc(pc_str)
    opp = not pc

    def slider_attacks(b):
        return {(atk, tgt)
                for atk in chess.SQUARES
                if b.piece_at(atk) and b.piece_at(atk).color == pc
                   and b.piece_at(atk).piece_type in (chess.BISHOP, chess.ROOK, chess.QUEEN)
                for tgt in b.attacks(atk)
                if b.piece_at(tgt) and b.piece_at(tgt).color == opp}

    before = slider_attacks(board)
    b = board.copy(); b.push(bm)
    after = slider_attacks(b)
    # New attacks originating from pieces that did NOT just move
    new = {(a, t) for a, t in (after - before) if a != bm.to_square}
    return [('3.1.4', 0.80, None, 'mathematical')] if new else []


def detect_discovered_check(board, bm, pc_str):
    """3.1.5 / 3.1.6 — Best move gives discovered or double check."""
    b = board.copy(); b.push(bm)
    if not b.is_check():
        return []
    checkers = b.checkers()
    results = []
    if len(checkers) >= 2:
        results += [('3.1.6', 0.95, None, 'mathematical'),
                    ('3.1.5', 0.90, None, 'mathematical')]
    elif bm.to_square not in checkers:
        results.append(('3.1.5', 0.90, None, 'mathematical'))
    return results


def detect_removal_of_defender(board, bm, pc_str):
    """3.1.7 — Best move captures a piece that was solely defending another."""
    if not board.is_capture(bm):
        return []
    pc = _cc(pc_str)
    opp = not pc
    b = board.copy(); b.push(bm)
    for sq in chess.SQUARES:
        p = b.piece_at(sq)
        if p and p.color == opp and p.piece_type != chess.KING:
            if b.is_attacked_by(pc, sq) and not b.is_attacked_by(opp, sq):
                if board.is_attacked_by(opp, sq):   # was defended before capture
                    return [('3.1.7', 0.85, None, 'mathematical')]
    return []


def detect_overloading(board, bm, pc_str):
    """3.1.8 — Best move attacks an overloaded opponent piece (sole defender of 2+)."""
    pc = _cc(pc_str)
    opp = not pc
    sole_of = {}
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != opp:
            continue
        for dsq in chess.SQUARES:
            dp = board.piece_at(dsq)
            if not dp or dp.color != opp or dsq == sq:
                continue
            defs = board.attackers(opp, dsq)
            if sq in defs and len(defs) == 1:
                sole_of.setdefault(sq, []).append(dsq)
    overloaded = {sq: lst for sq, lst in sole_of.items() if len(lst) >= 2}
    if not overloaded:
        return []
    b = board.copy(); b.push(bm)
    atk = b.attacks(bm.to_square)
    for ol_sq, defended in overloaded.items():
        if ol_sq in atk or any(d in atk for d in defended):
            return [('3.1.8', 0.75, None, 'mathematical')]
    return []


def detect_deflection(board, bm, pc_str):
    """3.1.10 — Best move threatens a sole defender, forcing it away."""
    pc = _cc(pc_str)
    opp = not pc
    b = board.copy(); b.push(bm)
    for sq in chess.SQUARES:
        p = b.piece_at(sq)
        if not p or p.color != opp:
            continue
        if not b.is_attacked_by(pc, sq):
            continue
        for dsq in chess.SQUARES:
            dp = board.piece_at(dsq)
            if not dp or dp.color != opp or dsq == sq:
                continue
            defs = board.attackers(opp, dsq)
            if sq in defs and len(defs) == 1:
                return [('3.1.10', 0.75, None, 'mathematical')]
    return []


def detect_decoy(board, bm, pc_str):
    """3.1.11 — Best move sacrifices a piece to lure opponent piece to bad square."""
    b = board.copy(); b.push(bm)
    opp = not _cc(pc_str)
    moved = b.piece_at(bm.to_square)
    if not moved:
        return []
    moved_val = PV.get(moved.piece_type, 0)
    if b.is_attacked_by(opp, bm.to_square):
        atkers = [b.piece_at(s) for s in b.attackers(opp, bm.to_square) if b.piece_at(s)]
        min_atk = min((PV.get(a.piece_type, 999999) for a in atkers), default=999999)
        if min_atk < moved_val:
            return [('3.1.11', 0.70, None, 'mathematical')]
    return []


def detect_zwischenzug(board, bm, pc_str):
    """3.1.12 — Best move is a quiet in-between check while a hanging piece exists."""
    pc = _cc(pc_str)
    opp = not pc
    if board.is_capture(bm):
        return []
    b = board.copy(); b.push(bm)
    if not b.is_check():
        return []
    # Confirm there's a hanging opponent piece that could have been recaptured instead
    hanging = any(
        board.piece_at(sq) and board.piece_at(sq).color == opp
        and board.is_attacked_by(pc, sq)
        and not board.is_attacked_by(opp, sq)
        for sq in chess.SQUARES
    )
    return [('3.1.12', 0.75, None, 'mathematical')] if hanging else []


def detect_xray(board, bm, pc_str):
    """3.1.13 — Best move's slider attacks through one opponent piece to another."""
    b = board.copy(); b.push(bm)
    moved = b.piece_at(bm.to_square)
    if not moved or moved.piece_type not in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        return []
    opp = not _cc(pc_str)
    for dx, dy in _slider_dirs(moved.piece_type):
        ray = _ray_pieces(b, bm.to_square, dx, dy, limit=2)
        if len(ray) == 2:
            (_, p1), (_, p2) = ray
            if p1.color == opp and p2.color == opp:
                return [('3.1.13', 0.75, None, 'mathematical')]
    return []


def detect_clearance(board, bm, pv_line_1):
    """3.1.14 — Best move vacates a square used by another piece in the follow-up."""
    if not pv_line_1:
        return []
    pv = pv_line_1.split()
    if len(pv) < 3:
        return []
    try:
        follow = chess.Move.from_uci(pv[2])
        if follow.to_square == bm.from_square:
            return [('3.1.14', 0.80, None, 'mathematical')]
    except Exception:
        pass
    return []


def detect_back_rank_mate(board, bm, pc_str):
    """3.2.1 — Best move delivers or creates a back-rank mate threat."""
    pc = _cc(pc_str)
    opp = not pc
    b = board.copy(); b.push(bm)
    opp_king = b.king(opp)
    if opp_king is None:
        return []
    king_rank = chess.square_rank(opp_king)
    if king_rank not in (0, 7):
        return []
    if b.is_checkmate():
        return [('3.2.1', 0.95, None, 'mathematical')]
    # Threat: king trapped on back rank with no escape off the rank
    free_off_rank = [
        sq for sq in b.attacks(opp_king)
        if (not b.piece_at(sq) or b.piece_at(sq).color == pc)
        and not b.is_attacked_by(pc, sq)
        and chess.square_rank(sq) != king_rank
    ]
    if free_off_rank:
        return []
    if b.is_attacked_by(pc, opp_king):
        return [('3.2.1', 0.85, None, 'mathematical')]
    return []


def detect_smothered_mate(board, bm, pc_str):
    """3.2.2 — Best move delivers smothered mate (knight check, king blocked by own pieces)."""
    opp = not _cc(pc_str)
    b = board.copy(); b.push(bm)
    if not b.is_checkmate():
        return []
    checkers = list(b.checkers())
    if len(checkers) != 1:
        return []
    checker = b.piece_at(checkers[0])
    if not checker or checker.piece_type != chess.KNIGHT:
        return []
    opp_king = b.king(opp)
    if opp_king is None:
        return []
    own_blocking = sum(
        1 for sq in b.attacks(opp_king)
        if b.piece_at(sq) and b.piece_at(sq).color == opp
    )
    return [('3.2.2', 0.95, None, 'mathematical')] if own_blocking >= 2 else []


def detect_forcing_move_missed(board, bm, pm, pc_str):
    """3.3.3 — Best move is check/capture but player played quiet."""
    b_bm = board.copy(); b_bm.push(bm)
    b_pm = board.copy(); b_pm.push(pm)
    if (board.is_capture(bm) or b_bm.is_check()) and not (board.is_capture(pm) or b_pm.is_check()):
        return [('3.3.3', 0.85, None, 'mathematical')]
    return []


def detect_calculation_depth(pv_line_1, cpl):
    """3.3.6 — PV length indicates how deep the player needed to calculate."""
    if not pv_line_1 or not cpl or cpl < 30:
        return []
    depth = len(pv_line_1.split()) // 2
    if depth < 2:
        return []
    weight = min(1.0, 0.40 + depth * 0.08)
    return [('3.3.6', weight, None, 'mathematical')]


def detect_quiet_move_missed(board, bm, pc_str, cpl):
    """3.4.2 — Best move is quiet (non-capture, non-check) but wins material/position."""
    if not cpl or cpl < 50:
        return []
    b = board.copy(); b.push(bm)
    if not board.is_capture(bm) and not b.is_check():
        return [('3.4.2', 0.80, None, 'mathematical')]
    return []


# ══════════════════════════════════════════════════════════════════════════════
# POSITIONAL DETECTORS (analyse what played_move DAMAGES vs best_move)
# ══════════════════════════════════════════════════════════════════════════════

def _piece_attack_count(board, color):
    return sum(len(board.attacks(sq))
               for sq in chess.SQUARES
               if board.piece_at(sq) and board.piece_at(sq).color == color)


def detect_piece_activity_loss(board, bm, pm, pc_str):
    """4.1.1 — Played move gives >20% fewer attacked squares than best move would."""
    pc = _cc(pc_str)
    b_bm = board.copy(); b_bm.push(bm)
    b_pm = board.copy(); b_pm.push(pm)
    act_best   = _piece_attack_count(b_bm, pc)
    act_played = _piece_attack_count(b_pm, pc)
    if act_best > 0 and (act_best - act_played) / act_best > 0.20:
        return [('4.1.1', 0.65, None, 'positional')]
    return []


def _bishop_obstruction(board, color):
    """Total own pawns on same color square as each bishop."""
    total = 0
    for bsq in chess.SQUARES:
        bp = board.piece_at(bsq)
        if not bp or bp.color != color or bp.piece_type != chess.BISHOP:
            continue
        bishop_light = bool(chess.BB_LIGHT_SQUARES & chess.BB_SQUARES[bsq])
        for psq in chess.SQUARES:
            pp = board.piece_at(psq)
            if pp and pp.color == color and pp.piece_type == chess.PAWN:
                pawn_light = bool(chess.BB_LIGHT_SQUARES & chess.BB_SQUARES[psq])
                if pawn_light == bishop_light:
                    total += 1
    return total


def detect_bad_bishop(board, pm, pc_str):
    """4.1.2 — Played move increased own-pawn obstruction of player's bishop."""
    pc = _cc(pc_str)
    b = board.copy(); b.push(pm)
    if _bishop_obstruction(b, pc) > _bishop_obstruction(board, pc):
        return [('4.1.2', 0.65, None, 'positional')]
    return []


def _is_outpost(sq, color, board):
    """Square on rank 3-5 (white) or 2-4 (black) not attackable by opponent pawns."""
    rank = chess.square_rank(sq)
    if color == chess.WHITE and rank < 3: return False
    if color == chess.BLACK and rank > 4: return False
    opp = not color
    return not any(sq in board.attacks(psq)
                   for psq in chess.SQUARES
                   if board.piece_at(psq) and board.piece_at(psq).color == opp
                   and board.piece_at(psq).piece_type == chess.PAWN)


def detect_knight_outpost_missed(board, bm, pm, pc_str):
    """4.1.4 — Best move places knight on outpost; player's move did not."""
    pc = _cc(pc_str)
    bm_piece = board.piece_at(bm.from_square)
    if not bm_piece or bm_piece.piece_type != chess.KNIGHT:
        return []
    if not _is_outpost(bm.to_square, pc, board):
        return []
    pm_piece = board.piece_at(pm.from_square)
    if (pm_piece and pm_piece.piece_type == chess.KNIGHT
            and _is_outpost(pm.to_square, pc, board)):
        return []
    return [('4.1.4', 0.70, None, 'positional')]


def _rooks_on_open_files(board, color):
    count = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != color or p.piece_type != chess.ROOK:
            continue
        f = chess.square_file(sq)
        if not any(board.piece_at(chess.square(f, r)) and
                   board.piece_at(chess.square(f, r)).color == color and
                   board.piece_at(chess.square(f, r)).piece_type == chess.PAWN
                   for r in range(8)):
            count += 1
    return count


def detect_rook_open_file_missed(board, bm, pm, pc_str):
    """4.1.5 — Best move places rook on open file; played move did not."""
    pc = _cc(pc_str)
    bm_piece = board.piece_at(bm.from_square)
    if not bm_piece or bm_piece.piece_type != chess.ROOK:
        return []
    b_bm = board.copy(); b_bm.push(bm)
    b_pm = board.copy(); b_pm.push(pm)
    if _rooks_on_open_files(b_bm, pc) > _rooks_on_open_files(b_pm, pc):
        return [('4.1.5', 0.70, None, 'positional')]
    return []


def _count_isolated(board, color):
    isolated = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != color or p.piece_type != chess.PAWN:
            continue
        f = chess.square_file(sq)
        has_neighbor = any(
            board.piece_at(chess.square(adj, r)) and
            board.piece_at(chess.square(adj, r)).color == color and
            board.piece_at(chess.square(adj, r)).piece_type == chess.PAWN
            for adj in [f-1, f+1] if 0 <= adj <= 7
            for r in range(8)
        )
        if not has_neighbor:
            isolated += 1
    return isolated


def detect_isolated_pawn(board, pm, pc_str):
    """4.2.1 — Played move created an isolated pawn."""
    pc = _cc(pc_str)
    b = board.copy(); b.push(pm)
    if _count_isolated(b, pc) > _count_isolated(board, pc):
        return [('4.2.1', 0.60, None, 'positional')]
    return []


def _count_doubled(board, color):
    doubled = 0
    for f in range(8):
        n = sum(1 for r in range(8)
                if board.piece_at(chess.square(f, r)) and
                board.piece_at(chess.square(f, r)).color == color and
                board.piece_at(chess.square(f, r)).piece_type == chess.PAWN)
        if n >= 2:
            doubled += n - 1
    return doubled


def detect_doubled_pawn(board, pm, pc_str):
    """4.2.2 — Played move created doubled pawns."""
    pc = _cc(pc_str)
    b = board.copy(); b.push(pm)
    if _count_doubled(b, pc) > _count_doubled(board, pc):
        return [('4.2.2', 0.55, None, 'positional')]
    return []


def _count_backward(board, color):
    opp = not color
    count = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != color or p.piece_type != chess.PAWN:
            continue
        f, r = chess.square_file(sq), chess.square_rank(sq)
        adv_r = r + 1 if color == chess.WHITE else r - 1
        if not (0 <= adv_r <= 7):
            continue
        # Any friendly pawn that could support the advance?
        has_support = any(
            board.piece_at(chess.square(adj, sup_r)) and
            board.piece_at(chess.square(adj, sup_r)).color == color and
            board.piece_at(chess.square(adj, sup_r)).piece_type == chess.PAWN
            for adj in [f-1, f+1] if 0 <= adj <= 7
            for sup_r in ([adv_r - 1] if color == chess.WHITE else [adv_r + 1])
            if 0 <= sup_r <= 7
        )
        if has_support:
            continue
        # Opponent pawn on same file ahead (semi-open) — makes it a target
        opp_ahead = any(
            board.piece_at(chess.square(f, cr)) and
            board.piece_at(chess.square(f, cr)).color == opp and
            board.piece_at(chess.square(f, cr)).piece_type == chess.PAWN
            for cr in (range(adv_r, 8) if color == chess.WHITE else range(0, adv_r + 1))
        )
        if opp_ahead:
            count += 1
    return count


def detect_backward_pawn(board, pm, pc_str):
    """4.2.3 — Played move created a backward pawn."""
    pc = _cc(pc_str)
    b = board.copy(); b.push(pm)
    if _count_backward(b, pc) > _count_backward(board, pc):
        return [('4.2.3', 0.60, None, 'positional')]
    return []


def _advanceable_passed(board, color):
    opp = not color
    result = []
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if not p or p.color != color or p.piece_type != chess.PAWN:
            continue
        f, r = chess.square_file(sq), chess.square_rank(sq)
        ranks_ahead = range(r+1, 8) if color == chess.WHITE else range(0, r)
        is_passed = not any(
            board.piece_at(chess.square(cf, cr)) and
            board.piece_at(chess.square(cf, cr)).color == opp and
            board.piece_at(chess.square(cf, cr)).piece_type == chess.PAWN
            for cr in ranks_ahead for cf in [f-1, f, f+1] if 0 <= cf <= 7
        )
        if is_passed:
            adv_r = r + 1 if color == chess.WHITE else r - 1
            if 0 <= adv_r <= 7 and board.piece_at(chess.square(f, adv_r)) is None:
                result.append(sq)
    return result


def detect_passed_pawn_neglected(board, pm, pc_str, cpl):
    """4.2.4 — Player had advanceable passed pawn but moved elsewhere (CPL >= 30)."""
    if not cpl or cpl < 30:
        return []
    pc = _cc(pc_str)
    for pp_sq in _advanceable_passed(board, pc):
        if pm.from_square != pp_sq:
            return [('4.2.4', 0.65, None, 'positional')]
    return []


def _pawn_defends(sq, color):
    """Squares diagonally in front of a pawn at sq."""
    f, r = chess.square_file(sq), chess.square_rank(sq)
    dr = 1 if color == chess.WHITE else -1
    return [chess.square(f + df, r + dr) for df in (-1, 1) if 0 <= f+df <= 7 and 0 <= r+dr <= 7]


def _can_pawn_defend(board, color, target_sq):
    """True if any friendly pawn could eventually attack target_sq."""
    target_f = chess.square_file(target_sq)
    target_r = chess.square_rank(target_sq)
    attack_r = target_r - 1 if color == chess.WHITE else target_r + 1
    if not (0 <= attack_r <= 7):
        return False
    return any(
        abs(chess.square_file(sq) - target_f) == 1 and
        ((color == chess.WHITE and chess.square_rank(sq) <= attack_r) or
         (color == chess.BLACK and chess.square_rank(sq) >= attack_r))
        for sq in chess.SQUARES
        if board.piece_at(sq) and board.piece_at(sq).color == color
        and board.piece_at(sq).piece_type == chess.PAWN
    )


def detect_weak_square(board, pm, pc_str):
    """4.3.3 — Player's pawn move left a square permanently undefendable by pawns."""
    pc = _cc(pc_str)
    opp = not pc
    moved = board.piece_at(pm.from_square)
    if not moved or moved.piece_type != chess.PAWN:
        return []
    b = board.copy(); b.push(pm)
    for dsq in _pawn_defends(pm.from_square, pc):
        sq_rank = chess.square_rank(dsq)
        if not (2 <= sq_rank <= 5):
            continue
        if _can_pawn_defend(board, pc, dsq) and not _can_pawn_defend(b, pc, dsq):
            if b.is_attacked_by(opp, dsq):
                return [('4.3.3', 0.60, None, 'positional')]
    return []


def _king_shield(board, color):
    ksq = board.king(color)
    if ksq is None:
        return 0
    kf, kr = chess.square_file(ksq), chess.square_rank(ksq)
    dr = 1 if color == chess.WHITE else -1
    return sum(
        1 for df in (-1, 0, 1) for d in (1, 2)
        if 0 <= kf+df <= 7 and 0 <= kr+dr*d <= 7
        and board.piece_at(chess.square(kf+df, kr+dr*d)) and
        board.piece_at(chess.square(kf+df, kr+dr*d)).color == color and
        board.piece_at(chess.square(kf+df, kr+dr*d)).piece_type == chess.PAWN
    )


def detect_pawn_shield_weakened(board, pm, pc_str):
    """4.4.2 — Played move reduced king pawn shield count."""
    pc = _cc(pc_str)
    b = board.copy(); b.push(pm)
    if _king_shield(b, pc) < _king_shield(board, pc):
        return [('4.4.2', 0.75, None, 'positional')]
    return []


def _open_files_near_king(board, color):
    ksq = board.king(color)
    if ksq is None:
        return set()
    kf = chess.square_file(ksq)
    return {
        f for f in (kf-1, kf, kf+1) if 0 <= f <= 7
        if not any(board.piece_at(chess.square(f, r)) and
                   board.piece_at(chess.square(f, r)).color == color and
                   board.piece_at(chess.square(f, r)).piece_type == chess.PAWN
                   for r in range(8))
    }


def detect_open_file_toward_king(board, pm, pc_str):
    """4.4.3 — Played move opened a file adjacent to player's own king."""
    pc = _cc(pc_str)
    b = board.copy(); b.push(pm)
    if _open_files_near_king(b, pc) - _open_files_near_king(board, pc):
        return [('4.4.3', 0.75, None, 'positional')]
    return []


# ══════════════════════════════════════════════════════════════════════════════
# PSYCHOLOGICAL DETECTORS (existing DB columns — no board work)
# ══════════════════════════════════════════════════════════════════════════════

def detect_psychological(row):
    results = []
    if row.get('is_time_pressure_error'):
        results.append(('7.1.2', 0.85, None, 'mathematical'))
    if row.get('is_likely_premove') and row.get('mistake_class') in ('blunder', 'mistake'):
        results.append(('7.3.4', 0.90, None, 'mathematical'))
    return results


# ══════════════════════════════════════════════════════════════════════════════
# MAIN DETECTOR DISPATCH
# ══════════════════════════════════════════════════════════════════════════════

_SPECIFIC_TACTICAL = {
    '3.1.1', '3.1.2', '3.1.3', '3.1.4', '3.1.5', '3.1.6',
    '3.1.7', '3.1.8', '3.1.9', '3.1.10', '3.1.11', '3.1.12',
    '3.1.13', '3.1.14', '3.1.15', '3.2.1', '3.2.2', '3.3.3',
}


def detect_all(row):
    """Run every Layer 1 detector for one move row. Returns deduplicated list."""
    try:
        board = chess.Board(row['fen_before'])
        bm    = chess.Move.from_uci(row['best_move_uci'])
        pm    = chess.Move.from_uci(row['uci'])
    except Exception:
        return []

    if bm not in board.legal_moves:
        return []

    pc  = row['color']
    cpl = row['centipawn_loss']
    pv  = row['pv_line_1']

    patterns = (
        detect_fork(board, bm, pc) +
        detect_pin(board, pm, pc) +
        detect_skewer(board, bm, pc) +
        detect_discovered_attack(board, bm, pc) +
        detect_discovered_check(board, bm, pc) +
        detect_removal_of_defender(board, bm, pc) +
        detect_overloading(board, bm, pc) +
        detect_deflection(board, bm, pc) +
        detect_decoy(board, bm, pc) +
        detect_zwischenzug(board, bm, pc) +
        detect_xray(board, bm, pc) +
        detect_clearance(board, bm, pv) +
        detect_back_rank_mate(board, bm, pc) +
        detect_smothered_mate(board, bm, pc) +
        detect_forcing_move_missed(board, bm, pm, pc) +
        detect_calculation_depth(pv, cpl) +
        detect_quiet_move_missed(board, bm, pc, cpl) +
        detect_piece_activity_loss(board, bm, pm, pc) +
        detect_bad_bishop(board, pm, pc) +
        detect_knight_outpost_missed(board, bm, pm, pc) +
        detect_rook_open_file_missed(board, bm, pm, pc) +
        detect_isolated_pawn(board, pm, pc) +
        detect_doubled_pawn(board, pm, pc) +
        detect_backward_pawn(board, pm, pc) +
        detect_passed_pawn_neglected(board, pm, pc, cpl) +
        detect_weak_square(board, pm, pc) +
        detect_pawn_shield_weakened(board, pm, pc) +
        detect_open_file_toward_king(board, pm, pc) +
        detect_psychological(row)
    )

    # Deduplicate by code — keep highest weight
    by_code = {}
    for code, weight, cpl_attr, method in patterns:
        if code not in by_code or weight > by_code[code][0]:
            by_code[code] = (weight, cpl_attr, method)

    # Demote 3.3.6 (Calculation depth) to secondary when a specific tactical
    # motif is identified. The motif IS the diagnosis; calculation training is
    # only prescribed after the player can see the pattern at all.
    if '3.3.6' in by_code:
        if any(c in _SPECIFIC_TACTICAL for c in by_code if c != '3.3.6'):
            w, ca, m = by_code['3.3.6']
            by_code['3.3.6'] = (min(w, 0.40), ca, m)

    return [(code, w, ca, m) for code, (w, ca, m) in by_code.items()]


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE I/O
# ══════════════════════════════════════════════════════════════════════════════

def _fetch_concept_ids(cur):
    cur.execute("SELECT code, id FROM concepts")
    return dict(cur.fetchall())


def _fetch_moves(cur, game_ids):
    ph = ','.join(['%s'] * len(game_ids))
    cur.execute(f"""
        SELECT
            m.id, m.game_id, m.fen_before, m.uci, m.best_move_uci,
            m.mistake_class, m.centipawn_loss, m.eval_before, m.eval_after,
            m.phase, m.color, m.pv_line_1,
            m.is_time_pressure_error, m.is_likely_premove,
            m.resignation_mindset_flag, m.complacency_flag,
            m.desperation_sacrifice, m.swindle_attempt
        FROM moves m
        WHERE m.game_id IN ({ph})
          AND m.mistake_class IS NOT NULL
          AND m.best_move_uci IS NOT NULL
          AND m.fen_before IS NOT NULL
          AND m.id NOT IN (SELECT DISTINCT move_id FROM move_concepts)
    """, game_ids)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _write_patterns(cur, move_id, patterns, concept_ids, cpl):
    if not patterns:
        return 0
    max_w = max(w for _, w, _, _ in patterns)
    written = 0
    for code, weight, cpl_attr, method in patterns:
        cid = concept_ids.get(code)
        if not cid:
            continue
        is_primary = (weight == max_w)
        cpl_a = cpl_attr if cpl_attr is not None else (int(cpl * weight) if cpl else None)
        cur.execute("""
            INSERT INTO move_concepts
                (move_id, concept_id, attribution_weight, cpl_attributed,
                 detection_method, is_primary_cause)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (move_id, concept_id) DO UPDATE SET
                attribution_weight = EXCLUDED.attribution_weight,
                cpl_attributed     = EXCLUDED.cpl_attributed,
                detection_method   = EXCLUDED.detection_method,
                is_primary_cause   = EXCLUDED.is_primary_cause
        """, (move_id, cid, weight, cpl_a, method, is_primary))
        written += 1
    return written


def _update_tags(cur, move_id, codes):
    if codes:
        cur.execute("UPDATE moves SET pattern_tags = %s WHERE id = %s",
                    (list(codes), move_id))


# ══════════════════════════════════════════════════════════════════════════════
# BATCH RUNNER
# ══════════════════════════════════════════════════════════════════════════════

BATCH_SIZE = 100

def run(game_ids=None):
    conn = get_connection()
    cur  = conn.cursor()
    concept_ids = _fetch_concept_ids(cur)

    if game_ids:
        cur.execute(
            "SELECT id FROM games WHERE analyzed = TRUE AND id = ANY(%s) ORDER BY id",
            (list(game_ids),)
        )
    else:
        cur.execute("SELECT id FROM games WHERE analyzed = TRUE ORDER BY id")
    all_ids = [r[0] for r in cur.fetchall()]

    total_games = len(all_ids)
    moves_done = patterns_done = 0
    blunders_total = blunders_zero = 0
    code_counts = {}
    errors = 0

    print(f"Processing {total_games} games in batches of {BATCH_SIZE}...")

    for start in range(0, total_games, BATCH_SIZE):
        batch = all_ids[start:start + BATCH_SIZE]
        rows  = _fetch_moves(cur, batch)

        for row in rows:
            try:
                patterns = detect_all(row)
            except Exception as e:
                errors += 1
                continue

            mid = row['id']
            if patterns:
                written = _write_patterns(cur, mid, patterns, concept_ids, row['centipawn_loss'])
                _update_tags(cur, mid, [p[0] for p in patterns])
                patterns_done += written
                for code, *_ in patterns:
                    code_counts[code] = code_counts.get(code, 0) + 1

            if row['mistake_class'] in ('blunder', 'mistake'):
                blunders_total += 1
                if not patterns:
                    blunders_zero += 1

            moves_done += 1

        conn.commit()
        done = min(start + BATCH_SIZE, total_games)
        print(f"  {done}/{total_games} games — {moves_done:,} moves, "
              f"{patterns_done:,} concept tags")

    cur.close()
    conn.close()

    # ── Print summary ──────────────────────────────────────────────────────────
    conn2 = get_connection()
    cur2  = conn2.cursor()
    cur2.execute("SELECT code, name FROM concepts")
    names = dict(cur2.fetchall())
    cur2.close(); conn2.close()

    print()
    print("=" * 65)
    print("LAYER 1 PATTERN DETECTION — SUMMARY")
    print("=" * 65)
    print(f"  Games processed:   {total_games:,}")
    print(f"  Moves processed:   {moves_done:,}")
    print(f"  Concept tags:      {patterns_done:,}")
    if moves_done:
        print(f"  Avg tags/move:     {patterns_done/moves_done:.2f}")
    if errors:
        print(f"  Errors skipped:    {errors}")
    print()
    print(f"  {'Code':<8} {'Name':<38} {'Count':>6}")
    print("  " + "-" * 55)
    for code, cnt in sorted(code_counts.items(), key=lambda x: -x[1]):
        print(f"  {code:<8} {names.get(code, '?'):<38} {cnt:>6,}")
    print()
    if blunders_total:
        pct = 100 * blunders_zero / blunders_total
        print(f"  False negative rate (blunders+mistakes with 0 tags):")
        print(f"  {blunders_zero:,} / {blunders_total:,} = {pct:.1f}%")
    print()


if __name__ == '__main__':
    ids = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else None
    run(ids)
