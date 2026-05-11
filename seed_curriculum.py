"""Seed concepts + concept_study_mapping from Chess King University curriculum."""
from db_setup import get_connection

conn = get_connection()
cur  = conn.cursor()

# ── New concepts ───────────────────────────────────────────────────────────────
new_concepts = [
    ('3.1.15', '3.1', 'Destruction of pawn shelter', 'tactics',
     '138 exercises in CT-ART 4.0 (Level 5-8, 1200-2400). Tactical demolition of '
     'the opponent king pawn cover via forced sacrifices. Distinct from positional '
     'pawn shield weakening (4.4.2) — this is an immediate forcing sequence.'),
    ('3.4.4', '3.4', 'Pawn promotion tactics', 'tactics',
     '52 exercises in CT-ART 4.0. Queening combinations, underpromotion to knight '
     'for fork/check, promotion races.'),
    ('3.4.5', '3.4', 'Trapping and encirclement', 'tactics',
     'Blocking all retreat squares of an opponent piece to trap it and win material. '
     'Distinct from removal of defender.'),
    ('3.4.6', '3.4', 'Stalemate trap', 'tactics',
     'Deliberately steering toward stalemate as a defensive resource when losing; '
     'also avoiding stalemate when winning. Key practical defensive technique.'),
    ('3.4.7', '3.4', 'Opening of a file', 'tactics',
     'Tactical pawn sacrifice to immediately open a file toward the opponent king. '
     'Near 4.4.3 but is a forcing sequence rather than a positional consequence.'),
    ('3.4.8', '3.4', 'Pursuit', 'tactics',
     'Chasing a valuable opponent piece across the board to force material loss.'),
    ('3.4.9', '3.4', 'Combination of tactical methods', 'tactics',
     'Multi-tactic sequences combining two or more motifs (e.g. decoy + fork, '
     'pin + removal of defender). Requires recognizing interplay between motifs.'),
    ('4.5.8', '4.5', 'Karlsbad pawn structure', 'positional',
     'Pawn structure from Caro-Kann/QGD: c3/d4 vs c6/d5. Classic plan: White '
     'minority attack b4-b5xc6. 48 exercises in Chess Middlegame I (GM Kalinin).'),
    ('4.5.9', '4.5', 'Hedgehog formation', 'positional',
     'Black pawn structure a6/b6/e6 vs White space advantage. Elastic setup with '
     'latent counterattack potential. Arises from Sicilian English. 44 exercises.'),
    ('4.5.10', '4.5', 'Mobile center', 'positional',
     'Pawn center that can advance (e4-e5 or d4-d5) to create space and restrict '
     'opponent pieces. Key plan in King Indian, Dutch, Sicilian. 58 exercises.'),
]

cur.executemany(
    'INSERT INTO concepts (code, parent_code, name, category, description) '
    'VALUES (%s, %s, %s, %s, %s) ON CONFLICT (code) DO NOTHING',
    new_concepts
)
print(f'New concepts inserted: {cur.rowcount}')

# ── concept_study_mapping ──────────────────────────────────────────────────────
mappings = [
    # FUNDAMENTALS
    ('1.1',    'tactical_drill',   'piece_movement',          0,    400,  0.90),
    ('1.2',    'tactical_drill',   'captures_basics',         0,    400,  0.90),
    # BASIC TACTICS
    ('3.1.6',  'tactical_drill',   'discovered_check',        200,  800,  0.85),
    ('3.2.9',  'tactical_drill',   'lawnmower_mate',          200,  600,  0.80),
    ('3.1.7',  'tactical_drill',   'hanging_pieces',          600,  1000, 0.90),
    ('3.1.1',  'tactical_drill',   'fork',                    600,  1000, 0.92),
    ('3.1.1',  'tactical_drill',   'fork_advanced',           1000, 1800, 0.90),
    ('3.1.2',  'tactical_drill',   'pin',                     600,  1000, 0.88),
    ('3.1.2',  'tactical_drill',   'pin_advanced',            1000, 2000, 0.85),
    ('3.1.4',  'tactical_drill',   'discovered_attack',        800, 2000, 0.87),
    ('3.4.2',  'tactical_drill',   'quiet_move_recognition',   400, 2400, 0.82),
    ('3.2.1',  'tactical_drill',   'mate_in_1',               200,  1200, 0.95),
    # INTERMEDIATE TACTICS
    ('3.2.1',  'tactical_drill',   'defend_against_mate',     1000, 1200, 0.85),
    ('3.2',    'tactical_drill',   'forced_mate_in_2',        1000, 1400, 0.90),
    ('3.1.7',  'tactical_drill',   'undermining',             1000, 1200, 0.87),
    ('3.1.5',  'tactical_drill',   'discovered_check_adv',    1000, 1200, 0.80),
    ('3.1.8',  'tactical_drill',   'overloading',             1000, 2000, 0.83),
    ('3.1.13', 'tactical_drill',   'xray_attack',             1400, 2200, 0.80),
    # ADVANCED TACTICS
    ('3.1.10', 'tactical_drill',   'deflection',              1200, 2000, 0.88),
    ('3.1.11', 'tactical_drill',   'decoy',                   1200, 2000, 0.87),
    ('3.1.9',  'tactical_drill',   'interference',            1200, 1400, 0.82),
    ('3.3.6',  'tactical_drill',   'forced_mate_in_2_adv',    1200, 1400, 0.85),
    ('3.3.6',  'tactical_drill',   'forced_mate_3_4',         1600, 1800, 0.88),
    # NEW — validated by exercise counts
    ('3.1.15', 'tactical_drill',   'pawn_shelter_demolition', 1200, 2400, 0.88),
    ('3.1.12', 'tactical_drill',   'zwischenzug',             1200, 2000, 0.83),
    ('3.4.4',  'tactical_drill',   'pawn_promotion_tactics',  1000, 1800, 0.80),
    ('3.4.5',  'tactical_drill',   'trapping_encirclement',   1200, 1800, 0.78),
    ('3.4.6',  'endgame_drill',    'stalemate_trap',          1000, 1600, 0.82),
    ('3.4.7',  'tactical_drill',   'file_opening_sacrifice',  1200, 1800, 0.80),
    ('3.4.8',  'tactical_drill',   'pursuit',                 1000, 1600, 0.75),
    ('3.4.9',  'tactical_drill',   'multi_tactic_combo',      1400, 2400, 0.88),
    # CALCULATION
    ('3.3.1',  'tactical_drill',   'calculation_training',    1600, 1800, 0.90),
    ('3.3.6',  'tactical_drill',   'calculation_depth',       1600, 2400, 0.92),
    # PAWN STRUCTURE
    ('4.2',    'positional_drill', 'pawn_structure_basics',   200,  600,  0.70),
    ('4.2.1',  'positional_drill', 'isolated_pawn',           1600, 1800, 0.82),
    ('4.2.8',  'positional_drill', 'hanging_pawns',           1600, 1800, 0.78),
    ('4.2.4',  'positional_drill', 'passed_pawn',             1200, 1600, 0.80),
    # POSITIONAL STRATEGY
    ('4.3.1',  'positional_drill', 'center_control',          1200, 1400, 0.78),
    ('4.1.5',  'positional_drill', 'open_lines_diagonals',    1200, 1400, 0.80),
    ('4.5.5',  'positional_drill', 'blockade',                1400, 1600, 0.75),
    ('4.3.3',  'positional_drill', 'weak_squares',            1400, 1600, 0.82),
    ('4.3.2',  'positional_drill', 'space_advantage',         1400, 1600, 0.75),
    ('2.2.4',  'positional_drill', 'exchange_sacrifice',      1400, 1600, 0.78),
    ('4.5.2',  'positional_drill', 'attacking_queenside',     1800, 2000, 0.72),
    ('4.4.5',  'positional_drill', 'attack_on_king',          1600, 1800, 0.80),
    ('4.5.8',  'positional_drill', 'karlsbad_structure',      1200, 1600, 0.78),
    ('4.5.9',  'positional_drill', 'hedgehog_formation',      1400, 1800, 0.75),
    ('4.5.10', 'positional_drill', 'mobile_center',           1200, 1600, 0.78),
    # ENDGAMES — rook endings boosted: 630 exercises = #1 endgame category
    ('6.1.4',  'endgame_drill',    'pawn_endgame_basics',     1000, 1200, 0.85),
    ('6.1.1',  'endgame_drill',    'rule_of_the_square',      1000, 1200, 0.83),
    ('6.1',    'endgame_drill',    'king_pawn_vs_king',        1000, 1200, 0.88),
    ('6.1',    'endgame_drill',    'pawn_endgame_principles',  1000, 1200, 0.85),
    ('6.1.4',  'endgame_drill',    'pawn_vs_pawn',             1000, 1200, 0.80),
    ('6.3.3',  'endgame_drill',    'knight_endings_basics',    1200, 1600, 0.82),
    ('6.3.3',  'endgame_drill',    'knight_endings_adv',       1400, 1600, 0.80),
    ('6.2.4',  'endgame_drill',    'rook_vs_pawns',            1200, 1400, 0.83),
    ('6.2',    'endgame_drill',    'pawn_endings_strategy',    1400, 1600, 0.85),
    ('6.2.1',  'endgame_drill',    'rook_pawn_vs_rook',        1400, 1600, 0.88),
    ('6.3.2',  'endgame_drill',    'bishop_same_color',        1400, 1600, 0.82),
    ('6.1',    'endgame_drill',    'multi_pawn_endings',       1200, 1400, 0.80),
    ('6.3.2',  'endgame_drill',    'bishop_opp_color',         1600, 1800, 0.83),
    ('6.2.1',  'endgame_drill',    'rook_endings_lucena',      1600, 1800, 0.92),
    ('6.2.2',  'endgame_drill',    'rook_endings_philidor',    1600, 1800, 0.92),
    ('6.2',    'endgame_drill',    'rook_endings_priority',    1600, 2000, 0.92),
    ('6.4',    'endgame_drill',    'queen_endings',            1600, 1800, 0.80),
    ('6.1',    'endgame_drill',    'middlegame_play',          1600, 1800, 0.78),
    ('6.2',    'endgame_drill',    'rook_endings_adv',         1800, 2000, 0.92),
    ('6.3.1',  'endgame_drill',    'rook_vs_bishop',           2000, 2200, 0.82),
    ('6.3.1',  'endgame_drill',    'rook_vs_knight',           2000, 2200, 0.82),
    ('6.3.1',  'endgame_drill',    'bishop_vs_knight',         2200, 2400, 0.85),
    ('6.4.2',  'endgame_drill',    'defense_counterattack',    2000, 2200, 0.75),
    # MATING PATTERNS
    ('3.2.9',  'tactical_drill',   'mate_with_queen',          600,  800,  0.85),
    ('3.2.9',  'tactical_drill',   'mate_with_rook',           600,  800,  0.82),
    ('3.2.1',  'tactical_drill',   'mate_in_1_multi',          600, 1000,  0.88),
    # OPENING
    ('5.1',    'opening_drill',    'basic_principles',         600, 1000,  0.80),
    ('5.2',    'opening_drill',    'main_openings',           1000, 2400,  0.82),
    ('5.2.2',  'opening_drill',    'sicilian_structures',     1200, 1800,  0.82),
    ('5.2.1',  'opening_drill',    'kings_indian_plans',      1200, 1800,  0.80),
    ('5.2.2',  'opening_drill',    'caro_kann_karlsbad',      1000, 1600,  0.80),
    ('5.2.3',  'opening_drill',    'dutch_hedgehog',          1200, 1800,  0.75),
    ('5.2.1',  'opening_drill',    'ruy_lopez_plans',         1000, 1600,  0.78),
    # PSYCHOLOGICAL
    ('7.1.2',  'psychological',    'draw_recognition',         200,  600,  0.70),
    ('7.3.1',  'psychological',    'calculation_training',    1600, 2400,  0.85),
]

cur.executemany(
    '''INSERT INTO concept_study_mapping
           (concept_code, study_module, study_subtype, elo_bracket_min, elo_bracket_max, effectiveness_score)
       VALUES (%s, %s, %s, %s, %s, %s)
       ON CONFLICT (concept_code, study_module, study_subtype) DO UPDATE SET
           elo_bracket_min     = EXCLUDED.elo_bracket_min,
           elo_bracket_max     = EXCLUDED.elo_bracket_max,
           effectiveness_score = EXCLUDED.effectiveness_score''',
    mappings
)
print(f'concept_study_mapping rows upserted: {cur.rowcount}')

conn.commit()
cur.execute('SELECT COUNT(*) FROM concept_study_mapping')
print(f'Total concept_study_mapping rows: {cur.fetchone()[0]}')
cur.execute('SELECT COUNT(*) FROM concepts')
print(f'Total concepts: {cur.fetchone()[0]}')
cur.close()
conn.close()
