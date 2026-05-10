import requests
import chess.pgn
import io
import re
from datetime import datetime, timezone
from db_setup import get_connection

PLATFORM = "chess.com"

def classify_game_type(time_control: str) -> str:
    if not time_control or time_control == "-":
        return "unknown"
    parts = time_control.split("+")
    base = int(parts[0])
    increment = int(parts[1]) if len(parts) > 1 else 0
    estimated = base + (40 * increment)
    if estimated < 180:
        return "bullet"
    elif estimated < 480:
        return "blitz"
    elif estimated < 1500:
        return "rapid"
    else:
        return "classical"

def parse_clock(comment: str) -> int | None:
    match = re.search(r'\[%clk\s+(\d+):(\d+):(\d+)\]', comment)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return (h * 3600 + m * 60 + s) * 1000
    return None

def get_or_create_player(cur, username: str) -> int:
    cur.execute("""
        INSERT INTO players (username, platform)
        VALUES (%s, %s)
        ON CONFLICT (username, platform) DO UPDATE SET username = EXCLUDED.username
        RETURNING id
    """, (username.lower(), PLATFORM))
    return cur.fetchone()[0]

def fetch_archive_urls(username: str) -> list:
    """Get the list of all monthly archive URLs for a player."""
    url = f"https://api.chess.com/pub/player/{username}/games/archives"
    headers = {"User-Agent": "chess-study-engine/0.1 (personal project)"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("archives", [])
    else:
        print(f"Failed to fetch archive list: HTTP {response.status_code}")
        return []

def fetch_games_from_url(url: str) -> list:
    """Fetch all games from a single monthly archive URL."""
    headers = {"User-Agent": "chess-study-engine/0.1 (personal project)"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("games", [])
    else:
        print(f"  Failed to fetch {url}: HTTP {response.status_code}")
        return []

def parse_and_insert_game(cur, game_data: dict, player_id: int, username: str):
    pgn_text = game_data.get("pgn", "")
    if not pgn_text:
        return False

    pgn_io = io.StringIO(pgn_text)
    game = chess.pgn.read_game(pgn_io)
    if not game:
        return False

    headers = game.headers
    source_game_id = game_data.get("url", "").split("/")[-1]
    time_control = game_data.get("time_control", "")
    game_type = classify_game_type(time_control)

    white = headers.get("White", "").lower()
    color = "white" if white == username.lower() else "black"

    if color == "white":
        player_elo = game_data.get("white", {}).get("rating")
        opponent_elo = game_data.get("black", {}).get("rating")
        player_result = game_data.get("white", {}).get("result", "")
    else:
        player_elo = game_data.get("black", {}).get("rating")
        opponent_elo = game_data.get("white", {}).get("rating")
        player_result = game_data.get("black", {}).get("result", "")

    if player_result == "win":
        result = "win"
    elif player_result in ("checkmated", "timeout", "resigned", "lose"):
        result = "loss"
    else:
        result = "draw"

    end_time = game_data.get("end_time")
    played_at = datetime.fromtimestamp(end_time, tz=timezone.utc) if end_time else None

    opening_eco = headers.get("ECO", None)
    opening_name = headers.get("Opening", None)
    total_moves = sum(1 for _ in game.mainline_moves())

    cur.execute("""
        INSERT INTO games (
            player_id, source, source_game_id, played_at, color, result, result_type,
            time_control, game_type, player_elo, opponent_elo,
            opening_eco, opening_name, total_moves, raw_pgn
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (source, source_game_id) DO NOTHING
        RETURNING id
    """, (
        player_id, PLATFORM, source_game_id, played_at, color, result, player_result,
        time_control, game_type, player_elo, opponent_elo,
        opening_eco, opening_name, total_moves, pgn_text
    ))

    row = cur.fetchone()
    if not row:
        return False

    game_id = row[0]
    board = game.board()
    move_in_phase = {"opening": 0, "middlegame": 0, "endgame": 0}
    prev_clocks = {True: None, False: None}

    for move_num, node in enumerate(game.mainline()):
        move = node.move
        comment = node.comment or ""
        clock_ms = parse_clock(comment)
        is_white_turn = board.turn
        move_color = "white" if is_white_turn else "black"
        is_player_move = (move_color == color)

        prev_clock = prev_clocks[is_white_turn]
        time_spent = (prev_clock - clock_ms) if (clock_ms is not None and prev_clock is not None) else None

        piece_count = len(board.piece_map())
        if move_num < 12:
            phase = "opening"
        elif piece_count <= 10:
            phase = "endgame"
        else:
            phase = "middlegame"

        move_in_phase[phase] += 1
        fen_before = board.fen()
        board.push(move)
        fen_after = board.fen()

        if is_player_move:
            p_clock_before, p_clock_after, p_time_spent = prev_clock, clock_ms, time_spent
            o_clock_before, o_clock_after, o_time_spent = None, None, None
        else:
            p_clock_before, p_clock_after, p_time_spent = None, None, None
            o_clock_before, o_clock_after, o_time_spent = prev_clock, clock_ms, time_spent

        cur.execute("""
            INSERT INTO moves (
                game_id, player_id, move_number, color, san, uci,
                fen_before, fen_after,
                clock_before_ms, clock_after_ms, time_spent_ms,
                opponent_clock_before_ms, opponent_clock_after_ms, opponent_time_spent_ms,
                phase, move_in_phase
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            game_id, player_id,
            (move_num // 2) + 1,
            move_color,
            node.san(),
            move.uci(),
            fen_before, fen_after,
            p_clock_before, p_clock_after, p_time_spent,
            o_clock_before, o_clock_after, o_time_spent,
            phase, move_in_phase[phase]
        ))

        prev_clocks[is_white_turn] = clock_ms

    return True

def import_all_games(username: str):
    conn = get_connection()
    cur = conn.cursor()

    player_id = get_or_create_player(cur, username)
    conn.commit()

    print(f"Fetching archive list for {username}...")
    archive_urls = fetch_archive_urls(username)
    print(f"Found {len(archive_urls)} monthly archives.\n")

    total_inserted = 0
    total_skipped = 0
    total_errors = 0

    for url in archive_urls:
        # Extract year/month from URL for display
        parts = url.rstrip("/").split("/")
        year, month = parts[-2], parts[-1]
        print(f"Processing {year}/{month}...", end=" ")

        games = fetch_games_from_url(url)
        inserted = 0
        skipped = 0

        for game_data in games:
            try:
                result = parse_and_insert_game(cur, game_data, player_id, username)
                if result:
                    inserted += 1
                else:
                    skipped += 1
                conn.commit()
            except Exception as e:
                total_errors += 1
                conn.rollback()

        total_inserted += inserted
        total_skipped += skipped
        print(f"{inserted} inserted, {skipped} skipped.")

    cur.close()
    conn.close()
    print(f"\nComplete. {total_inserted} games inserted, {total_skipped} skipped, {total_errors} errors.")

if __name__ == "__main__":
    import_all_games("StickDoggin")