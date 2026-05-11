"""
seed_lichess_puzzles.py — Download and seed the Lichess Puzzle Database.

Downloads ~300MB compressed CSV, decompresses with zstandard, filters and
seeds drill_positions with ~3-3.5M puzzles covering all concept codes.

USAGE:
  pip install zstandard requests
  python seed_lichess_puzzles.py

  Flags:
    --skip-download    Skip download if puzzle CSV already present locally
    --dry-run          Parse and count only — do not write to DB
    --limit N          Only seed first N puzzles (for testing)

ESTIMATED TIME: 20-40 minutes (download + seed)
ESTIMATED STORAGE: ~1.5-2 GB in PostgreSQL
"""

import csv
import io
import os
import sys
import time
import requests
import zstandard as zstd
from db_setup import get_connection

# ─── Config ───────────────────────────────────────────────────────────────────
PUZZLE_URL    = 'https://database.lichess.org/lichess_db_puzzle.csv.zst'
LOCAL_PATH    = 'lichess_db_puzzle.csv.zst'
BATCH_SIZE    = 10_000
MIN_POPULARITY = 50

# ─── Lichess theme → concept code mapping ────────────────────────────────────
# Primary concept is the FIRST matching theme in this ordered mapping.
# Order matters: more specific patterns come first.
THEME_TO_CODE = {
    # Specific mates (most specific first)
    'smotheredMate':        '3.2.2',
    'arabianMate':          '3.2.3',
    'bodenMate':            '3.2.4',
    'doubleBishopMate':     '3.2.5',
    'hookMate':             '3.2.6',
    'anastasiasMate':       '3.2.7',
    'killBoxMate':          '3.2.8',
    'backRankMate':         '3.2.1',
    'mateIn1':              '3.2.1',
    'mateIn2':              '3.2',
    'mateIn3':              '3.3.6',
    'mateIn4':              '3.3.6',
    'mateIn5':              '3.3.6',
    # Specific tactical motifs
    'doubleCheck':          '3.1.6',
    'discoveredCheck':      '3.1.5',
    'fork':                 '3.1.1',
    'pin':                  '3.1.2',
    'skewer':               '3.1.3',
    'discoveredAttack':     '3.1.4',
    'hangingPiece':         '3.1.7',
    'trappedPiece':         '3.1.7',
    'capturingDefender':    '3.1.7',
    'overloading':          '3.1.8',
    'interference':         '3.1.9',
    'deflection':           '3.1.10',
    'attraction':           '3.1.11',
    'zwischenzug':          '3.1.12',
    'xRayAttack':           '3.1.13',
    'clearance':            '3.1.14',
    # Promotion tactics
    'underPromotion':       '3.4.4',
    'promotion':            '3.4.4',
    # Quiet move
    'quietMove':            '3.4.2',
    'zugzwang':             '4.5.5',
    # Pawn themes
    'passedPawn':           '4.2.4',
    'advancedPawn':         '4.2.4',
    'isolatedPawn':         '4.2.1',
    # King safety
    'exposedKing':          '4.4.2',
    'kingsideAttack':       '4.4.5',
    'queensideAttack':      '4.5.2',
    # Endgames (most specific first)
    'rookEndgame':          '6.2.1',
    'bishopEndgame':        '6.3.2',
    'knightEndgame':        '6.3.3',
    'queenEndgame':         '6.4',
    'pawnEndgame':          '6.1.4',
    'endgame':              '6.1',
    # General tactics (fallbacks)
    'sacrifice':            '2.2.4',
    'long':                 '3.3.6',
    'veryLong':             '3.3.6',
    'crushing':             '3.3.6',
    'mate':                 '3.2.1',
    'oneMove':              '3.2.1',
    # Misc defensive
    'defensiveMove':        '7.1.2',
    'equality':             '7.1.2',
}

# Set of concept codes that REQUIRE a mapping (skip puzzles with only generic codes
# like 'crushing' if they have no more specific theme)
_GENERIC_CODES = {'3.3.6', '7.1.2', '2.2.4', '3.2'}


def themes_to_code(themes_str):
    """
    Map space-separated Lichess themes to our primary concept code.
    Uses the full THEME_TO_CODE map (unvalidated against DB).
    Returns (primary_code, [all_codes]) or (None, []) if no match.
    """
    return _themes_to_code_validated(themes_str, THEME_TO_CODE)


def _themes_to_code_validated(themes_str, theme_map):
    """Map themes using a pre-validated theme_map dict."""
    if not themes_str:
        return None, []
    themes = themes_str.split()
    primary = None
    all_codes = []
    for theme in themes:
        code = theme_map.get(theme)
        if code and code not in all_codes:
            all_codes.append(code)
        if primary is None and code and code not in _GENERIC_CODES:
            primary = code
    if primary is None and all_codes:
        primary = all_codes[0]
    return primary, all_codes


def ensure_columns(cur):
    """Add source/lichess columns and unique index to drill_positions if missing."""
    for col, coltype in [
        ('source',            'TEXT'),
        ('lichess_puzzle_id', 'TEXT'),
        ('puzzle_rating',     'INTEGER'),
    ]:
        cur.execute(f"""
            ALTER TABLE drill_positions
            ADD COLUMN IF NOT EXISTS {col} {coltype}
        """)
    # Full unique index (non-partial) required for ON CONFLICT to work
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_drill_lichess_puzzle_id
        ON drill_positions (lichess_puzzle_id)
    """)


def download_puzzle_db(path):
    """Stream download the compressed puzzle DB."""
    print(f"Downloading Lichess puzzle DB from:")
    print(f"  {PUZZLE_URL}")
    print(f"  Target: {path}")
    r = requests.get(PUZZLE_URL, stream=True, timeout=600)
    r.raise_for_status()
    total = int(r.headers.get('content-length', 0))
    downloaded = 0
    chunk_size = 1024 * 1024  # 1 MB
    start = time.time()
    with open(path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=chunk_size):
            f.write(chunk)
            downloaded += len(chunk)
            elapsed = time.time() - start
            if elapsed > 0 and downloaded % (10 * chunk_size) < chunk_size:
                pct = downloaded / total * 100 if total else 0
                mb  = downloaded / 1024 / 1024
                print(f"  {mb:.0f}MB  {pct:.0f}%  {mb/elapsed:.1f} MB/s")
    print(f"  Download complete: {downloaded/1024/1024:.0f}MB in {elapsed:.0f}s")


def seed_puzzles(dry_run=False, limit=None, skip_download=False):
    """Main seeding routine."""

    if not skip_download or not os.path.exists(LOCAL_PATH):
        download_puzzle_db(LOCAL_PATH)
    else:
        print(f"Using existing local file: {LOCAL_PATH}")

    print()
    print("Parsing and seeding puzzles...")

    conn = get_connection()
    cur  = conn.cursor()

    if not dry_run:
        ensure_columns(cur)
        conn.commit()

    # Fetch valid concept codes (FK constraint — only insert codes that exist)
    cur.execute("SELECT code FROM concepts")
    valid_codes = {r[0] for r in cur.fetchall()}
    print(f"  Valid concept codes in DB: {len(valid_codes)}")

    # Filter THEME_TO_CODE to only valid codes
    valid_theme_map = {t: c for t, c in THEME_TO_CODE.items() if c in valid_codes}
    invalid = {c for c in THEME_TO_CODE.values() if c not in valid_codes}
    if invalid:
        print(f"  WARNING: {len(invalid)} codes in theme map not in concepts table: {sorted(invalid)}")
        print(f"           These themes will be skipped.")

    # Open and decompress
    dctx = zstd.ZstdDecompressor()
    batch    = []
    accepted = 0
    rejected = 0
    skipped  = 0
    t_start  = time.time()

    with open(LOCAL_PATH, 'rb') as fh:
        stream = dctx.stream_reader(fh)
        text   = io.TextIOWrapper(stream, encoding='utf-8')
        reader = csv.DictReader(text)

        for row in reader:
            if limit and (accepted + rejected) >= limit:
                break

            # Popularity filter
            try:
                popularity = int(row.get('Popularity', 0))
            except (ValueError, TypeError):
                popularity = 0
            if popularity <= MIN_POPULARITY:
                rejected += 1
                continue

            # Theme mapping (validated against DB codes)
            themes_str = row.get('Themes', '')
            primary_code, all_codes = _themes_to_code_validated(
                themes_str, valid_theme_map)
            if not primary_code:
                rejected += 1
                continue

            # Parse fields
            try:
                rating = int(row['Rating'])
                puzzle_id = row['PuzzleId']
                fen = row['FEN']
                moves = row['Moves'].strip().split()
            except (KeyError, ValueError):
                skipped += 1
                continue

            if not moves or not fen:
                skipped += 1
                continue

            correct_move = moves[0]           # first move in solution sequence
            difficulty   = min(1.0, max(0.0, rating / 3000.0))

            if not dry_run:
                batch.append((
                    None,          # player_id (global puzzle)
                    None,          # source_move_id
                    primary_code,  # concept_code
                    fen,
                    correct_move,
                    None,          # correct_move_san
                    difficulty,
                    'lichess_puzzle_db',
                    puzzle_id,
                    rating,
                ))

            accepted += 1

            if not dry_run and len(batch) >= BATCH_SIZE:
                _flush_batch(cur, batch)
                batch.clear()
                conn.commit()
                elapsed = time.time() - t_start
                rate = accepted / elapsed if elapsed > 0 else 0
                print(f"  {accepted:>7,} puzzles seeded  "
                      f"{rejected:>7,} rejected  "
                      f"{rate:.0f}/s")

            elif dry_run and accepted % 100_000 == 0:
                elapsed = time.time() - t_start
                print(f"  [dry-run] {accepted:>7,} would be seeded  "
                      f"{rejected:>7,} rejected  "
                      f"elapsed={elapsed:.0f}s")

    # Flush remainder
    if batch and not dry_run:
        _flush_batch(cur, batch)
        conn.commit()

    cur.close()
    conn.close()

    elapsed = time.time() - t_start
    print()
    print("=" * 60)
    print("LICHESS PUZZLE SEED COMPLETE")
    print("=" * 60)
    print(f"  Puzzles seeded:   {accepted:,}")
    print(f"  Rejected:         {rejected:,}  (low popularity or no theme match)")
    print(f"  Skipped (errors): {skipped:,}")
    print(f"  Elapsed:          {elapsed:.0f}s  ({elapsed/60:.1f} min)")
    if accepted:
        print(f"  Rate:             {accepted/elapsed:.0f} puzzles/sec")
    if dry_run:
        print("  [DRY RUN — no data written]")


def _flush_batch(cur, batch):
    cur.executemany("""
        INSERT INTO drill_positions
            (player_id, source_move_id, concept_code, fen,
             correct_move, correct_move_san, difficulty,
             source, lichess_puzzle_id, puzzle_rating)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (lichess_puzzle_id) DO NOTHING
    """, batch)


if __name__ == '__main__':
    dry_run       = '--dry-run'       in sys.argv
    skip_download = '--skip-download' in sys.argv
    limit_arg     = None
    if '--limit' in sys.argv:
        idx = sys.argv.index('--limit')
        if idx + 1 < len(sys.argv):
            limit_arg = int(sys.argv[idx + 1])

    print("=" * 60)
    print("LICHESS PUZZLE DATABASE SEEDER")
    print("=" * 60)
    if dry_run:
        print("  MODE: DRY RUN (no DB writes)")
    if limit_arg:
        print(f"  Limit: {limit_arg:,} puzzles")
    print()

    try:
        import zstandard
    except ImportError:
        print("ERROR: zstandard not installed.")
        print("  Run:  pip install zstandard requests")
        sys.exit(1)

    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed.")
        print("  Run:  pip install requests")
        sys.exit(1)

    seed_puzzles(dry_run=dry_run, limit=limit_arg, skip_download=skip_download)
