import psycopg
from db_setup import get_connection

CONCEPTS = [
    # 1. FUNDAMENTAL RULES
    ("1",       None,   "Fundamental Rules",                    "fundamentals",     "Core rules of chess"),
    ("1.1",     "1",    "Piece movement and capture",           "fundamentals",     "How each piece moves and captures"),
    ("1.2",     "1",    "Special moves",                        "fundamentals",     "Castling, en passant, promotion"),
    ("1.3",     "1",    "Check, checkmate, stalemate",          "fundamentals",     "Game-ending and check conditions"),
    ("1.4",     "1",    "Draw conditions",                      "fundamentals",     "50-move rule, repetition, insufficient material"),
    ("1.5",     "1",    "Touch-move and illegal moves",         "fundamentals",     "Over-the-board rules"),

    # 2. MATERIAL
    ("2",       None,   "Material",                             "material",         "Piece values and material balance"),
    ("2.1",     "2",    "Piece values",                         "material",         "Relative and contextual piece values"),
    ("2.2",     "2",    "Material imbalances",                  "material",         "Trading different types of pieces"),
    ("2.2.1",   "2.2",  "Rook vs two minor pieces",             "material",         "Exchange imbalance evaluation"),
    ("2.2.2",   "2.2",  "Queen vs rook and minor piece",        "material",         "Queen vs rook+minor imbalance"),
    ("2.2.3",   "2.2",  "Bishop pair advantage",                "material",         "Two bishops vs bishop+knight or two knights"),
    ("2.2.4",   "2.2",  "Exchange sacrifice",                   "material",         "Deliberate rook for minor piece sacrifice"),
    ("2.3",     "2",    "When to trade pieces",                 "material",         "Deciding when trades benefit your position"),

    # 3. TACTICS
    ("3",       None,   "Tactics",                              "tactics",          "Short-term forcing sequences"),
    ("3.1",     "3",    "Basic tactical motifs",                "tactics",          "Fundamental tactical patterns"),
    ("3.1.1",   "3.1",  "Fork",                                 "tactics",          "Attacking two pieces simultaneously"),
    ("3.1.2",   "3.1",  "Pin",                                  "tactics",          "Absolute and relative pins"),
    ("3.1.3",   "3.1",  "Skewer",                               "tactics",          "Forcing a valuable piece to move, exposing another"),
    ("3.1.4",   "3.1",  "Discovered attack",                    "tactics",          "Unmasking an attack by moving another piece"),
    ("3.1.5",   "3.1",  "Discovered check",                     "tactics",          "Unmasking a check by moving another piece"),
    ("3.1.6",   "3.1",  "Double check",                         "tactics",          "Two pieces giving check simultaneously"),
    ("3.1.7",   "3.1",  "Removal of the defender",              "tactics",          "Capturing or driving away a key defending piece"),
    ("3.1.8",   "3.1",  "Overloading",                          "tactics",          "Giving one piece too many defensive duties"),
    ("3.1.9",   "3.1",  "Interference",                         "tactics",          "Blocking a piece's defensive line"),
    ("3.1.10",  "3.1",  "Deflection",                           "tactics",          "Forcing a defender away from a key square"),
    ("3.1.11",  "3.1",  "Decoy and lure",                       "tactics",          "Luring a piece to a bad square"),
    ("3.1.12",  "3.1",  "Zwischenzug",                          "tactics",          "An in-between move before the expected reply"),
    ("3.1.13",  "3.1",  "X-ray attack",                         "tactics",          "Attacking through an intervening piece"),
    ("3.1.14",  "3.1",  "Clearance sacrifice",                  "tactics",          "Sacrificing to clear a square or line"),

    # 3.2 MATING PATTERNS
    ("3.2",     "3",    "Mating patterns",                      "tactics",          "Recurring checkmate patterns"),
    ("3.2.1",   "3.2",  "Back-rank mate",                       "tactics",          "Mating on the first or eighth rank"),
    ("3.2.2",   "3.2",  "Smothered mate",                       "tactics",          "Knight mate with king smothered by own pieces"),
    ("3.2.3",   "3.2",  "Scholar's mate",                       "tactics",          "Early queen and bishop attack on f7/f2"),
    ("3.2.4",   "3.2",  "Anastasia's mate",                     "tactics",          "Knight and rook mating pattern"),
    ("3.2.5",   "3.2",  "Arabian mate",                         "tactics",          "Knight and rook in the corner"),
    ("3.2.6",   "3.2",  "Boden's mate",                         "tactics",          "Two criss-crossing bishops"),
    ("3.2.7",   "3.2",  "Epaulette mate",                       "tactics",          "King blocked by its own rooks"),
    ("3.2.8",   "3.2",  "Hook mate",                            "tactics",          "Rook, knight, and pawn mating pattern"),
    ("3.2.9",   "3.2",  "Ladder mate",                          "tactics",          "Two rooks delivering checkmate in sequence"),
    ("3.2.10",  "3.2",  "Opera mate",                           "tactics",          "Rook and bishop mating pattern"),
    ("3.2.11",  "3.2",  "Legal's mate",                         "tactics",          "Queen sacrifice leading to knight mate"),
    ("3.2.12",  "3.2",  "King hunt",                            "tactics",          "Chasing the king across the board to mate"),

    # 3.3 CALCULATION
    ("3.3",     "3",    "Calculation",                          "tactics",          "Thinking ahead accurately"),
    ("3.3.1",   "3.3",  "Candidate move generation",            "tactics",          "Identifying all reasonable moves to consider"),
    ("3.3.2",   "3.3",  "Tree pruning",                         "tactics",          "Eliminating bad lines early in calculation"),
    ("3.3.3",   "3.3",  "Forcing moves first",                  "tactics",          "Checks, captures, and threats as priorities"),
    ("3.3.4",   "3.3",  "Counting attackers and defenders",     "tactics",          "Material count on a contested square"),
    ("3.3.5",   "3.3",  "Prophylactic thinking",                "tactics",          "Finding the opponent's best reply"),
    ("3.3.6",   "3.3",  "Calculation depth",                    "tactics",          "Calculating sequences of 2 to 10+ moves"),

    # 3.4 TACTICAL VISION
    ("3.4",     "3",    "Tactical vision",                      "tactics",          "Seeing and sensing tactical possibilities"),
    ("3.4.1",   "3.4",  "Pattern recognition speed",            "tactics",          "Quickly identifying known tactical motifs"),
    ("3.4.2",   "3.4",  "Quiet move recognition",               "tactics",          "Finding non-forcing moves that win"),
    ("3.4.3",   "3.4",  "Defensive tactics",                    "tactics",          "Finding resources in bad positions"),

    # 4. POSITIONAL PRINCIPLES
    ("4",       None,   "Positional Principles",                "positional",       "Long-term strategic concepts"),
    ("4.1",     "4",    "Piece activity and coordination",      "positional",       "Making pieces work together effectively"),
    ("4.1.1",   "4.1",  "Piece centralization",                 "positional",       "Placing pieces on central squares"),
    ("4.1.2",   "4.1",  "Bad bishop",                           "positional",       "Bishop blocked by its own pawns"),
    ("4.1.3",   "4.1",  "Bishop trade decisions",               "positional",       "When to trade good vs bad bishops"),
    ("4.1.4",   "4.1",  "Knight outpost",                       "positional",       "Supported knight on advanced square"),
    ("4.1.5",   "4.1",  "Rook on open file",                    "positional",       "Rook on open or half-open file"),
    ("4.1.6",   "4.1",  "Rook on seventh rank",                 "positional",       "Rook dominating the seventh rank"),
    ("4.1.7",   "4.1",  "Doubled rooks",                        "positional",       "Two rooks on the same file or rank"),
    ("4.1.8",   "4.1",  "Queen activity vs exposure",           "positional",       "Balancing queen activity with safety"),
    ("4.1.9",   "4.1",  "King as active piece",                 "positional",       "Using the king actively in endgames"),

    # 4.2 PAWN STRUCTURE
    ("4.2",     "4",    "Pawn structure",                       "positional",       "Pawn formations and their implications"),
    ("4.2.1",   "4.2",  "Isolated pawn",                        "positional",       "IQP: attacking and defending with it"),
    ("4.2.2",   "4.2",  "Doubled pawns",                        "positional",       "Two pawns on the same file"),
    ("4.2.3",   "4.2",  "Backward pawn",                        "positional",       "Pawn that cannot be supported by other pawns"),
    ("4.2.4",   "4.2",  "Passed pawn",                          "positional",       "Pawn with no opposing pawns blocking it"),
    ("4.2.5",   "4.2",  "Pawn chain",                           "positional",       "Attacking the base of a pawn chain"),
    ("4.2.6",   "4.2",  "Pawn majority",                        "positional",       "Queenside vs kingside pawn majority"),
    ("4.2.7",   "4.2",  "Pawn breaks",                          "positional",       "Timing and executing pawn breaks"),
    ("4.2.8",   "4.2",  "Hanging pawns",                        "positional",       "Two adjacent pawns with no pawn support"),
    ("4.2.9",   "4.2",  "Pawn islands",                         "positional",       "Fewer pawn islands is generally better"),
    ("4.2.10",  "4.2",  "Pawn storm",                           "positional",       "Advancing pawns toward the opponent's king"),

    # 4.3 SPACE AND CONTROL
    ("4.3",     "4",    "Space and control",                    "positional",       "Controlling territory on the board"),
    ("4.3.1",   "4.3",  "Center control",                       "positional",       "Classical vs hypermodern center control"),
    ("4.3.2",   "4.3",  "Space advantage",                      "positional",       "Using space without overextending"),
    ("4.3.3",   "4.3",  "Weak squares",                         "positional",       "Creating and exploiting weak squares"),
    ("4.3.4",   "4.3",  "Color complex weakness",               "positional",       "Weakness on all squares of one color"),
    ("4.3.5",   "4.3",  "Territorial restriction",              "positional",       "Keeping opponent pieces passive and cramped"),

    # 4.4 KING SAFETY
    ("4.4",     "4",    "King safety",                          "positional",       "Keeping the king safe from attack"),
    ("4.4.1",   "4.4",  "Castling timing",                      "positional",       "When to castle and to which side"),
    ("4.4.2",   "4.4",  "Pawn shield integrity",                "positional",       "Maintaining pawns in front of the castled king"),
    ("4.4.3",   "4.4",  "Open files toward the king",           "positional",       "Danger of open files near the king"),
    ("4.4.4",   "4.4",  "King in center danger",                "positional",       "Risks of leaving the king uncastled"),
    ("4.4.5",   "4.4",  "Opposite-side castling attacks",       "positional",       "Attacking when kings are on opposite sides"),

    # 4.5 STRATEGIC PLANNING
    ("4.5",     "4",    "Strategic planning",                   "positional",       "Forming and executing long-term plans"),
    ("4.5.1",   "4.5",  "Identifying the critical imbalance",   "positional",       "Finding the key factor that determines the plan"),
    ("4.5.2",   "4.5",  "Minority attack",                      "positional",       "Using fewer pawns to create weaknesses"),
    ("4.5.3",   "4.5",  "Piece reorganization",                 "positional",       "Rerouting pieces to better squares"),
    ("4.5.4",   "4.5",  "Prophylaxis",                          "positional",       "Preventing the opponent's plan"),
    ("4.5.5",   "4.5",  "Zugzwang",                             "positional",       "Position where any move worsens your position"),
    ("4.5.6",   "4.5",  "Fortress construction",                "positional",       "Building an impenetrable defensive setup"),
    ("4.5.7",   "4.5",  "Transformation of advantage",          "positional",       "Converting one type of advantage into another"),

    # 5. OPENING THEORY
    ("5",       None,   "Opening Theory",                       "opening",          "Opening principles and specific lines"),
    ("5.1",     "5",    "Opening principles",                   "opening",          "General rules for the opening phase"),
    ("5.1.1",   "5.1",  "Development priority",                 "opening",          "Getting pieces off the back rank quickly"),
    ("5.1.2",   "5.1",  "Center establishment",                 "opening",          "Controlling the center in the opening"),
    ("5.1.3",   "5.1",  "Early king safety",                    "opening",          "Castling early to protect the king"),
    ("5.1.4",   "5.1",  "Piece harmony in the opening",         "opening",          "Coordinating pieces without blocking each other"),
    ("5.1.5",   "5.1",  "Avoiding premature attacks",           "opening",          "Not attacking before development is complete"),
    ("5.2",     "5",    "Opening families",                     "opening",          "The main opening systems by ECO code"),
    ("5.2.1",   "5.2",  "Open games",                           "opening",          "1.e4 e5 openings"),
    ("5.2.2",   "5.2",  "Semi-open games",                      "opening",          "1.e4 with Black not playing e5"),
    ("5.2.3",   "5.2",  "Closed games",                         "opening",          "1.d4 d5 openings"),
    ("5.2.4",   "5.2",  "Indian defenses",                      "opening",          "1.d4 without d5"),
    ("5.2.5",   "5.2",  "Flank openings",                       "opening",          "English, Reti, and other flank systems"),
    ("5.3",     "5",    "Repertoire concepts",                  "opening",          "Building and managing an opening repertoire"),
    ("5.3.1",   "5.3",  "Transpositions",                       "opening",          "Reaching the same position via different move orders"),
    ("5.3.2",   "5.3",  "Move order subtleties",                "opening",          "Small move order changes with big implications"),
    ("5.3.3",   "5.3",  "Anti-system lines",                    "opening",          "Lines designed to avoid main theory"),
    ("5.3.4",   "5.3",  "Knowing when book ends",               "opening",          "Recognizing when you leave prepared theory"),
    ("5.4",     "5",    "Opening traps and refutations",        "opening",          "Specific traps and how to avoid or use them"),

    # 6. ENDGAME THEORY
    ("6",       None,   "Endgame Theory",                       "endgame",          "Technique and theory for the endgame phase"),
    ("6.1",     "6",    "King and pawn endings",                "endgame",          "The most fundamental endgame type"),
    ("6.1.1",   "6.1",  "Opposition",                           "endgame",          "Direct, distant, and diagonal opposition"),
    ("6.1.2",   "6.1",  "Key squares",                          "endgame",          "Squares the king must reach to promote"),
    ("6.1.3",   "6.1",  "Triangulation",                        "endgame",          "Losing a tempo to gain opposition"),
    ("6.1.4",   "6.1",  "Pawn races",                           "endgame",          "Calculating who promotes first"),
    ("6.1.5",   "6.1",  "Shouldering",                          "endgame",          "Using the king to block the opponent's king"),
    ("6.1.6",   "6.1",  "Rook pawn exceptions",                 "endgame",          "Special drawing rules with rook pawns"),
    ("6.2",     "6",    "Rook endings",                         "endgame",          "The most common endgame type in practice"),
    ("6.2.1",   "6.2",  "Lucena position",                      "endgame",          "Winning technique: building the bridge"),
    ("6.2.2",   "6.2",  "Philidor position",                    "endgame",          "Defensive drawing technique"),
    ("6.2.3",   "6.2",  "Active vs passive rook",               "endgame",          "Keeping the rook active in endings"),
    ("6.2.4",   "6.2",  "Rook behind passed pawn",              "endgame",          "Correct rook placement with passed pawns"),
    ("6.2.5",   "6.2",  "Cutting off the king",                 "endgame",          "Using the rook to restrict the opponent's king"),
    ("6.2.6",   "6.2",  "Back-rank containment",                "endgame",          "Trapping the king on the back rank"),
    ("6.3",     "6",    "Minor piece endings",                  "endgame",          "Bishop and knight endgames"),
    ("6.3.1",   "6.3",  "Bishop vs knight",                     "endgame",          "When each piece is superior"),
    ("6.3.2",   "6.3",  "Same and opposite color bishops",      "endgame",          "Drawing tendencies and winning chances"),
    ("6.3.3",   "6.3",  "Knight endings",                       "endgame",          "Knight endgame technique and outposts"),
    ("6.3.4",   "6.3",  "Wrong color bishop and rook pawn",     "endgame",          "The classic drawing exception"),
    ("6.4",     "6",    "Queen endings",                        "endgame",          "Queen endgame technique"),
    ("6.4.1",   "6.4",  "Queen vs pawn on seventh",             "endgame",          "Winning or drawing queen vs advanced pawn"),
    ("6.4.2",   "6.4",  "Perpetual check defense",              "endgame",          "Using perpetual check to draw"),
    ("6.4.3",   "6.4",  "Queen and pawn endings",               "endgame",          "Technique with queens and pawns remaining"),
    ("6.5",     "6",    "Practical endgame concepts",           "endgame",          "General endgame decision-making"),
    ("6.5.1",   "6.5",  "Simplification decisions",             "endgame",          "Deciding when to trade into an endgame"),
    ("6.5.2",   "6.5",  "Endgame prophylaxis",                  "endgame",          "Preventing the opponent's endgame plan"),
    ("6.5.3",   "6.5",  "Saving drawn endings",                 "endgame",          "Finding defensive resources in bad endings"),
    ("6.5.4",   "6.5",  "Converting winning endings",           "endgame",          "Technique for converting advantages"),

    # 7. PSYCHOLOGICAL AND PRACTICAL FACTORS
    ("7",       None,   "Psychological and Practical Factors",  "psychology",       "Mental and practical aspects of chess"),
    ("7.1",     "7",    "Time management",                      "psychology",       "Managing the clock effectively"),
    ("7.1.1",   "7.1",  "Clock usage by phase",                 "psychology",       "Spending time appropriately per phase"),
    ("7.1.2",   "7.1",  "Time pressure decision-making",        "psychology",       "Making good decisions with little time"),
    ("7.1.3",   "7.1",  "Increment management",                 "psychology",       "Using increment effectively"),
    ("7.1.4",   "7.1",  "Flagging vs resigning",                "psychology",       "Practical decisions in losing positions"),
    ("7.2",     "7",    "Decision-making under uncertainty",     "psychology",       "Choosing moves without full calculation"),
    ("7.2.1",   "7.2",  "Safest sufficient move",               "psychology",       "Choosing solid moves when unsure"),
    ("7.2.2",   "7.2",  "Avoiding unnecessary complexity",      "psychology",       "Simplifying when ahead"),
    ("7.2.3",   "7.2",  "Practical chances",                    "psychology",       "Objective eval vs practical winning chances"),
    ("7.3",     "7",    "Competitive psychology",               "psychology",       "Mental game and emotional control"),
    ("7.3.1",   "7.3",  "Tilt recognition and management",      "psychology",       "Identifying and recovering from tilt"),
    ("7.3.2",   "7.3",  "Opponent rating bias",                 "psychology",       "Playing differently vs higher or lower rated"),
    ("7.3.3",   "7.3",  "Winning and losing streaks",           "psychology",       "Managing momentum and slumps"),
    ("7.3.4",   "7.3",  "Pre-move habits",                      "psychology",       "Automatic moves that lead to blunders"),
    ("7.4",     "7",    "Game phase transitions",               "psychology",       "Navigating phase changes effectively"),
    ("7.4.1",   "7.4",  "Opening to middlegame transition",     "psychology",       "Recognizing when opening theory ends"),
    ("7.4.2",   "7.4",  "Middlegame to endgame transition",     "psychology",       "Deciding when to simplify"),
    ("7.4.3",   "7.4",  "Recognizing drawn positions",          "psychology",       "Knowing when to accept or offer draws"),

    # 8. VISUALIZATION AND BOARD AWARENESS
    ("8",       None,   "Visualization and Board Awareness",    "visualization",    "Mental board representation and calculation"),
    ("8.1",     "8",    "Board geometry",                       "visualization",    "Understanding piece movement patterns spatially"),
    ("8.1.1",   "8.1",  "Knight distance and movement",         "visualization",    "Visualizing knight hops across the board"),
    ("8.1.2",   "8.1",  "Bishop diagonals and color",           "visualization",    "Tracking diagonal lines and color complexes"),
    ("8.1.3",   "8.1",  "Rook and queen ray calculation",       "visualization",    "Seeing along ranks, files, and diagonals"),
    ("8.2",     "8",    "Piece tracking during calculation",    "visualization",    "Remembering piece positions deep in a line"),
    ("8.2.1",   "8.2",  "Remembering captured pieces",          "visualization",    "Tracking what has been taken off the board"),
    ("8.2.2",   "8.2",  "Tracking positions ahead",             "visualization",    "Holding the position N moves ahead in mind"),
    ("8.2.3",   "8.2",  "Blindfold calculation",                "visualization",    "Calculating without looking at the board"),
    ("8.3",     "8",    "Pattern memory",                       "visualization",    "Recognizing known position types instantly"),
    ("8.3.1",   "8.3",  "Position type recognition",            "visualization",    "Instantly recognizing IQP, minority attack, etc."),
    ("8.3.2",   "8.3",  "Danger pattern recognition",           "visualization",    "Seeing back-rank threats and king hunts early"),
    ("8.3.3",   "8.3",  "Endgame position recognition",         "visualization",    "Recognizing theoretical endgame positions"),
]

def seed_concepts():
    conn = get_connection()
    cur = conn.cursor()

    inserted = 0
    skipped = 0

    for code, parent_code, name, category, description in CONCEPTS:
        cur.execute("""
            INSERT INTO concepts (code, parent_code, name, category, description)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO NOTHING
        """, (code, parent_code, name, category, description))
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    conn.commit()
    cur.close()
    conn.close()
    print(f"Done. {inserted} concepts inserted, {skipped} already existed.")

if __name__ == "__main__":
    seed_concepts()