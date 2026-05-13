"""One-time setup: add solution_depth to drill_positions and create player_calculation_profile."""
import psycopg

conn = psycopg.connect(host='127.0.0.1', port=5432, dbname='chess_engine',
                       user='postgres', password='0088')
cur = conn.cursor()

# 1a: Add solution_depth column
cur.execute('ALTER TABLE drill_positions ADD COLUMN IF NOT EXISTS solution_depth INTEGER')
conn.commit()
print('solution_depth column added')

cur.execute("""
    UPDATE drill_positions
    SET solution_depth = array_length(string_to_array(trim(correct_move), ' '), 1)
    WHERE source = 'lichess_puzzle_db'
      AND correct_move IS NOT NULL
      AND solution_depth IS NULL
""")
rows = cur.rowcount
conn.commit()
print(f'Updated {rows:,} rows with solution_depth')

cur.execute("""
    SELECT solution_depth, COUNT(*) AS cnt
    FROM drill_positions
    WHERE source = 'lichess_puzzle_db' AND solution_depth IS NOT NULL
    GROUP BY solution_depth
    ORDER BY solution_depth
    LIMIT 15
""")
print('Depth distribution:')
for r in cur.fetchall():
    print(f'  depth={r[0]}: {r[1]:,} puzzles')

# 1b: Create player_calculation_profile
cur.execute("""
    CREATE TABLE IF NOT EXISTS player_calculation_profile (
        player_id       INTEGER REFERENCES players(id),
        game_type       TEXT NOT NULL DEFAULT 'rapid',
        max_depth_solved INTEGER DEFAULT 0,
        avg_depth_solved FLOAT DEFAULT 0.0,
        depth_ceiling   INTEGER DEFAULT 3,
        sessions_count  INTEGER DEFAULT 0,
        updated_at      TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (player_id, game_type)
    )
""")
conn.commit()
print('player_calculation_profile table created')

cur.execute("""
    INSERT INTO player_calculation_profile (player_id, game_type)
    VALUES (1, 'rapid'), (1, 'blitz'), (1, 'bullet'), (1, 'classical')
    ON CONFLICT DO NOTHING
""")
conn.commit()
print('Seeded player_calculation_profile for player 1')

# 1e: Update concept_study_mapping for 3.3.6.c
cur.execute("""
    UPDATE concept_study_mapping
    SET study_subtype = 'progressive_depth_visualization'
    WHERE concept_code = '3.3.6.c'
""")
updated = cur.rowcount
conn.commit()
print(f'Updated 3.3.6.c study_subtype: {updated} rows')

# 1e: Create concept_instructions table
cur.execute("""
    CREATE TABLE IF NOT EXISTS concept_instructions (
        concept_code  TEXT PRIMARY KEY REFERENCES concepts(code),
        instruction   TEXT NOT NULL,
        why_it_works  TEXT,
        example       TEXT
    )
""")
conn.commit()
print('concept_instructions table created')

instructions = [
    # Subtypes 3.3.6.a-d
    ('3.3.6.a',
     'Practice 2-3 move forcing sequences. Start every calculation by scanning checks, captures, and threats. Ask: what forcing move do I have RIGHT NOW?',
     'Short forcing sequences are the most commonly missed tactics at club level. Pattern recognition for 2-3 move sequences becomes automatic with volume repetition.',
     'Position has a knight fork in 2 moves (Nxf7+ Kxf7, Nd6+). Player missed it and played a developing move instead.'),

    ('3.3.6.b',
     'Train yourself to see quiet preparatory moves that SET UP tactics. Before looking for the combination, find the quiet move that makes it work.',
     'The hardest part of tactics is not the combination itself but finding the quiet first move. This is where strong players separate from club players — they see quiet setups.',
     'Rd1 (quiet rook lift) makes Rxd7+ decisive two moves later. Player saw the Rxd7 combination but not that Rd1 was needed first.'),

    ('3.3.6.c',
     'Build your calculation depth through progressive puzzle training. Start with 3-move combinations until 85%+ solve rate, then advance to 4-move, then 5+. Visualize each branch completely before moving on.',
     'Calculation depth is a trainable skill, not talent. Systematic depth-progressive training with visualization exercises increases the number of moves a player can hold in working memory.',
     '5-ply sequence: Bxh7+ Kxh7, Ng5+ Kg8, Qh5 (threatening Qxf7#, Qh7#). Player saw Bxh7 but could not complete the full sequence.'),

    ('3.3.6.d',
     'Practice defensive calculation — finding moves that reduce your opponent\'s threats rather than creating your own. When losing, calculate what your opponent WANTS to do and find the move that disrupts their plan.',
     'Defensive calculation is cognitively harder than attacking calculation because it requires predicting opponent intentions. Players under pressure skip defensive calculation and hope for the best.',
     'Down material, player has Rxe4 that deflects the attacking rook. Instead played a passive move and allowed the attack to continue.'),

    # Subtypes 3.4.2.a-f
    ('3.4.2.a',
     'Before every move, ask: what is my opponent threatening on their next turn? Find the move that prevents their best plan while improving your position. This is prophylaxis.',
     'Prophylaxis is the #1 distinguishing skill between 1600 and 1900+ players. Asking "what does my opponent want?" before every move eliminates a huge class of positional errors.',
     'Opponent has a knight that wants to land on f4. h3 prevents this and maintains king safety. Player instead played an attacking move and allowed Nf4 next move.'),

    ('3.4.2.b',
     'Identify your worst-placed piece and find the maneuver to improve it. Look for centralized squares, open files, and outposts. One well-placed piece is worth more than two passive ones.',
     'Piece activity is the most reliable positional metric at club level. Consistently improving your weakest piece is a habit that compounds over time.',
     'Knight on a3 is completely passive. Na3-c2-e3-f5 outpost maneuver over 4 moves. Player missed the maneuver and played on the kingside instead.'),

    ('3.4.2.c',
     'Look for moves that look quiet but set up a decisive tactical threat on the next move. These are "Type A combinations" — the quiet first move is the hardest part.',
     'Type A combinations account for ~14% of all quiet move failures. Training pattern recognition for quiet setup moves produces the highest ROI for improving tactical ability.',
     'h4 (quiet pawn push) creates a discovered attack threat and limits king escape squares, making Rxh7+ decisive. Player missed h4 and played a direct attack that was defended.'),

    ('3.4.2.d',
     'Before pushing a pawn, calculate: does this leave any passed pawn or isolated pawn weakness? Check if the pawn break creates a structural advantage or just creates weaknesses.',
     'Pawn structure mistakes are permanent — unlike piece placement, pawns cannot move backwards. Each structural decision echoes for the rest of the game.',
     'e5 pawn break creates a passed d-pawn but also creates a backwards c-pawn. Calculate whether your compensation is real before pushing.'),

    ('3.4.2.e',
     'Always assess king safety before making quiet moves in the middlegame. Play a king safety move (luft, rook lift, defensive piece) before launching an attack.',
     'The most common reason attacks fail is that the defending side creates a counter-attack. A defended king cannot be attacked. Spending one move on king safety typically saves 3-5 moves of defensive scrambling.',
     'Playing g3 (luft) before Nf5 attack means Qh4+ threats are always answered by Kg2. Player skipped g3 and had to spend 2 tempo defending after Qh4+.'),

    ('3.4.2.f',
     'In endgames, play slowly and precisely. Avoid pawn moves that give your opponent tempo or create zugzwang for yourself. Pass with quiet king moves when your opponent must weaken themselves.',
     'Endgame technique is about converting advantages, not creating them. In K+P endgames especially, a single wasted tempo often means the difference between a win and a draw.',
     'King opposition endgame: waiting move Ke3 (instead of marching forward prematurely) forces opponent king to give way, allowing pawn to advance.'),

    # Top 5 weaknesses
    ('7.3.1',
     'Recognize tilt early: 3+ consecutive losses in a session = stop and reset. Take a 15-minute break, drink water, walk around. Come back with a clear head or quit for the day.',
     'Tilt is neurological — continued play under stress reduces executive function (the prefrontal cortex that governs calculation). One tilt game undoes the benefit of 3 normal games.',
     'Session score: -3 games in a row. Average CPL jumped from 45 to 120. Best move: close the browser.'),

    ('7.1.1',
     'Play your best chess in the first 4 games of any session, then stop or take a break. Track your accuracy across games 1-4 vs 5+. If you see fatigue patterns, enforce a hard 4-game limit.',
     'Calculation ability degrades measurably after 60-90 minutes of play. The brain\'s glycogen stores for executive function are limited. Regular short breaks maintain accuracy better than long sessions.',
     'Games 1-3: avg CPL 38. Games 4-6: avg CPL 67. Games 7+: avg CPL 94. The pattern is consistent and predictable.'),

    ('3.4.2',
     'Before playing a quiet move, always answer: (1) What does this move prevent? (2) What new threat does this create? (3) Is my king safe enough for this to work? If you cannot answer all three, look for a better move.',
     'Quiet move failures represent the largest single Elo impact weakness in your profile (+50 Elo estimated). The systematic approach above adds 15-30 seconds per quiet move decision, but saves games.',
     'Quiet moves account for 60-70% of all moves in a chess game. Improving your quiet move decision quality compounds across every game.'),

    ('3.3.3',
     'In every position, before playing your move, scan for forcing moves: Checks (all of them), Captures (all of them), Threats (what would you love to do in 1 move?). This is the CCT scan.',
     'The CCT (Checks-Captures-Threats) scan is the #1 tactical tool. It takes 10-15 seconds. Done before every move, it eliminates the majority of missed tactical opportunities.',
     'Knight can fork king and queen with Ne7+. CCT scan finds checks first → Ne7+ discovered. Without CCT, player plays a development move and misses the fork.'),

    ('3.1.1',
     'After your opponent\'s move, before calculating your response, check: can any of my pieces fork two of their pieces? Look specifically for knight fork patterns and queen-king configurations.',
     'Fork patterns at club level are primarily missed not because the position is complex but because the player never looked. Systematic scanning eliminates this class of error entirely.',
     'Knight on d5 can fork Kf6 and Rb7 with Nc7+. After opponent\'s last move created this configuration, player did CCT scan (Checks: Nc7+!) and found it.')
]

cur.executemany("""
    INSERT INTO concept_instructions (concept_code, instruction, why_it_works, example)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (concept_code) DO UPDATE SET
        instruction  = EXCLUDED.instruction,
        why_it_works = EXCLUDED.why_it_works,
        example      = EXCLUDED.example
""", instructions)
conn.commit()
print(f'Inserted/updated {len(instructions)} concept instructions')

cur.close()
conn.close()
print('Done.')
