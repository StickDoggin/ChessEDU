# Chess Study Engine — Full Project Context Document

> **Purpose:** This document is the persistent brain of the chess-study-engine project.
> It captures every architectural decision, algorithm, design principle, business consideration,
> competitive insight, and outstanding item from the full project conversation.
> Claude Code should read this at the start of every session before touching any file.
> Update this document whenever a significant decision is made or a design changes.

---

## Table of Contents

1. [Product Vision](#1-product-vision)
2. [Competitive Landscape](#2-competitive-landscape)
3. [Business Model](#3-business-model)
4. [System Architecture Overview](#4-system-architecture-overview)
5. [Database Schema — Full Reference](#5-database-schema--full-reference)
6. [Chess Knowledge Ontology](#6-chess-knowledge-ontology)
7. [Data Ingestion Layer](#7-data-ingestion-layer)
8. [Stockfish Analysis Engine](#8-stockfish-analysis-engine)
9. [Accuracy Models](#9-accuracy-models)
10. [Mistake Classification System](#10-mistake-classification-system)
11. [Psychological Pattern Detection](#11-psychological-pattern-detection)
12. [Time Pressure System](#12-time-pressure-system)
13. [Opening Theory Integration](#13-opening-theory-integration)
14. [Player Profile and Weakness Graph](#14-player-profile-and-weakness-graph)
15. [Threshold System and ML Readiness](#15-threshold-system-and-ml-readiness)
16. [Study Module Architecture](#16-study-module-architecture)
17. [AI Opponent System](#17-ai-opponent-system)
18. [Gamification and Retention](#18-gamification-and-retention)
19. [Performance and Scalability](#19-performance-and-scalability)
20. [Cloud Compute Roadmap](#20-cloud-compute-roadmap)
21. [File Reference — Current Codebase](#21-file-reference--current-codebase)
22. [Current Status and Known Issues](#22-current-status-and-known-issues)
23. [Build Order — What's Done and What's Next](#23-build-order--whats-done-and-whats-next)
24. [Design Principles — Never Violate These](#24-design-principles--never-violate-these)
25. [Outstanding Questions and Open Items](#25-outstanding-questions-and-open-items)
26. [Environment and Setup](#26-environment-and-setup)
27. [Chess King University Curriculum Reference](#27-chess-king-university-curriculum-reference)

---

## 1. Product Vision

### The Core Problem

Every existing chess study tool is a content library with a generic progression system.
They tell you what to study (openings, tactics, endgames) without knowing what YOU specifically
need to study. The result is players spending hours on material that doesn't address their actual
weaknesses, leading to slow or stalled improvement.

### The Solution

A data-driven chess coaching engine that:
1. Imports your complete game history from Chess.com and Lichess
2. Runs deep Stockfish analysis on every game, annotating every move
3. Builds a statistical model of your specific weaknesses, weighted by recency and Elo relevance
4. Ranks those weaknesses by their estimated Elo impact
5. Prescribes specific study activities in priority order
6. Tracks whether study interventions actually resolved the weakness
7. Adapts continuously as new games are played

### The Differentiator

The tool creates a **data flywheel**:
- More users → more game data → better outcome tracking
- Better outcome tracking → better Elo impact predictions
- Better predictions → better study routing → better user results
- Better results → more users

The professional benchmark model and outcome tracking pipeline are the two hardest things
to replicate — they require years of longitudinal data. A competitor can build a puzzle system;
they cannot replicate three years of "study X caused Y% weakness reduction at this Elo bracket"
outcome data.

### What This Is NOT

- Not a replacement for Chess.com or Lichess (players keep using those to play)
- Not a generic puzzle trainer
- Not an opening memorization tool
- Not a game analysis viewer

It sits on top of all existing tools as a diagnostic and prescription layer.

### Target User

A chess player who:
- Has a significant game history (100+ online games)
- Is actively trying to improve (not just casual play)
- Is frustrated that they keep making the same mistakes
- Is between 800 and 2200 Elo (the improvement-hungry range)
- Pays for chess tools (Chess.com Diamond is $14/mo — this market exists)

Primary user: StickDoggin (Karl) — 1650 rapid/blitz on Chess.com, primarily rapid last 30-60 days,
10,921 games imported covering 2012-2026.

---

## 2. Competitive Landscape

### Noctie ($13.90/month)
**Website:** chessiverse.com adjacent tool, separate product

**What it does:**
- Imports Chess.com games
- Identifies mistakes and creates flashcards automatically
- Game review flow: shows position, identifies mistake, offers "Solve" challenge
- Flashcard categories: Opening mistakes, Missed checkmates, Endgame mistakes,
  Missed tactics, Tactical mistakes, Positional mistakes
- Opening books (14 available, limited)
- "Played like 2481" metric (engaging but misleading — single-game comparison to GM)

**What it doesn't do:**
- No diagnostic layer — identifies mistakes but not patterns across games
- No weakness weighting — everyone gets same generic categories
- No Elo impact estimation
- No time pressure analysis
- No opponent capitalization tracking
- No epoch awareness — old games weighted same as recent
- No AI opponent
- No longitudinal weakness tracking

**Our assessment:** Doing the first 20% of what we're building. The game review UX
is well-designed and worth emulating. The flashcard → solve flow is the right pattern.

### ChessLine ($3.99/month)
**What it does well:**
- Opening theory browser with move trees, frequency percentages, win rates
- Shows "1 of 239" positions for progress tracking
- Browse/Train split is the right UX pattern
- Opening performance by variation with actual game results tied to ECO codes
- Shows win rate delta (-10%) per opening — simple but effective
- Daily task list: Fix Mistakes (3) +30XP, Opening Deviations (2) +20XP, etc.
- Game history with accuracy circles (82%, 76%) and performance rating
- "Ask your coach" chat input (LLM integration, depth unclear)

**What it doesn't do:**
- Requires manual analysis request — most games never get analyzed
- No weakness diagnosis — opening tracking shows performance but not why
- No time pressure awareness
- No opponent capitalization
- No epoch awareness
- Opening training is generic, not filtered to lines you specifically struggle with
- No psychological pattern detection

**Key insight:** ChessLine's opening section is the benchmark to beat.
The move tree with frequency + win rate is the right information architecture.
We should build a similar browser but filtered to lines you actually play and
weighted by your personal win rate in each variation.

**Critical differentiator vs ChessLine:** Automatic analysis vs manual request.
ChessLine requiring manual review means most games never get analyzed.
Our pipeline analyzes everything automatically in priority order.
This is not a feature — it's a fundamentally different product philosophy.

### Chessiverse
- Human-like bots with personalities and playstyles (600+ bots)
- Course integration with bots that adapt to what you're studying
- Bot quality evolved through multiple generations (v1→v3)
- Clean UX, backed by chess creators like John Bartholomew
- Their bot-plus-course model: study a concept, then immediately play a bot
  that forces you into those positions — this is the prescription loop we designed
- **Missing:** No diagnostic layer, bots are generic not targeted at your weaknesses

### ChessKing, ChessTactics
- Good for generic puzzle training
- Some offer puzzles filtered by position type and game phase
- Some analyze your games and give puzzles based on mistakes
- **Missing:** No statistical weakness modeling, no Elo impact weighting,
  no personalized prescription ordering

### Key Competitive Positioning

```
ChessLine ($3.99):    Opening theory + manual game review
Noctie ($13.90):      Auto game review + generic flashcards
Chessiverse:          Human-like bot opponents
Our tool ($9.99-$14.99): Diagnostic engine + personalized prescription
                          + targeted AI opponent + all of the above integrated
```

No existing tool combines:
1. Automatic deep analysis of full game history
2. Statistical weakness diagnosis with Elo impact weighting
3. Personalized study prescription in priority order
4. AI opponent that targets your specific weaknesses
5. Outcome tracking that validates whether study worked

### Pricing Recommendation

$3.99 is too low given the value delivered and competitive pricing.
$9.99-$14.99 is the right range based on:
- ChessLine charges $3.99 for significantly less
- Noctie charges $13.90 for a subset of our features
- Chess.com Diamond is $14/mo and has millions of paying subscribers

Freemium model (probably optimal):
- Free: Import games, basic accuracy stats, 3 drills/day, weakness overview
- $9.99/month: Full analysis, unlimited drills, complete weakness graph, prescription
- $14.99/month: AI opponent, coaching mode, priority analysis queue, all features

---

## 3. Business Model

### Market Size

```
Active online chess players:           ~30-50M
Players who actively study:            ~10-15% → 3-5M
Players who pay for chess tools:       ~5-8%   → 1.5-3M
```

### Revenue Projections (Solo Founder)

**Base expenses (fixed monthly):**
```
Cloud VM for Stockfish analysis:       $20-40/mo
PostgreSQL managed database:           $15-25/mo
App hosting (Render/Railway/Fly.io):   $10-20/mo
CDN / storage:                         $5-15/mo
Domain + SSL:                          $2/mo
Email (Postmark/Sendgrid):             $10-20/mo
Error monitoring (Sentry):             $0-26/mo
Analytics:                             $0-20/mo
Stripe fees:                           ~2.9% + $0.30/transaction
Total fixed:                           ~$60-150/mo at launch
```

**Variable costs (scale with users):**
```
Analysis compute per new user:         ~$0.50-2.00 one-time (Stockfish on ~500 games)
Ongoing new games per user/month:      ~$0.05-0.20
Database storage per analyzed user:    ~50MB
```

**Profit margins at scale:**
```
100 users ($3,500 MRR at $35 avg):     ~49% margin, ~$1,700/mo profit
1,000 users:                           ~86% margin, ~$30,000/mo profit
5,000 users:                           ~89% margin, ~$188,000/yr profit
20,000 users:                          ~91% margin, ~$760,000/yr profit
50,000 users:                          ~90% margin, ~$1.89M/yr profit
```

Software margins are exceptional because:
- Stockfish is free
- PostgreSQL is cheap at scale
- One codebase serves 50,000 users as easily as 500
- Time cost is fixed regardless of user count

**Break-even for comfortable living (~$8,000/mo profit):**
- At $3.99: ~3,000 users
- At $9.99: ~1,000 users

**Acquisition value at scale:**
At 50,000+ users with the data moat, acquisition value to Chess.com,
Chessbase, or sports tech company: likely 5-10x ARR = $50-100M range.

**Operational reality at scale:**
At 20,000+ users solo is genuinely hard:
- Support tickets: ~50-100/week
- Bug reports: ~20-30/week
- Infrastructure fires: occasional
At this scale, one part-time support hire is probably needed.

---

## 4. System Architecture Overview

### The Six Layers

```
Layer 1: Data Ingestion
  Chess.com API + Lichess API + PGN upload
  → games table, moves table (raw, no analysis)

Layer 2: Stockfish Analysis Engine
  Full-game annotation at depth 14-20
  Two-pass: player moves, then opponent response to mistakes
  → moves table populated with evals, CPL, WDL, PV lines

Layer 3: Player Profile and Weakness Model
  Cross-game pattern detection
  Recency-weighted, Elo-proximity-weighted aggregation
  → weakness_graph table

Layer 4: Study Module Router
  Adaptive study plan from weakness graph
  Priority ordering by Elo impact
  → prescription output

Layer 5: Gamification and Retention
  XP system, spaced repetition, insight feed
  → drill_positions, drill_attempts, study_sessions

Layer 6: Data Infrastructure
  Stockfish-annotated corpus, opening database,
  professional game corpus, outcome tracking
  → openings, concept_study_mapping, analysis_log
```

### Data Flow

```
Chess.com API → import_chesscom.py → games + moves tables (raw)
                                          ↓
                              analyze_games.py (Stockfish)
                                          ↓
                          moves table (fully annotated)
                                          ↓
                    pattern_detector.py (future) → move_concepts table
                                          ↓
                    weakness_aggregator.py (future) → weakness_graph table
                                          ↓
                    prescription_engine.py (future) → study plan output
```

### Key Design Decisions

**Everything is in PostgreSQL.** No Redis, no MongoDB, no separate services.
Postgres handles everything including JSONB for flexible concept scores.
This keeps the stack simple for a solo founder.

**Analysis is async and queue-based.** Import and analysis run independently.
New games can be imported while old ones are analyzed in background.
The analysis_queue table manages priority, status, and retry logic.

**Thresholds are database rows, not code constants.**
Every threshold lives in player_thresholds table.
Code reads thresholds at runtime. ML can update them without code changes.
This is the #1 ML-readiness decision.

**Everything is a continuous score, labels are derived.**
mistake_score is a float 0.0-1.0. mistake_class is derived from it at query time.
This means the ML trains on floats, not categorical labels.

---

## 5. Database Schema — Full Reference

### players
```sql
id          SERIAL PRIMARY KEY
username    TEXT NOT NULL
platform    TEXT NOT NULL  -- 'chess.com' or 'lichess'
created_at  TIMESTAMPTZ DEFAULT NOW()
UNIQUE (username, platform)
```

### player_ratings
```sql
id          SERIAL PRIMARY KEY
player_id   INTEGER REFERENCES players(id)
game_type   TEXT NOT NULL  -- 'rapid', 'blitz', 'bullet', 'classical'
current_elo INTEGER
fetched_at  TIMESTAMPTZ DEFAULT NOW()
UNIQUE (player_id, game_type)
```
Populated by fetch_and_store_current_ratings() in db_setup.py.
StickDoggin current ratings: rapid=1656, blitz=1632, bullet=1414, classical=400(default).

### player_epochs
```sql
id          SERIAL PRIMARY KEY
player_id   INTEGER REFERENCES players(id)
game_type   TEXT NOT NULL
started_at  TIMESTAMPTZ
ended_at    TIMESTAMPTZ  -- NULL if current epoch
elo_start   INTEGER
elo_end     INTEGER
```
Epochs are contiguous periods of consistent skill level and error patterns.
NOT time-based — detected via statistical breakpoints in performance.
Separate epochs per game type (your blitz epoch ≠ your rapid epoch).

### games
```sql
id                          SERIAL PRIMARY KEY
player_id                   INTEGER REFERENCES players(id)
epoch_id                    INTEGER REFERENCES player_epochs(id)
source                      TEXT NOT NULL  -- 'chess.com', 'lichess', 'pgn_upload'
source_game_id              TEXT NOT NULL  -- external ID for deduplication
played_at                   TIMESTAMPTZ
color                       TEXT  -- 'white' or 'black'
result                      TEXT  -- 'win', 'loss', 'draw'
result_type                 TEXT  -- 'checkmated', 'timeout', 'resigned', 'stalemate', etc.
time_control                TEXT  -- '600+0', '180+2', etc. (raw string)
game_type                   TEXT  -- 'bullet', 'blitz', 'rapid', 'classical' (derived)
player_elo                  INTEGER
opponent_elo                INTEGER
opening_eco                 TEXT  -- 'B12'
opening_name                TEXT  -- 'Caro-Kann Defense: Advance Variation'
opening_var                 TEXT
total_moves                 INTEGER
raw_pgn                     TEXT

-- Analysis status
analyzed                    BOOLEAN DEFAULT FALSE
analysis_priority           INTEGER DEFAULT 5
analyzed_at                 TIMESTAMPTZ
novelty_move                INTEGER  -- move number where book ended
novelty_fen                 TEXT     -- FEN at novelty point

-- Accuracy (three models)
accuracy_pct                FLOAT  -- WDL-based (primary)
accuracy_wdl                FLOAT  -- Stockfish WDL model
accuracy_lichess            FLOAT  -- CPL-based strict formula
accuracy_chesscom           FLOAT  -- win probability delta

-- Opponent data
opponent_avg_cpl            FLOAT
opponent_accuracy_pct       FLOAT
opponent_time_pressure_moves INTEGER

-- Session context
session_id                  INTEGER REFERENCES sessions(id)
session_streak              INTEGER  -- positive=wins, negative=losses before this game
streak_cpl_delta            FLOAT    -- CPL vs baseline during streak

-- Psychological game-level flags
missed_salvations           INTEGER DEFAULT 0
complacency_blunders        INTEGER DEFAULT 0
winning_position_converted  BOOLEAN
max_advantage_reached       INTEGER  -- peak eval in player's favor
advantage_surrendered       BOOLEAN DEFAULT FALSE

-- Time scramble
time_scramble_occurred      BOOLEAN DEFAULT FALSE
time_scramble_start_move    INTEGER
scramble_winner             TEXT

-- Repetition
ended_by_repetition         BOOLEAN DEFAULT FALSE
repetition_offered_by       TEXT  -- 'player' or 'opponent'

UNIQUE (source, source_game_id)
```

### moves
```sql
id                          SERIAL PRIMARY KEY
game_id                     INTEGER REFERENCES games(id)
player_id                   INTEGER REFERENCES players(id)
move_number                 INTEGER
color                       TEXT  -- 'white' or 'black'
san                         TEXT  -- 'Nf3'
uci                         TEXT  -- 'g1f3'
fen_before                  TEXT
fen_after                   TEXT

-- Clock data (milliseconds)
clock_before_ms             INTEGER
clock_after_ms              INTEGER
time_spent_ms               INTEGER
increment_ms                INTEGER
time_pressure               TEXT  -- 'critical', 'low', 'normal', 'comfortable'
time_percentile             FLOAT

-- Opponent clock data
opponent_clock_before_ms    INTEGER
opponent_clock_after_ms     INTEGER
opponent_time_spent_ms      INTEGER
opponent_time_pressure      TEXT

-- Game phase
phase                       TEXT  -- 'opening', 'middlegame', 'endgame'
move_in_phase               INTEGER
moves_since_novelty         INTEGER  -- 0=still in book, NULL=book not ended yet

-- Stockfish analysis
eval_before                 INTEGER  -- centipawns, from player's perspective
eval_after                  INTEGER
best_eval                   INTEGER
centipawn_loss              INTEGER  -- CAPPED at 500 before storage
best_move_uci               TEXT
best_move_san               TEXT
pv_line_1                   TEXT  -- top 5 principal variations (UCI strings)
pv_line_2                   TEXT
pv_line_3                   TEXT
pv_line_4                   TEXT
pv_line_5                   TEXT
analysis_depth              INTEGER
is_book_move                BOOLEAN

-- Played move rank (1=best, 2=second best, NULL=not in top 5)
played_move_rank            INTEGER
played_move_cp              INTEGER  -- eval of the move actually played

-- WDL (Win/Draw/Loss from Stockfish) — from player's perspective
wdl_wins_before             INTEGER  -- 0-1000
wdl_draws_before            INTEGER
wdl_losses_before           INTEGER
wdl_wins_after              INTEGER
wdl_draws_after             INTEGER
wdl_losses_after            INTEGER

-- Three accuracy models per move
accuracy_wdl                FLOAT  -- primary model
accuracy_lichess            FLOAT  -- strictest
accuracy_chesscom           FLOAT  -- most forgiving, matches Chess.com feel

-- Classification
mistake_score               FLOAT   -- continuous 0.0-1.0 (SOURCE OF TRUTH)
mistake_class               TEXT    -- 'blunder','mistake','inaccuracy','suboptimal' (DERIVED)
mistake_severity            FLOAT   -- same as mistake_score currently
contextual_severity         FLOAT   -- phase and tension adjusted

-- Position context
position_tension            FLOAT   -- 0=one-sided, 1=perfectly equal
position_complexity         FLOAT   -- 0=forcing/simple, 1=maximum complexity
candidate_move_count        INTEGER -- how many moves within 50cp of best
is_only_move                BOOLEAN -- only one move maintains eval
position_eval_state         TEXT    -- 'winning', 'equal', 'losing'

-- Error flags
is_time_pressure_error      BOOLEAN
tactical_depth_required     INTEGER -- min ply to find correct move

-- Premove/panic detection
is_likely_premove           BOOLEAN  -- time_spent_ms < 500
is_likely_panic             BOOLEAN  -- time_spent < 2000 AND clock < 10000

-- Sacrifice detection
is_sacrifice                BOOLEAN
sacrifice_type              TEXT     -- 'correct', 'reasonable', 'speculative'
sacrifice_correct           BOOLEAN

-- Psychological flags
missed_salvation            BOOLEAN DEFAULT FALSE
salvation_eval_swing        INTEGER
resignation_mindset_flag    BOOLEAN DEFAULT FALSE
complacency_flag            BOOLEAN DEFAULT FALSE
desperation_sacrifice       BOOLEAN DEFAULT FALSE
swindle_attempt             BOOLEAN DEFAULT FALSE

-- Repetition
is_repetition               BOOLEAN DEFAULT FALSE
times_position_seen         INTEGER

-- Drift detection
cumulative_drift_5          FLOAT    -- sum of CPL over last 5 moves
drift_flag                  BOOLEAN  -- small CPLs accumulated to big swing

-- Tablebase (future)
tablebase_result            TEXT     -- 'win', 'draw', 'loss'
tablebase_dtz               INTEGER
tablebase_deviation         INTEGER

-- Analysis quality
analysis_quality            TEXT     -- 'book', 'low', 'medium', 'high'
analysis_confidence         FLOAT    -- 0.0-1.0

-- Pattern tags (populated by pattern detector, future)
pattern_tags                TEXT[]
```

### concepts
```sql
id          SERIAL PRIMARY KEY
code        TEXT UNIQUE NOT NULL  -- '3.1.1', '4.2.4', etc.
parent_code TEXT                  -- NULL for top-level categories
name        TEXT NOT NULL
category    TEXT NOT NULL  -- 'tactics', 'positional', 'opening', 'endgame', etc.
description TEXT
```
176 concepts seeded covering 8 top-level categories.
See Section 6 for the full ontology.

### move_concepts
```sql
move_id             INTEGER REFERENCES moves(id)
concept_id          INTEGER REFERENCES concepts(id)
relevance           FLOAT DEFAULT 1.0      -- legacy, use attribution_weight
attribution_weight  FLOAT DEFAULT 1.0      -- 0.0-1.0 confidence this label applies
cpl_attributed      INTEGER                -- how many CPL points this concept explains
detection_method    TEXT                   -- 'mathematical', 'positional', 'statistical'
is_primary_cause    BOOLEAN DEFAULT FALSE  -- dominant label for this mistake
PRIMARY KEY (move_id, concept_id)
```

### analysis_queue
```sql
id              SERIAL PRIMARY KEY
game_id         INTEGER REFERENCES games(id) UNIQUE
priority        INTEGER DEFAULT 5  -- higher = analyzed first
status          TEXT DEFAULT 'pending'  -- 'pending','in_progress','complete','error'
queued_at       TIMESTAMPTZ DEFAULT NOW()
started_at      TIMESTAMPTZ
completed_at    TIMESTAMPTZ
worker_id       TEXT
error_message   TEXT
retry_count     INTEGER DEFAULT 0
last_move_analyzed INTEGER DEFAULT 0  -- for resume capability
```

**Priority formula:**
```
Recency:    played_at > 60 days ago  → +5
            played_at > 6 months     → +3
            played_at > 18 months    → +1
            older                    → +0

Result:     loss  → +3
            draw  → +1
            win   → +0

Game type:  rapid   → +3
            blitz   → +2
            bullet  → +0
            other   → +0

Elo:        within bracket_low to bracket_high → +2
            (bracket = current_elo ± 150)
```

### player_thresholds
```sql
id              SERIAL PRIMARY KEY
player_id       INTEGER REFERENCES players(id)  -- NULL = global default
game_type       TEXT NOT NULL
threshold_name  TEXT NOT NULL
value           FLOAT NOT NULL
source          TEXT DEFAULT 'default'  -- 'default','statistical','changepoint','neural'
confidence      FLOAT DEFAULT 0.5
sample_size     INTEGER DEFAULT 0
version         INTEGER DEFAULT 1
derived_from    TEXT DEFAULT 'default_v1'
updated_at      TIMESTAMPTZ DEFAULT NOW()
UNIQUE (player_id, game_type, threshold_name)
```

**Default thresholds seeded (58 rows):**
```
Per game type (blitz, rapid, bullet, classical):
  blunder_cpl, mistake_cpl, inaccuracy_cpl, suboptimal_cpl
  critical_time_pct, low_time_pct, normal_time_pct
  blunder_score_threshold, mistake_score_threshold,
  inaccuracy_score_threshold, suboptimal_score_threshold

Global ('all' game type):
  high_quality_depth, medium_quality_depth
  high_quality_time_s, medium_quality_time_s
  resignation_mindset_eval, complacency_eval, winning_advantage_eval
  salvation_min_swing, tilt_cpl_multiplier
  premove_ms, panic_ms, panic_clock_ms
  recency_half_life_days, elo_proximity_scale
```

**Bullet-specific adjustments:**
Bullet gets higher CPL thresholds (250 blunder vs 200) because time pressure
is inherent to the format — the same mistake is less diagnostic in bullet.

**Classical-specific adjustments:**
Classical gets lower CPL thresholds (150 blunder vs 200) because players
have full time to find the best move — the same mistake is more diagnostic.

### weakness_graph
```sql
id              SERIAL PRIMARY KEY
player_id       INTEGER REFERENCES players(id)
concept_code    TEXT REFERENCES concepts(code)
game_type       TEXT NOT NULL

-- Frequency
occurrence_count        INTEGER DEFAULT 0
occurrence_rate         FLOAT    -- per 100 moves
avg_cpl_when_occurs     FLOAT
avg_contextual_severity FLOAT
avg_attribution_weight  FLOAT

-- Trend
trend_30_days           FLOAT   -- positive=improving, negative=worsening
trend_90_days           FLOAT

-- Exploitability
avg_exploitability              FLOAT
opponent_capitalization_rate    FLOAT

-- Elo impact
estimated_elo_impact    FLOAT
primary_study_module    TEXT

-- Status tracking
status              TEXT DEFAULT 'active'  -- 'active','improving','resolved','regressed'
first_detected      DATE
last_occurred       DATE
resolution_date     DATE
regression_count    INTEGER DEFAULT 0
mastery_score       FLOAT DEFAULT 0.0
  -- 0.0=never addressed, 0.5=improving, 0.8=mostly resolved, 1.0=mastered
study_efficiency    FLOAT   -- estimated_elo_impact / estimated_study_hours
estimated_study_hours FLOAT

updated_at  TIMESTAMPTZ DEFAULT NOW()
UNIQUE (player_id, concept_code, game_type)
```

### concept_study_mapping
```sql
concept_code            TEXT REFERENCES concepts(code)
study_module            TEXT NOT NULL
study_subtype           TEXT NOT NULL
effectiveness_score     FLOAT DEFAULT 0.5  -- updated by outcome tracking
min_attribution_weight  FLOAT DEFAULT 0.3  -- ignore weak signals
elo_bracket_min         INTEGER
elo_bracket_max         INTEGER
PRIMARY KEY (concept_code, study_module, study_subtype)
```
This table IS the prescription layer foundation.
Query: find highest-weighted recurring concept errors → join here → rank by effectiveness_score.

### player_snapshots
```sql
id              SERIAL PRIMARY KEY
player_id       INTEGER REFERENCES players(id)
snapshot_date   DATE NOT NULL
game_type       TEXT NOT NULL
elo             INTEGER
games_analyzed  INTEGER

-- Accuracy metrics
avg_cpl_overall             FLOAT
avg_cpl_opening             FLOAT
avg_cpl_middlegame          FLOAT
avg_cpl_endgame             FLOAT

-- Mistake rates (per 100 moves)
blunder_rate                FLOAT
missed_tactic_rate          FLOAT
positional_error_rate       FLOAT
time_pressure_error_rate    FLOAT

-- Calculation metrics
avg_tactical_depth_failed   FLOAT
avg_tactical_depth_solved   FLOAT

-- Time management
avg_time_spent_opening_ms   FLOAT
avg_time_spent_middlegame_ms FLOAT
avg_time_spent_endgame_ms   FLOAT
critical_time_blunder_rate  FLOAT

-- Exploitability
avg_exploitability_score    FLOAT
opponent_capitalization_rate FLOAT

-- Concept weakness scores (stored as JSON for flexibility)
concept_scores              JSONB

-- Top 5 weaknesses at this snapshot
top_weakness_1 through top_weakness_5  TEXT (concept codes)

created_at  TIMESTAMPTZ DEFAULT NOW()
UNIQUE (player_id, snapshot_date, game_type)
```

### evaluation_state_performance
```sql
id                          SERIAL PRIMARY KEY
player_id                   INTEGER REFERENCES players(id)
game_type                   TEXT NOT NULL
eval_state                  TEXT NOT NULL  -- 'winning', 'equal', 'losing'
avg_cpl                     FLOAT
blunder_rate                FLOAT
missed_opportunity_rate     FLOAT
avg_time_spent_ms           FLOAT
winning_conversion_rate     FLOAT
salvation_find_rate         FLOAT
equality_decision_rate      FLOAT
sample_size                 INTEGER DEFAULT 0
updated_at                  TIMESTAMPTZ DEFAULT NOW()
UNIQUE (player_id, game_type, eval_state)
```

### sessions
```sql
id              SERIAL PRIMARY KEY
player_id       INTEGER REFERENCES players(id)
started_at      TIMESTAMPTZ
ended_at        TIMESTAMPTZ
game_count      INTEGER
game_type       TEXT
avg_cpl         FLOAT
avg_accuracy    FLOAT
peak_cpl        FLOAT
tilt_detected   BOOLEAN DEFAULT FALSE
tilt_coefficient FLOAT
fatigue_detected BOOLEAN DEFAULT FALSE
fatigue_start_game INTEGER
created_at      TIMESTAMPTZ DEFAULT NOW()
```

### elo_history
```sql
id          SERIAL PRIMARY KEY
player_id   INTEGER REFERENCES players(id)
game_type   TEXT NOT NULL
elo         INTEGER NOT NULL
recorded_at TIMESTAMPTZ NOT NULL
game_id     INTEGER REFERENCES games(id)
```
Populated from games.player_elo during schema_update2.py run.
Enables rating arc visualization and epoch detection.

### openings
```sql
eco         TEXT NOT NULL
name        TEXT NOT NULL
pgn         TEXT
uci_moves   TEXT
epd         TEXT
PRIMARY KEY (eco, name)
```
TO BE SEEDED from Lichess opening TSV:
https://github.com/lichess-org/chess-openings
3,561 named variations. One-time seed operation.

### drill_positions
```sql
id              SERIAL PRIMARY KEY
player_id       INTEGER REFERENCES players(id)
source_move_id  INTEGER REFERENCES moves(id)  -- from their own game
concept_code    TEXT REFERENCES concepts(code)
fen             TEXT NOT NULL
correct_move    TEXT NOT NULL
correct_move_san TEXT
difficulty      FLOAT DEFAULT 0.5

-- SM-2 spaced repetition fields
next_review     DATE DEFAULT CURRENT_DATE
interval_days   INTEGER DEFAULT 1
ease_factor     FLOAT DEFAULT 2.5
review_count    INTEGER DEFAULT 0
last_result     TEXT  -- 'correct', 'incorrect', 'hint_used'

created_at      TIMESTAMPTZ DEFAULT NOW()
```

### drill_attempts
```sql
id              SERIAL PRIMARY KEY
drill_id        INTEGER REFERENCES drill_positions(id)
player_id       INTEGER REFERENCES players(id)
attempted_at    TIMESTAMPTZ DEFAULT NOW()
move_played     TEXT
was_correct     BOOLEAN
time_spent_ms   INTEGER
hint_used       BOOLEAN DEFAULT FALSE
new_interval    INTEGER
new_ease_factor FLOAT
```

### study_sessions
```sql
id              SERIAL PRIMARY KEY
player_id       INTEGER REFERENCES players(id)
session_date    DATE DEFAULT CURRENT_DATE
module_type     TEXT
concept_codes   TEXT[]
duration_mins   INTEGER
positions_seen  INTEGER DEFAULT 0
positions_solved INTEGER DEFAULT 0
avg_solve_time_ms INTEGER
difficulty_avg  FLOAT
completed_at    TIMESTAMPTZ
```

### import_log
```sql
id              SERIAL PRIMARY KEY
player_id       INTEGER REFERENCES players(id)
platform        TEXT
imported_at     TIMESTAMPTZ DEFAULT NOW()
games_found     INTEGER DEFAULT 0
games_inserted  INTEGER DEFAULT 0
games_skipped   INTEGER DEFAULT 0
errors          INTEGER DEFAULT 0
last_game_date  DATE
```

### analysis_log
```sql
id                  SERIAL PRIMARY KEY
started_at          TIMESTAMPTZ DEFAULT NOW()
completed_at        TIMESTAMPTZ
games_analyzed      INTEGER DEFAULT 0
moves_annotated     INTEGER DEFAULT 0
avg_depth           FLOAT
avg_time_per_move_ms FLOAT
errors              INTEGER DEFAULT 0
```

### time_pressure_thresholds
```sql
id              SERIAL PRIMARY KEY
game_type       TEXT NOT NULL
elo_bracket     TEXT NOT NULL
critical_pct    FLOAT NOT NULL
low_pct         FLOAT NOT NULL
normal_pct      FLOAT NOT NULL
computed_at     TIMESTAMPTZ DEFAULT NOW()
sample_size     INTEGER
UNIQUE (game_type, elo_bracket)
```
This table stores ML-derived thresholds per bracket.
The player_thresholds table stores per-player thresholds.
These two tables work together — bracket defaults → personal refinement.

---

## 6. Chess Knowledge Ontology

176 concepts organized in 8 top-level categories.
Every mistake maps to one or more concept codes.
Every study activity is tagged to concept codes.
The weakness graph weights nodes by concept code.

### Top-Level Categories

```
1. Fundamental Rules        (1.1 - 1.5)
2. Material                 (2.1 - 2.3.x)
3. Tactics                  (3.1 - 3.4.x)
4. Positional Principles    (4.1 - 4.5.x)
5. Opening Theory           (5.1 - 5.4)
6. Endgame Theory           (6.1 - 6.5.x)
7. Psychological Factors    (7.1 - 7.4.x)
8. Visualization            (8.1 - 8.3.x)
```

### Key Tactical Codes

```
3.1.1  Fork
3.1.2  Pin (absolute and relative)
3.1.3  Skewer
3.1.4  Discovered attack
3.1.5  Discovered check
3.1.6  Double check
3.1.7  Removal of the defender
3.1.8  Overloading / overworked piece
3.1.9  Interference
3.1.10 Deflection
3.1.11 Decoy and lure
3.1.12 Zwischenzug
3.1.13 X-ray attack
3.1.14 Clearance sacrifice

3.2.1  Back-rank mate
3.2.2  Smothered mate
3.2.3  Scholar's mate
... (12 mating patterns total)

3.3.1  Candidate move generation
3.3.2  Tree pruning
3.3.3  Forcing moves first
3.3.4  Counting attackers and defenders
3.3.5  Prophylactic thinking
3.3.6  Calculation depth (2-ply through 10+)
```

### Key Positional Codes

```
4.1.1  Piece centralization
4.1.2  Bad bishop
4.1.4  Knight outpost
4.1.5  Rook on open file
4.1.6  Rook on seventh rank
4.2.1  Isolated pawn (IQP)
4.2.3  Backward pawn
4.2.4  Passed pawn
4.2.7  Pawn breaks
4.2.10 Pawn storm
4.3.3  Weak squares
4.4.1  Castling timing
4.4.2  Pawn shield integrity
4.4.3  Open files toward king
4.5.4  Prophylaxis
4.5.5  Zugzwang
```

### Key Psychological Codes

```
7.1.1  Clock usage by phase
7.1.2  Time pressure decision-making
7.3.1  Tilt recognition and management
7.3.2  Opponent rating bias
7.3.4  Pre-move habits
7.4.1  Opening to middlegame transition
7.4.2  Middlegame to endgame transition
```

---

## 7. Data Ingestion Layer

### Chess.com Importer (import_chesscom.py)

**Function:** `import_all_games(username: str)`
- Fetches archive list from Chess.com API
- Processes each monthly archive chronologically
- Parses PGN including clock times from comments: `{ [%clk 0:04:32] }`
- Inserts games and moves with clock data
- Handles deduplication via UNIQUE(source, source_game_id)

**StickDoggin stats:**
- 44 monthly archives (2012-2026)
- 10,921 games inserted
- 0 skipped, 2 errors (malformed PGNs on Chess.com's end)
- Distribution: ~9,210 blitz, ~542 rapid, ~1,103 bullet, ~66 classical

**Game type classification:**
```python
def classify_game_type(time_control: str) -> str:
    parts = time_control.split("+")
    base = int(parts[0])
    increment = int(parts[1]) if len(parts) > 1 else 0
    estimated = base + (40 * increment)  # 40 moves assumed
    if estimated < 180:   return "bullet"
    if estimated < 480:   return "blitz"
    if estimated < 1500:  return "rapid"
    return "classical"
```

**Clock parsing:**
```python
def parse_clock(comment: str) -> int | None:
    match = re.search(r'\[%clk\s+(\d+):(\d+):(\d+)\]', comment)
    if match:
        h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
        return (h * 3600 + m * 60 + s) * 1000
    return None
```

**Phase classification (simple heuristic):**
```python
if move_num < 12: phase = "opening"
elif piece_count <= 10: phase = "endgame"
else: phase = "middlegame"
```
Note: This is a starting heuristic. Future improvement: use novelty_move
to define opening end, and material threshold for endgame start.

**Lichess integration:**
Lichess public API is the same format.
Bulk database (500M+ games) available at https://database.lichess.org
Use for population-level models (exploitability scores, threshold detection).
Not yet implemented — planned for Phase 2.

### Import Log
Every import writes to import_log table.
Query `SELECT * FROM import_log ORDER BY imported_at DESC` to see history.

---

## 8. Stockfish Analysis Engine

### Binary Location
```
C:\Users\karlb\chess-study-engine\stockfish\stockfish-windows-x86-64-avx2.exe
```
Stored in .env as STOCKFISH_PATH.
Stockfish version: 18.3 (latest as of May 2026).
Uses NNUE (neural network evaluation) internally.

### Analysis Configuration
```python
engine.configure({'Threads': 1, 'Hash': 128})
```
One thread per engine instance (parallel workers each spawn their own instance).
128MB hash table — balance between speed and memory when running 8 parallel workers.

### Hybrid Analysis Limit System

The key insight: neither pure time-based nor pure depth-based analysis is optimal.
We use a hybrid: time limit with a minimum depth guarantee.

```python
# Per move timing (sequential, long game factor applied if >80 moves):
Early opening (moves 1-3):  0.08s time + depth 20 cap, min depth 8
Opening (moves 4-10):       0.15s time + depth 20 cap, min depth 8
Middlegame:                 0.50s time + depth 20 cap, min depth 14
Endgame:                    0.40s time + depth 20 cap, min depth 16
Post-blunder position:      2.00s time + depth 20 cap, min depth 16
Post-mistake position:      0.80s time + depth 20 cap, min depth 14
Long game factor (>80 mvs): all times × 0.6
```

**Why minimum depth matters:**
Stockfish can stop early on time before reaching a meaningful depth on complex positions.
Min depth guarantees we never accept a shallow result even on fast positions.
If time runs out before min depth, we re-run with depth as the hard constraint.

**Why post-blunder gets more time:**
The position immediately after a blunder is where we most need to understand
exactly what was missed. This is where the pattern detector will fire.
Extra depth = more accurate PV lines = better concept identification.

**Stability detection (future improvement):**
Stockfish reports eval continuously as depth increases.
We could stop early if eval has stabilized (changed < 15cp for 3 consecutive depths).
This is more intelligent than fixed time but requires streaming analysis mode.
Planned for Phase 3 when we have cloud compute and can afford the complexity.

### MULTIPV = 5
We analyze with 5 principal variations per position.
This gives us:
- Top 5 moves and their evaluations
- played_move_rank: which of the 5 did the player choose?
- candidate_move_count: how many moves within 50cp of best?
- is_only_move: was there only one good move? (position complexity signal)

### CPL Calculation

```python
# CRITICAL: CPL is capped at CPL_CAP (500) BEFORE storage
cpl_raw = max(0, eval_before - eval_after)
cpl = min(cpl_raw, CPL_CAP)
```

**Why cap CPL:**
Mate scores returned as 10000cp (or 9999, 9998, etc. for "mate in N").
Without capping, a single checkmate position would make avg_cpl = 9000+,
completely destroying accuracy calculations.
The cap of 500 means "anything worse than a losing exchange is treated
as maximally bad" — which is correct for classification purposes.

**Why we cap before storage (not just before averaging):**
Previous bug stored raw 9270 CPL values in the database.
These leaked into accuracy calculations despite the averaging cap.
Always cap at the point of calculation.

### WDL (Win/Draw/Loss) Extraction

Stockfish 12+ includes a WDL model trained on millions of games.
Returns (wins, draws, losses) as integers 0-1000 summing to 1000.

**Critical perspective fix (previous bug):**
WDL must be extracted from WHITE's perspective first, then flipped if player is black.

```python
def extract_wdl_for_player(score, player_color: str) -> tuple:
    wdl = score.white().wdl()  # ALWAYS from white's perspective first
    if player_color == 'white':
        return wdl.wins, wdl.draws, wdl.losses
    else:
        return wdl.losses, wdl.draws, wdl.wins  # flip for black

def extract_wdl_after_move(score, player_color: str) -> tuple:
    # After a move, it's OPPONENT's turn — perspective has shifted
    wdl = score.white().wdl()
    if player_color == 'white':
        # White just moved, now black to move. White's wins = our wins.
        return wdl.wins, wdl.draws, wdl.losses
    else:
        # Black just moved, now white to move. White's wins = our losses.
        return wdl.losses, wdl.draws, wdl.wins
```

### Two-Pass Analysis
Pass 1: Annotate player's moves (CPL, WDL, mistake class, PV lines)
Pass 2 (future): For each flagged mistake, analyze opponent's next 5 moves
  → Did they find the punishment?
  → What was their clock state?
  → How much did eval shift?
  → Populates: opponent_capitalized, capitalization_move, capitalization_cpl_swing

### Book Move Detection
**IMPLEMENTED: Local Polyglot opening book (gm2001.bin)**
File: `books/gm2001.bin` (475KB, GM games 2001–2013, ELO 2530+)
Source: https://github.com/michaeldv/donna_opening_books

```python
import chess.polyglot
book = chess.polyglot.open_reader(os.getenv('POLYGLOT_BOOK_PATH'))
entries = list(book.find_all(board))  # instant binary search
is_book = any(e.move == move for e in entries)
```

Book moves skip Stockfish entirely → significant speed saving (~20% of moves).
Zero network latency vs previous Lichess Explorer API (~200–500ms per call).
Book opened once per game, closed in cleanup. Safe for parallel workers.

The books/ directory is gitignored — must be downloaded separately.
Download source documented in Section 13.

### Syzygy Endgame Tablebases
**IMPLEMENTED: 3-4-5 piece Syzygy tablebases**
Location: `syzygy/` directory (938MB, 290 files — .rtbw + .rtbz pairs)
Source: http://tablebase.sesse.net/syzygy/3-4-5/

When piece count on board drops to 5 or fewer, tablebase lookup fires instead
of relying solely on Stockfish WDL. Stores per move:
- `tablebase_result`: 'win', 'draw', or 'loss' from side-to-move's perspective
- `tablebase_dtz`: Distance To Zero (plies to forced result). NULL for drawn
  positions where DTZ is undefined — this is correct, not a bug.
- `tablebase_deviation`: How many DTZ moves slower than optimal the player played.
  NULL for draws; populated for win/loss positions.

```python
# Board snapshot taken before push (only when pieces <= 5):
board_snap = board.copy() if pieces_now <= 5 else None
board.push(move)
if board_snap:
    tb_result, tb_dtz, tb_deviation = get_tablebase_info(board_snap, board, syzygy_tb)
```

The syzygy/ directory is gitignored — must be downloaded separately.
Download with the PowerShell script in Section 26.

### Analysis Queue Management
The `run_analysis_queue()` function:
1. Resets any stale 'in_progress' jobs (>15 minutes old)
2. Pulls highest-priority pending games
3. Marks them as 'in_progress'
4. Processes sequentially or in parallel
5. Updates analysis_log with performance metrics

**Current mode:** Sequential (parallel=False in `__main__`)
**Parallel mode:** Available via ProcessPoolExecutor, set parallel=True
**Workers:** multiprocessing.cpu_count() - 1

### Performance Metrics
```
Sequential speed:       ~0.8-1.0 games/minute
Average game time:      ~60-90 seconds
Average moves/game:     ~75 moves
Long games (>80 moves): ~90-150 seconds
```

Current throughput: 10,921 games ÷ 0.9 games/min = ~200 hours sequential.
With 8 parallel workers: ~25 hours.
With cloud VM (future): ~8-12 hours.

---

## 9. Accuracy Models

Three accuracy models are computed per move and aggregated per game.
Each measures something slightly different. All three are stored.

### Model 1: Lichess (CPL-based)
```python
def accuracy_lichess(cpl) -> float | None:
    capped = min(cpl, CPL_CAP)
    return max(0.0, min(100.0,
        103.1668 * math.exp(-0.04354 * capped) - 3.1669
    ))
```
**Characteristics:**
- Strictest standard — compares to perfect engine play
- Typical values for 1650 player: 30-60%
- Other tools show 75-95% because they use different baselines
- Calibrated for depth 20+ Stockfish; our depth 14-18 produces lower values
- Best for internal consistency and ranking games relative to each other

### Model 2: Stockfish WDL (position-aware)
```python
def accuracy_wdl(wins_before, draws_before, losses_before,
                 wins_after, draws_after, losses_after) -> float | None:
    wp_before = wins_before / 1000
    wp_after  = wins_after  / 1000
    raw = max(0.0, 1.0 - max(0.0, wp_before - wp_after))
    decisiveness = abs((wins_before/1000) - 0.5) * 2
    position_weight = 1.0 - (decisiveness * 0.7)  # 0.3 minimum weight
    neutral = 0.85
    blended = raw * position_weight + neutral * (1.0 - position_weight)
    return max(0.0, min(100.0, blended * 100))
```
**Key innovation: position-aware accuracy**
When a position is already completely won or lost (WDL near 1000/0 or 0/1000),
any move looks equally accurate because you can't lose/gain more than you have.
This was causing bugs: 292 CPL from a lost position scoring 100% accuracy.
The fix: blend raw accuracy with a neutral 85% baseline, weighted by
how contested the position is. Already-decided positions count less.

**Characteristics:**
- Most grounded — uses Stockfish's own probability model
- Accounts for position context (won/lost positions weighted appropriately)
- Typical values for 1650 player: 70-85%
- PRIMARY accuracy model — stored in games.accuracy_pct

### Model 3: Chess.com style (win probability delta)
```python
def accuracy_chesscom(wins_before, draws_before, losses_before,
                      wins_after, draws_after, losses_after) -> float | None:
    cp_b = wdl_to_cp(wins_before, draws_before, losses_before)
    cp_a = wdl_to_cp(wins_after,  draws_after,  losses_after)
    wp_before = 1 / (1 + 10 ** (-cp_b / 400))
    wp_after  = 1 / (1 + 10 ** (-cp_a / 400))
    raw = max(0.0, min(1.0, 1.0 - abs(wp_before - wp_after)))
    # Same position-aware blending as WDL model
    decisiveness = abs((wins_before/1000) - 0.5) * 2
    position_weight = 1.0 - (decisiveness * 0.7)
    blended = raw * position_weight + 0.85 * (1.0 - position_weight)
    return max(0.0, min(100.0, blended * 100))
```
**Characteristics:**
- Closest to what Chess.com displays (70-90% typical)
- Measures win probability change, not deviation from perfect play
- More forgiving than Lichess model
- Users recognize this scale from their Chess.com experience

### Model 4: Maia-2 (IMPLEMENTED — maia_pass.py)
Maia-2 is a unified neural network trained to predict human moves across all skill levels
simultaneously (NeurIPS 2024, University of Toronto CSSLab).
pip: `pip install maia2`
Models: rapid (~280MB) and blitz (~280MB), downloaded on first run to ./maia2_models/.

**What makes it unique:**
Instead of "how far from perfect was this move?"
Maia-2 asks "how human-like was this move at YOUR exact rating?"

- Takes `elo_self` and `elo_oppo` as raw integers
- Returns `move_probs` (dict of UCI->probability, sorted desc) and `win_prob` (0-1 from player's perspective)
- Human win probability: more honest than engine eval for practical play

**Fields written to moves table:**
- `maia_probability`  — P(player_move | position, elo_self, elo_oppo)
- `maia_top_move_uci` — Maia's most-likely move in this position/rating context
- `maia_agreement`    — True if player chose Maia's top move
- `maia_bracket_rank` — Rank of player's move in Maia's distribution (1 = most likely)
- `maia_win_prob`     — Human win probability at player's Elo, from player's perspective
- `weakness_type`     — 'personal' | 'bracket' | NULL

**weakness_type classification:**
```
CPL < 150                    → NULL   (not a significant mistake)
CPL >= 150 + maia_prob < 15% → personal  (you miss this; others at your Elo find it → HIGH priority drill)
CPL >= 150 + maia_prob >= 15% → bracket  (everyone at your Elo misses this → lower priority)
```
This distinction is critical for prescription priority: personal weaknesses are actionable;
bracket weaknesses are normal and expected for the skill level.

**games table:**
- `avg_maia_win_prob` — AVG(maia_win_prob) for all player moves in the game

**Model selection:**
- rapid / classical / unknown → rapid_model
- blitz / bullet → blitz_model

**Usage:**
```
python maia_pass.py               # process all unprocessed player moves
python maia_pass.py --limit 10   # test mode: first 10 games
python maia_pass.py --player 1   # restrict to player_id=1
python maia_pass.py --sample     # show sample results from DB
```

**References:**
- Maia-2 GitHub: https://github.com/CSSLab/maia2
- Maia-3 (announced, not yet released): will support multi-move context and multi-agent rating

---

## 10. Mistake Classification System

### Continuous Score (Source of Truth)
```python
def compute_mistake_score(cpl, eval_before, phase, thresholds) -> float:
    """
    Returns 0.0 (perfect) to 1.0 (catastrophic).
    Uses sigmoid curve — no cliff edges.
    Phase and tension modify weight, NOT the label.
    """
    bt  = thresholds.get('blunder_cpl', 200)
    x   = (cpl - bt / 2) / max(1, bt / 4)  # sigmoid centered at bt/2
    sig = 1 / (1 + math.exp(-x))
    t   = position_tension(eval_before)       # 0=one-sided, 1=equal
    pm  = {'endgame': 1.4, 'middlegame': 1.0, 'opening': 0.6}.get(phase, 1.0)
    return min(1.0, sig * (0.4 + 0.6 * t) * pm)
```

**Why sigmoid instead of flat thresholds:**
- No cliff edges: 199 CPL and 201 CPL treated nearly identically
- ML can find the real inflection point in YOUR data
- Gradual transitions match chess reality better
- Phase multiplier: endgame errors compound (1.4x), opening errors less diagnostic (0.6x)

### Discrete Label (Derived from CPL, not score)
```python
def classify_mistake(score: float, cpl, thresholds) -> str | None:
    """
    CRITICAL: Label is driven by RAW CPL, not the continuous score.
    310 CPL is ALWAYS a blunder regardless of phase or position tension.
    Previous bug had phase modifier driving labels → 310 CPL in opening = 'inaccuracy'.
    """
    if cpl >= thresholds.get('blunder_cpl',    200): return 'blunder'
    if cpl >= thresholds.get('mistake_cpl',    100): return 'mistake'
    if cpl >= thresholds.get('inaccuracy_cpl',  50): return 'inaccuracy'
    if cpl >= thresholds.get('suboptimal_cpl',  20) and \
       score >= thresholds.get('suboptimal_score_threshold', 0.15):
        return 'suboptimal'
    return None
```

**The suboptimal_cpl category (20-50 CPL):**
A 20 CPL loss matters significantly in certain contexts:
- Position is near-equal (eval within ±30cp) → ANY loss amplified
- Endgame positions → technique errors compound over many moves
- Position has one winning plan and many drawing moves → missing plan = draw

When to classify suboptimal (not just noise):
- CPL 20-50 AND position_tension >= 0.7 AND mistake_score >= 0.15
- This catches the 1800→2000 improvement zone

**Informator symbol mapping:**
```
??  Blunder        → CPL >= 200 or mistake_score >= 0.85
?   Mistake        → CPL >= 100 or mistake_score >= 0.60
?!  Inaccuracy     → CPL >= 50  or mistake_score >= 0.35
⩲  Slight edge lost → CPL 20-50 in near-equal position
=   Holds equality  → CPL < 20, position remains balanced
```

### Multiple Labels Per Move
A single blunder can have multiple concept labels simultaneously.
Example for a 280 CPL missed fork:
```
move_concepts rows:
  missed_fork:         attribution_weight=0.85, cpl_attributed=200, is_primary_cause=TRUE
  time_pressure_error: attribution_weight=0.70, cpl_attributed=80,  is_primary_cause=FALSE
  piece_tracking_loss: attribution_weight=0.45, cpl_attributed=50,  is_primary_cause=FALSE
```
Weights don't sum to 100% — they're independent confidence scores.
Primary cause drives the study recommendation.
Secondary causes add context and refine prescription.

### Sacrifice Detection
```python
def detect_sacrifice(board, move, best_move_uci, cpl) -> tuple:
    target = board.piece_at(move.to_square)  # capturing a piece?
    if not target: return False, None
    if move.uci() == best_move_uci:    return True, 'correct'
    if cpl is not None and cpl < 50:   return True, 'reasonable'
    if cpl is not None and cpl < 150:  return True, 'speculative'
    return False, None
```
Correct and reasonable sacrifices that would otherwise be labeled blunders
have their mistake_class set to None and mistake_score set to 0.0.
This prevents sacrifices from polluting the mistake taxonomy.

### Evaluation Drift Detection
Catches cumulative small errors that individually look fine:
```python
# For each player move, compute sum of CPL over last 5 moves
window = [prev_4_cpls + current_cpl]
cumulative = sum(window)
drift_flag = (cumulative > 100 and current_cpl < inaccuracy_cpl)
```
Example: Five 22-CPL moves in a row. Each looks fine individually.
But cumulative=110 with drift_flag=TRUE reveals a pattern.
This catches the "5x 20-CPL" problem that causes 1600 players to
slowly convert won positions into draws or losses.

---

## 11. Psychological Pattern Detection

### Position Evaluation States
Every player move is tagged with position_eval_state:
```
'winning': eval_before >= +200cp (from player's perspective)
'equal':   eval_before between -200 and +200
'losing':  eval_before <= -200cp
```
This enables state-dependent analysis — the same mistake means
different things in different contexts.

### Missed Salvation (Resignation Mindset)
```
Conditions:
  1. player_eval_state == 'losing' (player was losing)
  2. Opponent just made a blunder (prev_opp_cpl >= 150)
  3. The opportunity was significant (best_eval - eval_after >= 100)
  4. Not under time pressure (tp not in critical/low)

Why it matters:
  Player has mentally accepted losing and stops calculating.
  The opponent's blunder goes unnoticed.
  Psychology: resignation mindset / learned helplessness.

Study prescription: Defensive tactics, swindle techniques,
  practical resistance exercises. Drill "find the resource" positions.
```

### Complacency Blunder
```
Conditions:
  1. player_eval_state == 'winning' (player was clearly winning)
  2. cpl >= blunder_threshold
  3. Not under time pressure

Why it matters:
  Player mentally celebrating too early, stops calculating.
  Converts winning positions into losses.

Study prescription: Converting won games, technique training,
  "stay focused when winning" exercises.
```

### Desperation Sacrifice
```
Conditions:
  1. player_eval_state == 'losing'
  2. is_sacrifice == TRUE
  3. sacrifice_correct == FALSE (not engine recommended)
  4. Not under critical time pressure

Why it matters:
  Giving material in bad positions without compensation.
  Different from a speculative sacrifice — this is panic.

vs. Swindle Attempt (POSITIVE pattern):
  player_eval_state == 'losing'
  played_rank == None (not in top 5 engine moves)
  pos_complexity > 0.6 (creates complex position)
  cpl < 150 (not a terrible move, just not optimal)
  → This is fighting spirit, not panic. Track separately.
```

### Opponent Rating Anxiety
(Future — requires population data)
```
Measurement: Group games by opponent_elo_delta (opponent - player)
Compare avg_cpl across groups:
  vs much weaker (< -200 Elo): baseline CPL
  vs similar (±100 Elo):       expected CPL
  vs stronger (+200 Elo):      elevated CPL?

anxiety_coefficient = avg_cpl_vs_stronger / avg_cpl_vs_weaker
If consistently > 1.3: pattern confirmed
```

### Tilt Detection
(Future — requires session grouping)
```
Group games by session (games within 2 hours of each other)
After a loss in session: does avg_cpl increase in next 1-3 games?
tilt_coefficient = avg_cpl_post_loss / avg_cpl_pre_loss
If consistently > 1.3: pattern confirmed
Per-move signal: time_spent < 20th percentile for that phase
                  → moving faster than usual = emotional decision-making
```

### Premove Blunder
```
is_likely_premove = time_spent_ms < 500
  (physically impossible to calculate in 0.5 seconds)
Combined with mistake_class in ('blunder', 'mistake') → premove_blunder pattern
This is a habit pattern, different from time pressure.
Study prescription: Slow down, reduce premove habits.
```

### Opening Preparation Gap (New Insight)
Player spends significantly more time thinking in a specific opening line
compared to their baseline for that phase and game type.
Cross-reference with:
- How frequently that line appears in their games
- How frequently it appears in public data at their rating
Produces a "preparation gap score" per opening variation.
Lines with high preparation gaps are flagged for targeted opening study.

**Schema needed (future):**
```sql
ALTER TABLE moves ADD COLUMN
    expected_time_ms  FLOAT,  -- player's avg time for this phase/game_type
    time_vs_expected  FLOAT;  -- actual/expected ratio (>2.0 = preparation gap)
```

---

## 12. Time Pressure System

### Philosophy
Time pressure analysis is one of the most underutilized signals in chess tools.
A blunder made with 45 seconds remaining in a blitz game is fundamentally different
from one made with 3 minutes on the clock.
Clock state changes whether a mistake is a calculation failure or a time management failure,
which changes the study prescription entirely.

### Time Pressure Classification
```python
def classify_time_pressure(clock_ms, total_time_ms, thresholds) -> str | None:
    pct = clock_ms / total_time_ms
    if pct <= thresholds.get('critical_time_pct'): return 'critical'
    if pct <= thresholds.get('low_time_pct'):      return 'low'
    if pct <= thresholds.get('normal_time_pct'):   return 'normal'
    return 'comfortable'
```

**Default thresholds by game type:**
```
         critical    low     normal
bullet:   10%        25%     50%
blitz:     8%        18%     40%
rapid:     5%        12%     30%
classical: 3%         8%     20%
```
Note: Bullet thresholds are higher because bullet chess is inherently time-pressured.
A player with 10% clock in bullet (6 seconds in 60+0) is in real trouble.
A player with 10% clock in rapid (60 seconds in 10+0) has plenty of time.

### ML-Derived Thresholds
The hardcoded defaults are starting points.
The real thresholds are player-specific and should be derived from data.

**Method: Changepoint Detection (ruptures library)**
Find the clock percentage where YOUR centipawn loss starts rising significantly.

```python
def find_personal_blunder_threshold(player_id, game_type):
    # Get all moves with clock data and CPL
    # Bin by clock percentage (0-5%, 5-10%, etc.)
    # Compute avg CPL per bin
    # Find the bin where avg CPL spikes
    # That bin's lower bound = your critical_time_pct
```

Also compare to opponent behavior:
```python
# A mistake under time pressure WITH opponent also under pressure
# → weaker signal (mutual time scramble)
# A mistake under time pressure WITH opponent comfortable
# → stronger signal (you specifically struggled with time)
```

**Opponent clock state:**
We track opponent_time_pressure on every move.
This enables:
1. Detecting mutual time scrambles (both players struggling)
2. Measuring whether opponent capitalized (needed comfortable clock)
3. Identifying if opponent-blunder exploitation correlates with your clock state

### Increment Handling
**IMPLEMENTED: Increment-aware time pressure classification**
Time control "10+5" means 10 minutes + 5 seconds per move.
The +5 seconds per move significantly changes time management.
In a 40-move game with 5-second increment, you earn back 200 seconds.

```python
def classify_time_pressure(clock_ms, total_time_ms, increment_ms,
                           total_moves, move_number, thresholds):
    if increment_ms and total_moves and move_number:
        moves_remaining = max(1, (total_moves - move_number) / 2)
        effective_clock = clock_ms + increment_ms * moves_remaining
    else:
        effective_clock = clock_ms
    pct = effective_clock / total_time_ms
    ...
```

Raw clock_ms stored as-is in the database. Only the classification uses
effective_clock. Falls back to raw clock when no increment or total_moves unknown.

---

## 13. Opening Theory Integration

### Current State
- ECO codes and opening names imported from Chess.com PGN headers
- Openings table created but NOT YET SEEDED
- Book move detection via Lichess Explorer API (live, per-move HTTP call)
- novelty_move and novelty_fen computed during analysis

### Planned: Seed Openings Table
Source: https://github.com/lichess-org/chess-openings
Format: TSV with columns: eco, name, pgn, uci, epd
3,561 named variations, maintained by Lichess.
One-time seed operation into openings table.

```python
def seed_openings_from_lichess_tsv(tsv_path: str):
    import csv
    conn = get_connection()
    cur = conn.cursor()
    with open(tsv_path) as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            cur.execute("""
                INSERT INTO openings (eco, name, pgn, uci_moves, epd)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (eco, name) DO NOTHING
            """, (row['eco'], row['name'], row['pgn'], row['uci'], row['epd']))
    conn.commit()
```

### Polyglot Opening Book — IMPLEMENTED
`books/gm2001.bin` (475KB) — GM games 2001–2013, ELO 2530+
Source: https://github.com/michaeldv/donna_opening_books
Replaces Lichess Explorer API. Zero latency. Safe for parallel workers.
Covers typical opening theory to move 12–15 for mainstream lines.
gitignored — download separately (see Section 26).

### Phase 2 Improvement: Cerebellum Opening Book
The Cerebellum book is used by Stockfish online and covers theory to move
30+ — significantly deeper than gm2001.bin. For players like StickDoggin
who know theory deeply (long novelty_move = 15+), gm2001.bin will mark
moves as novelties that are still well within theory.

**Why it matters for novelty_move accuracy:**
If a player knows a line to move 22 but gm2001.bin only covers to move 12,
novelty_move will be set to 12 and moves 12–22 will get full Stockfish
analysis (wasted compute) and incorrect moves_since_novelty counts.

**Source:** https://github.com/official-stockfish/books (look for cerebellum.bin
or Cerebellum_Light.bin). The full Cerebellum project is at cerebellum.info.
May require separate download — file is several MB.

**Action:** Replace or supplement gm2001.bin with Cerebellum in Phase 2.
Update POLYGLOT_BOOK_PATH in .env once downloaded.

### Opening Clustering (Planned)
Group similar opening variations for targeted drilling.
If struggling with Caro-Kann Advance, drill the whole Advance variation family.

Implementation approach:
1. Store full UCi move sequence per variation in openings table
2. Compute positional similarity between variations using FEN comparison
3. Cluster variants with high similarity scores
4. When a variation is flagged as a weakness, include similar variations in drill queue

### Preparation Gap Detection (Planned)
```python
def detect_preparation_gap(moves, player_baseline_time):
    for move in opening_moves:
        if move.time_spent_ms > player_baseline_time[move.phase] * 2.0:
            # Player spending 2x normal time in this opening position
            # Flag as preparation gap
            gap_score = move.time_spent_ms / player_baseline_time[move.phase]
```
Cross-reference with:
- Opening frequency in player's games (rare opening = less concerning)
- Opening frequency in public database at player's rating
- Whether the novelty point follows shortly after (quick novelty after long think)

### Opening Performance by Line
Using existing data:
```sql
SELECT
    g.opening_eco,
    g.opening_name,
    COUNT(*) as games,
    AVG(CASE WHEN g.result='win' THEN 1 ELSE 0 END) as win_rate,
    AVG(m.centipawn_loss) as avg_cpl_opening_phase,
    AVG(g.novelty_move) as avg_novelty_depth
FROM games g
JOIN moves m ON m.game_id = g.id AND m.phase = 'opening'
WHERE g.player_id = {player_id}
GROUP BY g.opening_eco, g.opening_name
HAVING COUNT(*) >= 5
ORDER BY win_rate ASC;
```

---

## 14. Player Profile and Weakness Graph

### Recency Weighting
Recent games are exponentially more relevant than old games.
Old mistakes from 1200 Elo days are nearly irrelevant at 1650.

```python
def recency_weight(played_at, current_date, half_life_days=90):
    """
    Exponential decay — weight halves every 90 days.
    Game from 90 days ago:  weight = 0.5
    Game from 180 days ago: weight = 0.25
    Game from 2 years ago:  weight ≈ 0.006 (nearly zero)
    """
    days_ago = (current_date - played_at).days
    return 0.5 ** (days_ago / half_life_days)
```

### Elo Proximity Weighting
Games at your current rating bracket are most relevant.

```python
def elo_proximity_weight(game_elo, current_elo, scale=150):
    """
    Gaussian weight centered on current Elo.
    Game at exactly current Elo:     weight = 1.0
    Game 150 Elo away:               weight = 0.61
    Game 300 Elo away:               weight = 0.14
    """
    return math.exp(-((game_elo - current_elo) ** 2) / (2 * scale ** 2))
```

**Combined weight:**
```python
def game_weight(played_at, game_elo, current_elo, current_date):
    return recency_weight(played_at, current_date) * \
           elo_proximity_weight(game_elo, current_elo)
```

### Weakness Status Lifecycle
```
'active'     → weakness is occurring regularly
'improving'  → occurrence rate decreasing over 30 days
'resolved'   → hasn't occurred in 30+ days after being active
'regressed'  → was resolved, then reappeared
```
A weakness marked 'resolved' that reappears in 3 games → 'regressed'
Regression count tracked, jumps back up priority queue.
Chess improvement is NOT linear — concepts re-emerge under time pressure.

### Exploitability Score
Populated by cross-game aggregation (future):
Of all times this mistake pattern appeared at this Elo bracket,
what fraction led to opponent gaining decisive advantage within 5 moves?

```
High CPL + high exploitability + opponent comfortable = URGENT study priority
High CPL + low exploitability + opponent under time pressure = Lower priority
Low CPL  + high exploitability = Hidden weakness (sneaky, important)
High CPL + opponent also blundered back = Mutual time scramble, different fix
```

The third case (low CPL + high exploitability) is missed by every existing tool.
These are positional mistakes the engine barely penalizes but better players punish.
Critical for breaking through rating plateaus.

### Prescription Ordering
Naive approach: fix worst weakness first.
Correct approach: maximize Elo-per-study-hour efficiency.

```python
def study_efficiency(weakness):
    return weakness['estimated_elo_impact'] / weakness['estimated_study_hours']

# Example:
# Weakness A: +25 Elo, 2 hours study → efficiency 12.5 Elo/hour
# Weakness B: +40 Elo, 20 hours study → efficiency 2.0 Elo/hour
# Weakness C: +15 Elo, 1 hour study  → efficiency 15.0 Elo/hour
# Order: C first, A second, B last
# Total gain: 80 Elo in 23 hours vs 40 Elo in 20 hours (naive)
```

---

## 15. Threshold System and ML Readiness

### The Core Principle
Every threshold is a row in player_thresholds table, NOT a code constant.
Code reads thresholds at runtime. ML updates the table, not the code.
This is the single most important ML-readiness decision.

### Continuous Scores, Derived Labels
```
ALWAYS store: mistake_score (FLOAT 0.0-1.0) — this is the source of truth
DERIVE from score: mistake_class (TEXT) — display only, queryable

When ML retrains: it updates mistake_score calculation
                  mistake_class follows automatically
Never retrain by changing the label directly
```

### Version Tracking
```sql
-- Every threshold row has a version
version     INTEGER DEFAULT 1
derived_from TEXT DEFAULT 'default_v1'
-- 'default_v1', 'statistical_v2', 'changepoint_v3', 'neural_v4'
```

### Sigmoid Curves Everywhere
No cliff edges. Everything is a smooth transition.
```
Hard threshold (old):  199 CPL = fine, 200 CPL = blunder
Sigmoid (current):     continuous score, label derived from CPL bracket
                        but score reflects context
```

### ML Progression Timeline
```
Phase 1 (NOW): Rules-based with sigmoid scoring
  - Hardcoded defaults in player_thresholds
  - CPL-based labels
  - Context-aware scores (phase, tension)

Phase 2 (after 200+ games analyzed): Statistical personalization
  - Win-rate analysis finds YOUR actual CPL thresholds
  - Where YOUR win rate drops below 40% vs CPL
  - Updates player_thresholds with source='statistical'

Phase 3 (after 500+ games): Changepoint detection
  - ruptures library (needs C++ Build Tools for Python 3.14)
  - Automated inflection point detection per player per game type
  - Updates player_thresholds with source='changepoint'

Phase 4 (after 2000+ games): Neural network outcome predictor
  - Small PyTorch model, trained on YOUR game history
  - Input: raw board features (eval, tension, complexity, time, etc.)
  - Output: probability this mistake leads to losing the game
  - Replaces hand-crafted severity formula
  - Updates player_thresholds with source='neural'

Phase 5 (population level, multi-user):
  - Train on all users' data
  - Bracket-specific models (1400-1600, 1600-1800, etc.)
  - Personalization = fine-tuning on top of population model
```

### ruptures Library Status
ruptures 1.1.9 requires Microsoft C++ Build Tools to compile on Windows.
Not installed yet. Install Microsoft C++ Build Tools (free, ~6GB) when needed.
Available at: https://visualstudio.microsoft.com/visual-cpp-build-tools/
Alternative: use scipy's signal processing for simpler changepoint detection.

---

## 16. Study Module Architecture

### Six Study Modules

**1. Opening Drill Module**
- Not generic opening theory — only lines from player's actual repertoire
- Only positions where player deviated from theory or blundered
- Interactive move-order trainer (like ChessLine's Lines view)
- Tests variations N moves beyond the blunder point
- Weighted by opening frequency in player's games
- Source: novelty_move + moves_since_novelty data from analysis

**2. Tactical Depth Trainer**
- Puzzles sorted by minimum required calculation depth
- Player's "depth ceiling" tracked over time (avg_tactical_depth_failed)
- If player misses 4-ply calculations → deliver 5-6+ ply drills
- Timed calculation challenges
- Visualization exercises (no-board mode)
- Similar-motif clustering (player sees variants of same pattern)

**3. Endgame Module**
- Not generic endgame theory — exact endgame types player lost from winning
- Tablebase-verified training positions
- K+P vs K, rook endings, opposite bishops, etc. as identified by analysis
- Reconstructs player's own failed endgames as exercises
- Technique approach over memorization

**4. Professional Game Study**
- GM games selected because they match player's specific pattern gap
- Guess-the-move mode at critical decision points
- GM vs player decision compared with reasoning
- Source: professional_games corpus (future table, tagged by concept)

**5. Visualization Trainer**
- For players who lose track of pieces during calculation
- No-board exercises
- Position presented, then hidden — player tracks moves mentally
- Progressive depth (2-move to 8-move sequences)
- Blindfold chess warmups

**6. Positional Concept Trainer**
- Strategic concept exercises tied to identified positional misjudgments
- Minority attack, prophylaxis, piece coordination exercises
- Uses Silman's seven imbalances as framework

### Spaced Repetition (SM-2 Algorithm)
Used for drill_positions table.
Same algorithm as Anki — well-documented, proven for memory retention.

```python
def sm2_update(ease_factor, interval, quality):
    """
    quality: 0-5 (0=complete blackout, 5=perfect response)
    Returns new (ease_factor, interval)
    """
    if quality >= 3:
        if interval == 0:   new_interval = 1
        elif interval == 1: new_interval = 6
        else:               new_interval = round(interval * ease_factor)
        new_ef = ease_factor + (0.1 - (5-quality) * (0.08 + (5-quality)*0.02))
        new_ef = max(1.3, new_ef)
    else:
        new_interval = 0  # reset
        new_ef = ease_factor
    return new_ef, new_interval
```

### Drill Difficulty Targeting
Optimal success rate for learning: 70-80%.
Below 60%: too hard, discouraging.
Above 85%: too easy, not building new pathways.

```python
def adjust_difficulty(recent_success_rate, current_difficulty):
    if recent_success_rate < 0.60:
        return max(0.1, current_difficulty - 0.1)  # easier
    if recent_success_rate > 0.85:
        return min(1.0, current_difficulty + 0.1)  # harder
    return current_difficulty  # stay the same
```

### Drill Encoding Specificity
Key principle: drill the EXACT position from YOUR game.
Not a similar position — the exact position with your pieces, your pawn structure.
This is what your brain needs to recognize in the future.

Plus interleaving: mix concept types in each drill session.
Don't do 20 fork puzzles then 20 pin puzzles.
Do: fork, pin, back-rank, fork, endgame, pin (interleaved).
Research shows interleaved practice is harder but produces better retention.

### Hint Ladder — "Shut Up and Calculate" Pedagogy

When showing a player their own game positions as drills, never give away the
answer immediately. Use a hint ladder — the player earns the answer by
calculating, not by being shown it.

| Level | What the player sees | XP cost |
|-------|---------------------|---------|
| 0 | Position shown, clock running → "Find the best move" | 0 (full XP) |
| 1 | "There is a tactical opportunity in this position" | −10% XP |
| 2 | Theme revealed → "Look for a [fork / pin / deflection]" | −30% XP |
| 3 | Piece identified → "Your knight on f5 can create threats" | −60% XP |
| 4 | Full solution shown | −100% XP (0 XP) |

The default session uses Level 0–1. Levels 2–4 are genuine rescue for stuck players.

**Theoretical basis:** The goal of tactical training is to make patterns
**pre-conscious** — recognized instantly without deliberate calculation, the same
way a reader sees a word without sounding out letters. A grandmaster doesn't
calculate a fork — they SEE it. This perceptual automaticity is built through
thousands of repetitions.

- Level 0–1 drills train both pattern recognition AND calculation.
- Level 2 (theme revealed) trains pattern recognition only.
- Hints at Level 0–1 produce the deepest learning because the player must
  search the entire pattern space.

This is "desirable difficulty": the harder retrieval attempt, when successful,
encodes the pattern more durably. Never short-circuit that process.

**Prescription language:** Frame drill goals as "Train your eye to see X,"
not "Practice calculating X." The goal is perceptual, not computational.

---

## 17. AI Opponent System

### Overview
A Maia-2-powered opponent that plays human-like moves at the player's exact Elo level,
weighted to steer games toward positions exposing the player's weaknesses.
No existing tool does this. Chessiverse has human-like bots but they're generic.

**Why Maia-2 over Stockfish skill-level simulation:**
Stockfish at lower skill levels plays randomly bad moves — not human-like bad moves.
Maia-2 plays the moves actual humans at that Elo play, including their specific error patterns.
This makes practice games feel real and creates positions where the player's weaknesses
actually arise (because Maia-2 produces the same board situations humans produce).
Inputs: `elo_self` (Maia's Elo) + `elo_oppo` (player's Elo) for full two-sided context.

### Three Opponent Modes

**Mirror Mode:**
Plays at player's exact current Elo.
Uses weakness graph to select moves that create positions player historically mishandles.
Goal: realistic practice against someone "like you" who knows where to push.

**Preset Mode:**
Any fixed Elo (800-2800).
Still weakness-weighted — a 1400-rated opponent that knows you blunder in Caro-Kann
will play the Caro-Kann every time.
Goal: practice against weaker/stronger opponents in your specific problem areas.

**Pure Training Mode:**
Not trying to win — trying to create positions.
Steers toward player's weakest concept categories regardless of who's winning.
Goal: maximum exposure to problem positions in game-like context.

### Weakness Steering Implementation
```python
def select_opponent_move(board, weakness_graph, target_elo):
    candidates = engine.analyse(board, multipv=5,
                                skill_level=elo_to_skill(target_elo))
    scored = []
    for move in candidates:
        board.push(move)
        weakness_score = evaluate_weakness_exposure(board, weakness_graph)
        engine_score = candidates[move]["cp"]
        combined = (0.6 * engine_score) + (0.4 * weakness_score * 100)
        scored.append((move, combined))
        board.pop()
    return max(scored, key=lambda x: x[1])[0]
```

### Elo Calibration
Stockfish skill levels 0-20 mapped to Elo:
```python
ELO_TO_SKILL = {
    800:1, 900:3, 1000:5, 1100:7, 1200:9, 1300:11,
    1400:13, 1500:14, 1600:15, 1700:16, 1800:17,
    1900:18, 2000:18, 2200:19, 2500:20
}
# Also use time limits to fine-tune strength between skill levels
ELO_TO_MOVETIME = {
    800:0.05, 1000:0.1, 1200:0.2, 1400:0.3,
    1600:0.5, 1800:1.0, 2000:2.0, 2200:5.0, 2500:10.0
}
```

### AI Games Table (Planned)
```sql
CREATE TABLE ai_games (
    id                  SERIAL PRIMARY KEY,
    player_id           INTEGER REFERENCES players(id),
    played_at           TIMESTAMPTZ DEFAULT NOW(),
    opponent_mode       TEXT,      -- 'mirror','preset','training'
    target_elo          INTEGER,
    weakness_codes      TEXT[],    -- which weaknesses were targeted
    player_color        TEXT,
    result              TEXT,
    weakness_triggered  INTEGER,   -- how many times target weakness appeared
    weakness_exploited  INTEGER,   -- how many times player failed it
    exposure_rate       FLOAT,     -- weakness_exploited / weakness_triggered
    raw_pgn             TEXT
);
```

### The Feedback Loop
After each AI game:
- Was the target weakness triggered? (did those positions arise?)
- Did the player handle them correctly this time?
- Yes → decrease weakness weight, increase drill difficulty
- No → increase weakness weight, queue more drills

This creates: analyze real games → identify weakness → drill it →
play AI games exposing it → measure improvement → update weakness graph → repeat.

**Build point:** After pattern detector and weakness aggregator are solid
(need populated weakness_graph with real data to steer intelligently).
Estimated: after 500+ games analyzed.

---

## 18. Gamification and Retention

### XP System — Skill-Specific
NOT a generic point pool. Separate XP bars per skill category.

```
Tactics XP:      earned from tactical drill completions, puzzle solving
Openings XP:     earned from opening line training, deviation corrections
Endgames XP:     earned from endgame position mastery
Visualization XP: earned from no-board calculation exercises
Calculation XP:  earned from depth-extending exercises
```

XP earned is proportional to difficulty — hard problems earn more XP than easy ones.
This prevents "grinding easy puzzles for XP" gaming of the system.

### Session Quality Multiplier
```python
session_multiplier = 1.0 + (avg_difficulty - 0.5) * 0.4
# Difficulty 0.5 (normal): 1.0x
# Difficulty 0.8 (hard):   1.12x
# Difficulty 0.3 (easy):   0.92x
```

### Mistake Memory System
The most important gamification layer:
- Every mistake from player's own games becomes a drill position
- SM-2 spaced repetition surfaces it again just before forgetting
- "Name the pattern" challenge before showing solution
- Player writes why they made the mistake (narrative tagging)
- Emotional tagging (tilt, fatigue, time pressure, didn't see it)
- Blunder highlight reel from own games (video-style replay)
- "This is what you played vs what you should have played" side-by-side

Why narrative tagging matters:
Research shows encoding WHY you erred dramatically improves retention.
"I moved my knight without considering the back rank" sticks better
than just "missed back rank mate."

### Insight Feed
After each new game syncs, player receives a personalized insight card:
- "You missed a fork on move 23 — this is the 4th time in this opening"
- "Your accuracy in endgames improved +12% this week"
- "Same pattern as your blunder vs Player123 last month"
- "You played the engine's top choice for 18 straight moves"
- "New weakness detected: underestimating kingside attacks"

These are natural-language summaries generated from the database queries,
not generic notifications.

### Progress Dashboard
- Weakness heatmap across game phases (before/after study period)
- Centipawn loss trend (rolling 30-day average)
- Accuracy by opening line
- Projected Elo gain from current study trajectory
- Comparison with peer players at same rating bracket
- Session history and weekly study cadence

### Point-in-Time Strength Snapshots
The player_snapshots table captures full weakness profile at any date.
Enables: "here's what your game looked like 3 months ago vs today"
With real data behind it — not just Elo, but specific concepts that improved.

### Progressive Analysis UX
When a new user signs up and their games are being analyzed, do not make them
wait for 100% completion before showing results. Show a progressive weakness
profile that updates as more games are analyzed.

**Confidence tiers:**
```
≥  50 games analyzed: preliminary profile, low confidence indicators
≥ 200 games analyzed: emerging patterns, medium confidence
≥ 500 games analyzed: full profile, high confidence
= all games analyzed: complete profile
```

Every weakness card and insight shown to the user must include a confidence label:
```
"Based on 127 of 1,847 games analyzed (7%) — insights will improve"
"Based on 891 of 1,847 games analyzed (48%) — moderate confidence"
"Based on 1,847 of 1,847 games analyzed (100%)"
```

**Why this works:**
- The priority queue already analyzes most-relevant games first (recent losses
  at current Elo bracket), so early results are the most representative sample
- Users see immediate value and watch it improve — better retention than a blank screen
- Transparent confidence labeling prevents confusion when results shift as more
  games are analyzed
- Weakness patterns emerging from 50 games are real signal, not noise

**Parallel analysis ordering note:**
Parallel analysis completes games in non-deterministic order (worker completion
order, not priority order) — this is fine for data quality but the user-facing
feed should sort by game date descending regardless of analysis completion order.
The weakness_graph aggregation must weight by recency regardless of the order
in which analysis jobs happen to finish.

---

## 19. Performance and Scalability

### Current Bottleneck
Sequential Stockfish analysis: ~0.9 games/minute.
10,921 games ÷ 0.9 = ~200 hours sequential.

### Parallelization
Already architected for it. Each worker:
- Opens its own Stockfish process (engine.configure({'Threads': 1}))
- Gets its own database connection (get_connection())
- Processes one game from start to finish
- Writes results atomically

```python
# Enable parallel mode (run in a dedicated PowerShell window):
run_analysis_queue(batch_size=11000, parallel=True)
# Uses ProcessPoolExecutor with cpu_count()-1 workers
```

**This machine: 12 logical cores → 11 workers**
Expected speed: 11 workers × ~0.9 games/min = ~9.9 games/min
~10,850 remaining games ÷ 9.9 = ~18 hours for full run.

### Batch Database Writes
All moves for a game are written in a single batch at the end.
Not move-by-move commits. This is ~10x faster for the database layer.

### Book Move Skipping
20-30% of moves are book moves (opening theory).
These skip Stockfish analysis entirely.
IMPLEMENTED: Local Polyglot book (gm2001.bin) — zero latency, no API calls.

### Incremental Analysis
Analyzed games are never touched again (analyzed = TRUE).
New games imported → added to queue → only new games processed.
The system only ever works on the delta.

### Priority Queue
Not FIFO — highest impact games analyzed first:
- Recent games (more relevant to current skill)
- Losses (more mistakes)
- Rapid/blitz (primary time controls)
- Games near current Elo bracket

### Database Indexes
Created on all high-frequency query paths:
```sql
idx_moves_game_id, idx_moves_player_id, idx_moves_mistake_class
idx_moves_phase, idx_games_analyzed, idx_games_played_at
idx_games_game_type, idx_analysis_queue_status, idx_analysis_queue_priority
idx_weakness_graph_player, idx_elo_history_player, idx_drill_positions_review
idx_moves_mistake_score, idx_moves_eval_state, idx_moves_missed_salvation
idx_games_accuracy, idx_games_advantage_surrendered
idx_thresholds_lookup, idx_eval_state_perf
```

### Long Game Handling
Games > 80 moves get LONG_GAME_FACTOR = 0.6 applied to all time limits.
Previously a 124-move game took 97 seconds.
With factor: ~58 seconds.
Ensures no single game becomes a blocking bottleneck.

---

## 20. Cloud Compute Roadmap

### Why Cloud
Local machine: 8-16 cores, intermittent availability, power dependent.
Cloud VM: 24/7 availability, dedicated cores, remote management.

### Recommended: Hetzner or DigitalOcean
```
Hetzner CX31:  4 vCPU, 8GB RAM, €8/month (~$9/month)
  → ~4 Stockfish workers (1 core each + 1 for OS)
  → ~4x speedup vs local sequential
  → 10,921 games ÷ 3.6 games/min = ~50 hours initial analysis

Hetzner CPX41: 8 vCPU, 16GB RAM, €18/month (~$20/month)
  → ~7 workers
  → ~7x speedup
  → 10,921 games ÷ 6.3 games/min = ~29 hours initial analysis

DigitalOcean similar pricing and specs.
```

### Architecture for Cloud
Postgres stays local during development, migrates to managed cloud DB later.
Cloud VM connects to Postgres over network (already using 127.0.0.1 in .env).
Change DB_HOST in .env → cloud VM connects immediately.

### Managed Postgres Options
```
Supabase free tier: 500MB, sufficient for initial phase
Railway:            $5/month, 1GB, good developer experience
Neon:               free tier, serverless Postgres, auto-scaling
DigitalOcean:       $15/month, managed, daily backups
```

### Cerebellum Opening Book (Medium Priority)
The current `gm2001.bin` Polyglot book covers theory to approximately move 12
on average. The Cerebellum book (used by Stockfish's online play) covers theory
to move 30+ — significantly deeper for players who know theory well.

**Why it matters for novelty_move accuracy:**
If a player knows a line to move 22 but gm2001.bin only covers to move 12,
`novelty_move` is set to 12 and moves 12–22 receive full Stockfish analysis
(wasted compute) plus incorrect `moves_since_novelty` counts. This degrades
opening performance tracking and preparation gap detection for well-prepared
players.

**Download status:** UNVERIFIED — do not use the official-stockfish/books
GitHub URL (that repo does not exist). Investigate these sources before
integrating:
- https://rebel13.nl/download/books.html
- Search "Cerebellum opening book download" for current hosting
- The Cerebellum project may have its own distribution site

**Priority:** Medium — implement after full analysis run completes and the
weakness aggregation layer is built. Update POLYGLOT_BOOK_PATH in .env once
a verified source is confirmed.

### Future: Distributed Analysis
When user base grows:
- Multiple cloud VMs, each running analysis workers
- Central Postgres (managed cloud)
- Job queue in database (already designed for this)
- Each VM polls queue, claims jobs, processes, writes back
- Scales horizontally by adding VMs

---

## 21. File Reference — Current Codebase

### db_setup.py
**Purpose:** Database initialization, table creation, utility functions
**Key functions:**
- `get_connection()` — returns psycopg connection using .env credentials
- `create_tables()` — creates all core tables (idempotent, uses IF NOT EXISTS)
- `add_analysis_columns()` — adds analyzed/analysis_priority/analyzed_at to games
- `fetch_and_store_current_ratings(username)` — pulls current ratings from Chess.com
- `populate_analysis_queue(username)` — adds all unanalyzed games to queue with priority scoring

**Important:** Every other script imports `get_connection` from this file.
Do not change the function signature.

**Status:** Complete and working.

### import_chesscom.py
**Purpose:** Import full game history from Chess.com
**Key functions:**
- `import_all_games(username)` — fetches all monthly archives and processes each
- `fetch_archive_urls(username)` — gets list of all monthly archive URLs
- `parse_and_insert_game(cur, game_data, player_id, username)` — parses PGN and inserts

**Status:** Complete and working. 10,921 games imported for StickDoggin.
**Known issue:** 2 games had errors (malformed PGN on Chess.com's end). Acceptable.

### seed_concepts.py
**Purpose:** Populates the concepts table with the full chess knowledge ontology
**Status:** Complete and working. 176 concepts inserted.

### schema_update.py
**Purpose:** First schema update — adds analysis tables, study tables, indexes
**Run once:** Creates analysis_queue, player_snapshots, weakness_graph, concept_study_mapping,
             drill_positions, drill_attempts, study_sessions, import_log, analysis_log.
             Also adds analyzed/novelty columns to games, attribution columns to move_concepts.
**Status:** Complete and run successfully.

### schema_update2.py
**Purpose:** Second schema update — adds psychological and ML columns
**Run once:** Creates player_thresholds, evaluation_state_performance.
             Adds psychological columns to moves (missed_salvation, resignation_mindset, etc.)
             Adds psychological columns to games (missed_salvations, advantage_surrendered, etc.)
             Adds status columns to weakness_graph (mastery_score, regression_count, etc.)
             Seeds 58 default thresholds.
             Creates additional indexes.
**Status:** Complete and run successfully.

### analyze_games.py
**Purpose:** Main Stockfish analysis engine. Processes games from analysis_queue.
**Key functions:**
- `load_thresholds(game_type)` — loads thresholds from database
- `open_polyglot_book()` — opens gm2001.bin for local book move detection
- `is_book_move(book, board, move)` — Polyglot lookup, replaces Lichess API
- `open_syzygy()` — opens Syzygy tablebase reader for <=5-piece positions
- `get_tablebase_info(board_before, board_after, syzygy_tb)` — DTZ/WDL lookup
- `extract_wdl_for_player(score, player_color)` — WDL from player's perspective (BEFORE move)
- `extract_wdl_after_move(score, player_color)` — WDL from player's perspective (AFTER move)
- `accuracy_wdl(...)` — Stockfish WDL accuracy model (position-aware)
- `accuracy_lichess(cpl)` — CPL-based strict accuracy
- `accuracy_chesscom(...)` — Win probability delta accuracy
- `compute_mistake_score(cpl, eval_before, phase, thresholds)` — sigmoid continuous score
- `classify_mistake(score, cpl, thresholds)` — discrete label from CPL (NOT score)
- `classify_time_pressure(clock_ms, total_time_ms, increment_ms, total_moves, move_number, thresholds)` — increment-aware 4-level classification
- `detect_sacrifice(board, move, best_move_uci, cpl)` — identifies sacrifices
- `detect_psychological_patterns(...)` — missed_salvation, complacency detection
- `analyse_position(engine, board, ...)` — hybrid time+depth analysis with min_depth guarantee
- `analyze_single_game(game_id)` — full analysis of one game
- `run_analysis_queue(batch_size, parallel)` — processes queue

**Current mode:** Sequential, batch_size=20 (in __main__)
**Full run command (parallel, all games):** See Section 26

**All known bugs fixed:**
1. WDL perspective error — fixed with extract_wdl_for_player/after_move
2. CPL not capped before storage — fixed, now min(cpl_raw, CPL_CAP)
3. Accuracy formula — fixed with position-aware blending
4. Classification labels wrong — fixed, labels now CPL-primary
5. Short games — filtered in queue query
6. Lichess API latency — replaced with local Polyglot book
7. Spurious ALTER TABLE per game — removed

**Validated:** 10-game test run confirmed WDL=85–89%, book_moves populate
on opening plies, tablebase_result populates on <=5-piece endgames, 0 errors.

**Status:** Ready for full parallel run.

### .env
```
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=chess_engine
DB_USER=postgres
DB_PASSWORD=0088
STOCKFISH_PATH=C:\Users\karlb\chess-study-engine\stockfish\stockfish-windows-x86-64-avx2.exe
POLYGLOT_BOOK_PATH=C:\Users\karlb\chess-study-engine\books\gm2001.bin
SYZYGY_PATH=C:\Users\karlb\chess-study-engine\syzygy
```
gitignored — never commit this file.

### stockfish/
```
stockfish-windows-x86-64-avx2.exe  (111MB)
```
Stockfish 18.3. AVX2 = modern CPU instruction set (faster than base version).
gitignored — download from https://stockfishchess.org/download/ (Windows AVX2).

### books/
```
gm2001.bin  (475KB)
```
Polyglot opening book — GM games 2001–2013, ELO 2530+.
gitignored — download from https://github.com/michaeldv/donna_opening_books

### syzygy/
```
290 files (.rtbw + .rtbz pairs), 938MB total, largest file 30.87MB
3-piece, 4-piece, and 5-piece Syzygy endgame tablebases
```
gitignored — download with the PowerShell script in Section 26.

---

## 22. Current Status and Known Issues

### What's Working
- [x] PostgreSQL database with full schema (30+ tables)
- [x] 176 chess concepts seeded
- [x] 10,921 games imported from Chess.com (StickDoggin)
- [x] Current ratings fetched (rapid=1656, blitz=1632)
- [x] Analysis queue populated with priority scores (10,921 games)
- [x] **6,088/10,921 games analyzed (56% — full run in progress as of 2026-05-11)**
- [x] Stockfish 18.3 installed and working
- [x] Hybrid time/depth analysis system working
- [x] Three accuracy models implemented (WDL=85–89%, Lichess=35–63%, Chess.com=85–89%)
- [x] Mistake scoring system (sigmoid + CPL-primary labels)
- [x] Sacrifice detection working
- [x] Increment-aware time pressure classification
- [x] Psychological pattern detection implemented
- [x] Drift flag detection implemented
- [x] Book move detection via local Polyglot book (gm2001.bin, zero latency)
- [x] Syzygy 3-4-5 piece tablebases integrated (938MB, 290 files)
- [x] best_move_san stored alongside best_move_uci
- [x] 58 default thresholds in database
- [x] Parallel analysis mode available (11 workers on this machine)
- [x] Session detector: 2,718 sessions grouped, tilt=5.4%, fatigue=8.4%
- [x] Weakness aggregator: produces ranked weakness profile with study recommendations
- [x] 5,441,692 Lichess puzzles seeded (23 min, 3,910/s) — all concept codes mapped
- [x] Drill session engine: SM-2 spaced repetition, 70/30 own-game/Lichess mix
- [x] Opening prep gap detector: recency-weighted, 90-day half-life, stale>180d filter
- [x] opening_name/opening_var backfilled from ECOUrl for all 10,890 games (99.7%)

### Opening Prep Gap Results (as of 2026-05-11, 56% analyzed)

10 active gaps detected, 27 lines correctly excluded as stale (>180 days old):

**Confirmed Recent (active gaps):**
- A45 Indian Game — 15d ago, 3.82x baseline, 72% loss rate (strongest gap)
- D02 London System — 6d ago, 1.73x baseline, 50% loss rate (very recent)
- B22 Alapin Sicilian Defense — 37d ago, 1.47x, 43% loss rate
- C64 Ruy Lopez - Classical Central Variation — 35d ago, 1.47x, 78% loss rate
- D00 Queens Pawn Opening — 85d ago, 1.33x, 100% loss rate
- B12 Advance Botvinnik Carls Defense — 9d ago, 1.26x, 12% loss rate

**Historically Stale (correctly excluded):**
- A04 Kingside Fianchetto (230d), C23 Bishop's Opening (613d), C20 (601d),
  C21 Center Game (632d), B40 French Variation (250d) — all pre-2025 patterns

**Pre-fix comparison:** The unweighted version showed C65/A30/B30 as top gaps with
ratios of 4.23/3.92/2.98 — but all three were stale (not played recently). The
recency-weighted version correctly surfaced the current gaps instead.

### Known Bugs / Issues

**Issue 1: WDL accuracy numbers**
Status: Fixed in latest analyze_games.py (extract_wdl_for_player/after_move).
Previous bug: WDL not taking player color perspective correctly.
Result: WDL=None for all games.
Fix: Use score.white().wdl() then flip based on player_color.
Needs: Test run to verify fixed.

**Issue 2: Accuracy values too low for Lichess model**
Status: Expected behavior, not a bug.
Lichess formula at depth 14-18 produces 30-60% for 1650 player.
Other tools show 75-95% because they use win probability not CPL deviation.
WDL and Chess.com models will show 70-85%.

**Issue 3: Classification labels incorrect (310 CPL = inaccuracy)**
Status: Fixed in latest version.
Previous bug: Phase multiplier (0.6 for opening) was affecting the LABEL
not just the weight. 310 CPL in opening phase → score=0.3 → 'inaccuracy'.
Fix: Labels now derived from raw CPL only. Phase affects score, not label.

**Issue 4: CPL values of 9270 in database**
Status: Fixed in latest version.
Previous bug: CPL was capped for averaging but not before storage.
Fix: cpl = min(cpl_raw, CPL_CAP) immediately after calculation.

**Issue 5: accuracy=None for some games**
Status: Fixed in latest version.
Previous bug: player_color case mismatch ('White' vs 'white').
Fix: player_color = (player_color or '').lower() at start of analysis.

**Issue 6: Lichess Explorer API calls slow down analysis**
Status: FIXED. Replaced with local Polyglot book (gm2001.bin).
Zero latency. No network dependency. Safe for parallel workers.

**Issue 7: Very long games (124+ moves) block queue**
Status: Mitigated with LONG_GAME_FACTOR = 0.6.
Still takes 60-90 seconds per game instead of potential 150+ seconds.
Acceptable for now.

**Issue 8: Opponent capitalization not yet computed**
Status: Design complete, implementation pending.
Currently opponent_capitalized is NULL for all moves.
Second pass needed: after flagging player mistakes, analyze opponent's
next 5 moves to see if they found the punishing continuation.

**Issue 9: accuracy_chesscom values from May 2026 full analysis run are incorrect**
Status: KNOWN — run `recalc_chesscom_accuracy.py` after full analysis completes.
Root cause: The circular conversion bug (wdl_to_cp → win_prob_from_cp = identity)
was fixed in analyze_games.py AFTER the full 10,921-game run started (May 2026).
All games analyzed during that run have accuracy_chesscom ≈ accuracy_wdl because
the old formula was a mathematical no-op.
Fix: Run `python recalc_chesscom_accuracy.py` after the full run completes.
This recomputes accuracy_chesscom from eval_before/eval_after using the correct
CP-based formula. No Stockfish re-run needed.
Do NOT run this during active analysis — wait until the run finishes.

**Issue 10: CPL uncapped for ~100 moves from mate-score edge cases**
Status: FIXED. Cleaned up May 2026.
Root cause: When best_cp = mate score (9999) and eval_after = opposing mate score
(-9999), cpl_raw = ~20000 before the min() cap fires. The cap was present but
the inputs were not pre-clamped. 100 rows had CPL 500-10565.
Fix: Pre-clamp both eval inputs to [-1000, +1000] before subtraction.
Cleanup: `UPDATE moves SET centipawn_loss = 500 WHERE centipawn_loss > 500` — fixed.

### Data Status (as of 2026-05-11)
```
Database:          chess_engine on PostgreSQL 18.3
Player:            StickDoggin (chess.com, id=1)
Games:             10,921 imported
Games analyzed:    6,088 / 10,921 (56% — full run in progress)
Games pending:     4,833 in analysis_queue
Moves in DB:       ~819,075 (10,921 x avg 75 moves)
Concepts:          176
Thresholds:        58 default rows
Drill positions:   5,441,692 (Lichess puzzles, all concept codes)
Sessions:          2,718 detected (avg 4.0 games, max 58)
Machine:           12 logical cores -> 11 parallel workers
```

### Post-Full-Run Checklist (run IN ORDER after analysis completes)
```
1. python recalc_chesscom_accuracy.py        # fix circular bug in May 2026 run
2. python pattern_detector.py               # apply 3.3.6 demotion to all games
3. python session_detector.py --clear       # regroup sessions with final data
4. python opening_prep_gap.py 1 --save      # save recency-weighted gaps
5. python weakness_aggregator.py 1 all      # generate final weakness profile
```

---

## 23. Build Order — What's Done and What's Next

### Phase 1: Foundation (COMPLETE)
- [x] Database schema design
- [x] Chess knowledge ontology (176 concepts)
- [x] Chess.com game importer
- [x] Stockfish analysis pipeline (sequential)
- [x] Three accuracy models
- [x] Mistake classification (sigmoid + CPL-primary labels)
- [x] Time pressure analysis
- [x] Psychological pattern detection
- [x] WDL extraction and perspective correction
- [x] Schema updates 1 and 2

### Phase 2: Analysis Completion (CURRENT)
- [x] Validate latest analyze_games.py fixes with test run (10 games, 0 errors)
- [x] Download and integrate Polyglot opening book — gm2001.bin (replaces API)
- [x] Integrate Syzygy 3-4-5 piece tablebases (938MB, tablebase_result populated)
- [x] Increment-aware time pressure classification
- [ ] **NEXT: Run full parallel analysis on all ~10,836 remaining games (~18 hours)**
- [ ] Seed openings table from Lichess TSV
- [ ] Upgrade to Cerebellum opening book for deeper novelty_move detection
- [ ] Implement opponent capitalization (second pass analysis)

### Phase 3: Pattern Detection
- [x] Mathematical pattern detector — pattern_detector.py (fork, pin, skewer, etc.)
- [x] Concept tagger — per-game, populates move_concepts table
- [x] Session detector — groups within 2h, detects tilt + fatigue
- [x] Opening preparation gap detector — recency-weighted, 90d half-life
- [ ] Positional feature extractor (Silman's seven imbalances)
- [ ] Opponent capitalization second pass

### Phase 4: Weakness Aggregation
- [x] Cross-game weakness aggregator — weakness_aggregator.py
- [x] Recency + Elo proximity weighting (0.5^(days/90) * exp(-dElo^2/45000))
- [x] Elo impact estimation (heuristic: min(50, avg_cpl*occurrence_rate*0.15))
- [x] Session-level psychological weaknesses (tilt, fatigue) in weakness_graph
- [x] Opening prep gaps in weakness_graph (game_type='opening')
- [ ] Point-in-time snapshot generator (player_snapshots table)
- [ ] Evaluation state performance aggregator

### Phase 5: Statistical ML
- [ ] Install Microsoft C++ Build Tools (for ruptures library)
- [ ] Install ruptures library for changepoint detection
- [ ] Time pressure threshold derivation from player's actual data
- [ ] Win-rate analysis to find personal CPL thresholds
- [ ] Personal threshold updates in player_thresholds table

### Phase 6: Study Modules (Basic)
- [x] Drill position seeding — 5,441,692 Lichess puzzles across all concept codes
- [x] SM-2 spaced repetition scheduler — drill_session.py
- [x] Concept study mapping — seed_curriculum.py (83 rows)
- [x] Prescription engine — weakness_aggregator.py generate_prescription()
- [ ] Opening deviation drill (using novelty_move data)
- [ ] Player's own game positions seeded to drill_positions (from pattern_detector)

### Phase 7: Frontend/API  <- NEXT PRIORITY
- [ ] REST API layer (FastAPI recommended)
- [ ] Authentication system
- [ ] Basic web dashboard (React + Recharts)
- [ ] Chess board integration (Chessground from Lichess — open source)
- [ ] Drill interface (show position → player makes move → feedback)

### Phase 8: Advanced Features
- [ ] AI opponent system (weakness-targeted Stockfish bots)
- [ ] Professional game corpus and recommendation
- [ ] Visualization trainer (no-board exercises)
- [ ] Maia Chess integration (human-like accuracy model)
- [ ] Neural network outcome predictor (PyTorch)
- [ ] Cloud compute deployment

### Phase 9: Product
- [ ] User account system (multi-user)
- [ ] Stripe billing integration
- [ ] Mobile app (React Native or Expo)
- [ ] Lichess game import (same format as Chess.com)
- [ ] Chess.com puzzle history integration
- [ ] Marketing site and SEO

---

## 24. Design Principles — Never Violate These

### 1. Thresholds Are Database Rows, Not Code Constants
Every number that could change based on data must be in player_thresholds.
Reading from the database at runtime is mandatory.
Hardcoded threshold constants in analyze_games.py are DEFAULTS ONLY,
used only as fallbacks when database lookup fails.

### 2. Continuous Scores Are the Source of Truth
mistake_score (FLOAT) is always computed and stored.
mistake_class (TEXT) is always derived from it.
The ML trains on floats. Labels are for human display only.
Never change the label without changing the underlying score.

### 3. CPL Is Always Capped Before Storage
CPL_CAP = 500. Apply before storing in database.
Mate scores (10000, 9999, etc.) must never appear in centipawn_loss column.
This is critical for accuracy calculations and averages.

### 4. WDL Perspective Must Be Explicit
Always use score.white().wdl() (NOT score.wdl() or score.relative.wdl()).
Then flip based on player_color.
Before move: player's wins = white wins if white, white losses if black.
After move: perspective shifts (opponent to move) — apply the reverse flip.
Wrong perspective → 100% accuracy for blunders → misleading output.

### 5. Labels Are CPL-Primary, Scores Are Context-Aware
310 CPL is ALWAYS a blunder. Phase does not change the label.
Phase (opening 0.6x, endgame 1.4x) changes the WEIGHT/SCORE.
The continuous score reflects context. The discrete label reflects magnitude.
Previous bug had phase affecting labels — this produced 310 CPL = 'inaccuracy'.

### 6. Multiple Labels Are Expected
One mistake can tag multiple concepts.
attribution_weight is per-label confidence, not a fraction of 100%.
The primary cause drives the study recommendation.
Secondary labels add context and refine the picture.

### 7. Nothing Breaks If Thresholds Change
Adding a new threshold, changing a default, or ML updating a value
must not require code changes.
Code reads thresholds at the start of each game analysis.
If player_id-specific threshold exists, use it. Otherwise use global default.

### 8. Every Feature Is Queryable
Every signal computed during analysis is stored in the database.
Never compute on the fly what could be pre-computed and stored.
This enables the prescription engine to be pure SQL queries + aggregations.

### 9. Already-Decided Positions Are Discounted
WDL accuracy in won/lost positions is unreliable (any move looks accurate).
Apply position_decisiveness blending to all accuracy models.
A blunder from a completely lost position should not score 100% accuracy.

### 10. Short Games Are Filtered
Games with fewer than MIN_GAME_MOVES (10) moves are skipped.
These are abandoned games, disconnects, or pre-arranged games.
They pollute accuracy statistics and opening analysis.

### 11. Pattern Recognition vs Calculation — Tactical Mistakes Have Two Causes

Almost every tactical failure can be labeled "3.3.6 Calculation depth failure"
but this is often the **wrong diagnosis**. Two fundamentally different causes:

**Cause A — Calculation Failure:** Player saw the pattern existed but couldn't
calculate deeply enough to confirm it worked. The motif was recognized; the
tree search failed. Fix: calculation training, deeper tree-search exercises.

**Cause B — Pattern Recognition Failure:** Player never saw the pattern at all.
The motif was invisible — they didn't know to look for it. Fix: pattern drilling
until the motif becomes pre-conscious.

The goal of tactical training is NOT to make players calculate faster. It is to
make patterns **pre-conscious** — recognized instantly without deliberate
calculation. A grandmaster doesn't calculate a fork — they SEE it.

**System implications:**

- 3.3.6 (Calculation depth) must NOT be the primary prescription when a
  specific pattern (fork, pin, back-rank, etc.) is identifiable. The motif IS
  the primary cause. Calculation training is secondary — it only helps after
  the player can see the pattern at all.

- `pattern_detector.py` enforces this: when any motif in `_SPECIFIC_TACTICAL`
  fires alongside 3.3.6, the 3.3.6 weight is capped at 0.40, ensuring it is
  never selected as primary cause when a concrete motif is present.

- 3.4.2 (Quiet move missed) remains secondary: quiet moves genuinely require
  calculation even after pattern recognition, so no demotion applies.

- Drill repetition builds **pattern libraries**, and pattern libraries
  **replace** calculation. This is the entire theoretical basis of tactical
  training at sub-GM levels.

### 12. Recency Weighting Is Not Optional — It Is Correctness

All weakness detection, gap scoring, and time-ratio calculations MUST apply
exponential recency decay. A weakness from 3 years ago at a different Elo
bracket is near-irrelevant to today's player. Treating it equally with last
week's game produces a false diagnosis.

**Decay formula:** `weight = 0.5 ^ (days_since_game / HALF_LIFE_DAYS)`

Where `HALF_LIFE_DAYS = 90` (weight halves every 90 days):
- Today:    1.000  |  90d: 0.500  |  180d: 0.250
- 1 year:   0.077  |  2yr: 0.006  |  3yr:  0.0004

**Staleness filter:** Any line/pattern not seen in `STALE_DAYS = 180` is marked
stale and excluded from active flagging regardless of historical score.

**What recency weighting changed in opening prep gaps:**
- Unweighted #1: C65 Ruy Lopez (4.23x ratio) — last played ~2018. Phantom gap.
- Weighted #1:  A45 Indian Game (3.82x ratio, 15d ago). Real, current gap.
- 27 of 37 previously flagged lines correctly reclassified as stale.

**System-wide application:** weakness_aggregator.py, opening_prep_gap.py,
session_detector.py, and any future detector must use the same formula.

### Next Build Priorities (after full analysis completes)

1. **API layer** — FastAPI, endpoints for weakness profile and drill serving
2. **Basic frontend** — React, weakness dashboard, drill board (Chessground)
3. **Opening drill module** — serve positions from prep gap lines specifically
4. **Player's own game positions** — seed drill_positions from pattern_detector
   output (own game positions are more memorable than Lichess puzzles)
5. **Opponent capitalization** — second-pass analysis to score how well the
   opponent punished each player mistake

---

## 25. Outstanding Questions and Open Items

### Algorithm Questions

**Q: Should we weight suboptimal (20-50 CPL) moves differently in different time controls?**
In classical chess, a 25 CPL move is always worth studying.
In bullet, a 25 CPL move might be optimal given the time constraint.
Current approach: suboptimal_cpl threshold is higher for bullet (25) vs classical (15).
But should we also weight by time_pressure at the point of the move?

**Q: What is the correct half-life for recency weighting?**
Currently 90 days (weight halves every 3 months).
This might be too aggressive — a game from 6 months ago at the same Elo
is still very relevant. Consider player-adjustable (fast learners vs slow improvers).

**Q: How do we handle games where the player was clearly sandbagging or not trying?**
Resignation on move 3, playing obvious blunders intentionally, etc.
These games would corrupt the weakness profile.
Potential detection: games where result_type = 'resigned' AND total_moves < 15.

**Q: Should we separate opening preparation failures from opening theory blunders?**
If you deviate from theory on move 8 because you forgot the line → preparation gap.
If you deviate from theory on move 8 because the opponent played an unusual move → different.
The novelty_move data helps here but we need more nuanced detection.

### 3.4.2 Quiet Move Recognition — Subtype Split (Roadmap)

3.4.2 fires at 10.78/100 weighted moves and is the #1 weakness by frequency.
However it conflates two fundamentally different failure types:

**Type A — Quiet first move of a tactical combination (44% of fires)**
- The best move is quiet but sets up a forced tactical sequence
- Player missed it because they didn't see the downstream tactic
- Prescription: train the underlying tactic (fork, pin, deflection, etc.)
- These resolve as the tactical pattern library improves
- Example: Rd1! (quiet rook move) that sets up a back-rank mate threat

**Type B — Genuinely quiet positional move (56% of fires)**
- The best move is quiet AND there is no downstream tactical pattern
- Player missed it due to lack of positional vision or candidate generation
- Prescription: positional calculation training, prophylaxis drills,
  candidate move generation exercises
- These are harder to resolve — represent the true 1600→1800 skill boundary
- Example: h3! (prophylactic pawn move) that prevents a future attack

**Implementation plan for Layer 2 of pattern_detector.py:**
When a specific tactical motif fires alongside 3.4.2 on the same move,
demote 3.4.2 to secondary — the tactical motif IS the primary cause.
This mirrors the existing 3.3.6 demotion in `_SPECIFIC_TACTICAL`.
Add 3.4.2 to the same demotion logic: when `_SPECIFIC_TACTICAL` motifs
are present, cap 3.4.2's weight at 0.40 as well.
This will re-classify ~44% of 3.4.2 primary fires as secondary, producing
a cleaner signal for the genuinely quiet positional failures.

Note: This change should only be applied AFTER the full analysis run
completes, then re-run pattern_detector.py on all games.

### Open Technical Questions

**Q: Should Lichess Explorer API calls be parallelized?**
Currently sequential (one call per move, blocking).
Could batch-fetch multiple positions in parallel.
Or just replace with Polyglot book — simpler and faster.

**Q: How do we handle transpositions in opening analysis?**
The same position can be reached via different move orders (transpositions).
The Lichess Explorer API handles this automatically (FEN-based lookup).
But our opening clustering by ECO code won't catch transpositions.
Need FEN-based similarity, not ECO-based.

**Q: When should we start training the neural network outcome predictor?**
Need enough data: 2000+ analyzed games minimum.
Current: ~70 games analyzed.
Estimated time to reach 2000: ~38 hours parallel analysis.
Plan: complete full analysis first, then train.

**Q: How do we measure whether a weakness is actually resolved?**
Current definition: "hasn't occurred in 30+ days."
Better definition: "has occurred multiple times since last study session
and player handled it correctly each time."
But this requires tracking concept-level accuracy in study sessions,
not just occurrence rate in games.

### Product Questions

**Q: What is the minimum viable product (MVP)?**
The smallest version that demonstrates the core value:
1. Import games (done)
2. Analyze games (in progress)
3. Show weakness profile (next major feature)
4. Prescribe one study activity (after weakness aggregation)
5. One drill module (tactical drill using player's own mistakes)
This MVP could attract early users and validate the core concept.

**Q: Should we support Lichess game import from the start?**
Yes — Lichess has 100M+ users, many prefer it.
Same PGN format, similar API structure.
Only difference: Lichess bulk database available for population models.
Add after Chess.com import is fully validated.

**Q: How do we handle players who play multiple accounts?**
Merge player profiles? Keep separate?
Current design: one row in players per (username, platform).
Multiple accounts = multiple player rows, no merging.
Future: allow linking accounts in a player_accounts table.

**Q: What's the right monetization model — subscription or lifetime?**
Lifetime deal at launch (e.g., $99) could fund early development.
Switch to subscription after initial funding.
Or freemium from day one.
Decision needed before building billing integration.

### Chess Knowledge Questions

**Q: How do we formally define "bad bishop" for automated detection?**
Current plan: bishop's pawns on same color as bishop for >60% of player's pawns.
But a bishop is "bad" relative to the opponent's bishop.
If both bishops are on same color pawns, neither is necessarily "bad."
Need more nuanced definition: bad bishop = blocked by own pawns AND
opponent has active bishop or knight outpost on the bishop's color complex.

**Q: What is the correct taxonomy for positional mistakes?**
Current plan: Silman's seven imbalances as the framework.
Should we also incorporate Nimzowitsch's "My System" concepts?
(Blockade, prophylaxis, the center, open files, weak squares, passed pawns)
These are complementary, not competing frameworks.
Both could be concept nodes — Silman for structural, Nimzowitsch for strategic.

**Q: How do we detect when a player's plan is inconsistent?**
Current approach: tag moves as "kingside attack", "queenside expansion", etc.
If 3-move window has all different directions → plan_inconsistency.
But this might flag legitimate plan changes (opponent forces rerouting).
Need to compare to engine's recommended plan direction.

---

## 26. Environment and Setup

### Hardware
- Windows 11 (Karl's machine)
- CPU: Modern (AVX2 support confirmed — Stockfish AVX2 binary works)
- RAM: Sufficient for PostgreSQL + Python + Stockfish

### Software Stack
```
Python:        3.14.3 (very new — some packages don't have compiled wheels)
PostgreSQL:    18.3 (very new)
Stockfish:     18.3 AVX2
VS Code:       1.118.1
```

### Python Packages Installed
```
psycopg[binary]==3.3.4    (PostgreSQL driver — NOT psycopg2)
python-chess==1.11.2       (via chess-1.11.2 wheel)
requests==2.33.1
python-dotenv==1.2.2
scikit-learn==1.8.0
pandas==3.0.2
numpy==2.4.4
scipy==1.17.1
```

**Not yet installed (needed for future phases):**
```
ruptures         (changepoint detection — needs C++ Build Tools)
torch/torchvision (neural network — needs separate installation)
fastapi          (API layer — when building frontend)
uvicorn          (ASGI server for FastAPI)
```

### Environment Variables (.env)
```
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=chess_engine
DB_USER=postgres
DB_PASSWORD=0088
STOCKFISH_PATH=C:\Users\karlb\chess-study-engine\stockfish\stockfish-windows-x86-64-avx2.exe
POLYGLOT_BOOK_PATH=C:\Users\karlb\chess-study-engine\books\gm2001.bin
SYZYGY_PATH=C:\Users\karlb\chess-study-engine\syzygy
```

### PostgreSQL
- Version: 18.3
- Database: chess_engine
- User: postgres
- Password: 0088
- Host: 127.0.0.1 (NOT localhost — use explicit IP to avoid auth issues)
- Port: 5432

**Connection command:**
```powershell
psql -U postgres -h 127.0.0.1 -d chess_engine
```

### Virtual Environment
```powershell
cd C:\Users\karlb\chess-study-engine
venv\Scripts\activate
```
Must activate before running any Python scripts.
PATH must include PostgreSQL bin directory:
```
C:\Program Files\PostgreSQL\18\bin
```
This is now permanent after restart.

### Project Structure
```
C:\Users\karlb\chess-study-engine\
├── .env                    (credentials — never commit to git)
├── db_setup.py             (database initialization and utilities)
├── import_chesscom.py      (Chess.com game importer)
├── seed_concepts.py        (chess knowledge ontology seeder)
├── schema_update.py        (first schema migration)
├── schema_update2.py       (second schema migration)
├── analyze_games.py        (Stockfish analysis engine)
├── CONTEXT.md              (this file)
├── venv/                   (Python virtual environment — gitignored)
├── stockfish/              (gitignored — download separately)
│   └── stockfish-windows-x86-64-avx2.exe
├── books/                  (gitignored — download separately)
│   └── gm2001.bin          (475KB Polyglot opening book)
└── syzygy/                 (gitignored — download separately, 938MB)
    └── *.rtbw, *.rtbz      (290 Syzygy tablebase files)
```

### Downloading Large Binary Files (not in git)
These files must be downloaded manually before first run:

**Stockfish (111MB):**
Download Windows AVX2 version from https://stockfishchess.org/download/
Place at: `stockfish\stockfish-windows-x86-64-avx2.exe`

**Polyglot book (475KB):**
Download gm2001.bin from https://github.com/michaeldv/donna_opening_books
Place at: `books\gm2001.bin`

**Syzygy tablebases (938MB, 290 files):**
```powershell
$base   = "http://tablebase.sesse.net/syzygy/3-4-5/"
$outDir = "C:\Users\karlb\chess-study-engine\syzygy"
New-Item -ItemType Directory -Force $outDir | Out-Null
$listing = Invoke-WebRequest -Uri $base -UseBasicParsing
$files   = $listing.Links | Where-Object { $_.href -match '\.(rtbw|rtbz)$' } | ForEach-Object { $_.href }
foreach ($f in $files) {
    $dest = Join-Path $outDir $f
    if (-not (Test-Path $dest)) {
        (New-Object System.Net.WebClient).DownloadFile("$base$f", $dest)
    }
}
```

### GitHub and Claude Code
Project uses GitHub for version control and Claude Code for AI-assisted development.
This CONTEXT.md file is the persistent knowledge base.
Claude Code should read CONTEXT.md at the start of every session.
Update CONTEXT.md whenever significant decisions are made or designs change.

### Running the Analysis
```powershell
# Standard sequential batch of 20 (for testing)
cd C:\Users\karlb\chess-study-engine
.\venv\Scripts\Activate.ps1
python analyze_games.py

# Full overnight parallel run (11 workers, all remaining games):
cd C:\Users\karlb\chess-study-engine
.\venv\Scripts\Activate.ps1
python -c "from analyze_games import run_analysis_queue; run_analysis_queue(batch_size=11000, parallel=True)"
# Expected: ~18 hours for 10,836 games at 9.9 games/min (11 workers)
# Leave running in a dedicated PowerShell window — do not close it
```

### Checking Queue Status
```sql
SELECT status, COUNT(*) FROM analysis_queue GROUP BY status;
SELECT game_id, started_at FROM analysis_queue WHERE status='in_progress';
```

### Resetting Stuck Jobs
```sql
UPDATE analysis_queue SET status='pending'
WHERE status='in_progress' AND started_at < NOW() - INTERVAL '15 minutes';
```

---

---

## 27. Chess King University Curriculum Reference

**Source:** Chess King University curriculum, extracted May 2026.
Three products analysed:
- **CT-ART 4.0** — Tactics 1200–2400 (10 levels)
- **Chess Middlegame I** — GM Alexander Kalinin — positional plans and pawn structures
- **Total Chess Endings** — GM Alexander Panchenko — 1600–2400 endgame theory

Data quality: exercise counts are exact. Elo brackets are approximate midpoints
of the level labels used by Chess King. Used to calibrate `concept_study_mapping`
`effectiveness_score` and `elo_bracket_min/max` values.

---

### Curriculum Elo Ladder (CT-ART 4.0 Levels)

| Level | Approx. Elo | Key Theme |
|-------|-------------|-----------|
| 1     | 0–200       | Piece movement, captures |
| 2–3   | 200–1000    | Basic tactics: forks, pins, mate in 1 |
| 4     | 1000–1200   | Undermining (140 ex), discovered check, defend against mate |
| 5–6   | 1200–1600   | Deflection (138 ex pawn shelter), decoy, interference, mate in 2 |
| 7     | 1600–1800   | Calculation depth, rook endings (priority), Lucena/Philidor |
| 8–9   | 1800–2200   | Rook endings advanced, bishop vs knight (253 ex), queen endings |
| 10    | 2200–2400   | Rook vs minor piece, combination of methods, complex endings |

---

### Exercise Counts by Category (CT-ART 4.0 + Panchenko)

**Tactical themes (CT-ART 4.0):**
```
Destruction of pawn shelter  138   (3.1.15) — weight as high as deflection
Deflection                   ~120  (3.1.10)
Decoy / lure                 ~115  (3.1.11)
Undermining (removal def.)   140   (3.1.7)  — Level 4, earlier than assumed
Zwischenzug                   48   (3.1.12) — boosted bracket to 1200+
Pawn promotion tactics         52   (3.4.4)  — new concept added
```

**Endgame exercises (Panchenko):**
```
Rook endings                 630   (#1 — Lucena/Philidor/Rook vs pawns)
Pawn endings                 300   (#2 — opposition, key squares, races)
Bishop endings               221   (#3 — same/opp color)
Knight endings               ~180  (#4)
Bishop vs knight             253   (more important than assumed — boosted)
Queen endings                ~120
```

**Opening-Middlegame plans (Kalinin):**
```
Sicilian structures          105   (4.5.x, 5.2.2) — most exercises
King's Indian plans           58   (4.5.10 mobile center)
Caro-Kann / Karlsbad          48   (4.5.8)
Dutch / Hedgehog              44   (4.5.9)
Ruy Lopez plans               38   (5.2.1)
```

---

### Key Findings and System Calibration Changes

**1. Rook endings are the #1 endgame priority (630 exercises)**
`effectiveness_score` boosted to 0.92 for Lucena, Philidor, and rook endings general.
`elo_bracket_min` corrected to 1600 (not 1400). Study prescription should prioritise
rook endings above all other endgame topics for players 1600–2400.

**2. Undermining (3.1.7) appears at Level 4 (1000–1200)**
Previously modeled as a 1400+ pattern. 140 exercises at 1000–1200 means this is
a core intermediate skill. `pattern_detector.py` attribution weight raised from 0.80 → 0.85.
`concept_study_mapping` effectiveness bumped to 0.87 at 1000–1200.

**3. Destruction of pawn shelter (3.1.15 — new concept)**
138 exercises, Level 5–6 (1200–2400). This is the tactical equivalent of 4.4.2
(pawn shield integrity). Added as new concept `3.1.15`. Weighted 0.88 =
same as deflection. NOT yet detected by pattern_detector.py (Layer 2 — requires
recognising forced pawn capture sequences near the king). TODO: add to Layer 2.

**4. Bishop vs knight (6.3.1) — 253 exercises, more important than assumed**
`effectiveness_score` boosted from 0.80 → 0.85 in the 2200–2400 bracket.

---

### New Concepts Added (May 2026)

The following concepts were added to the `concepts` table from this curriculum
analysis. They are NOT yet detected by `pattern_detector.py` (Layer 2/3):

| Code    | Name                        | Source      | Notes |
|---------|-----------------------------|-------------|-------|
| 3.1.15  | Destruction of pawn shelter | CT-ART 4.0  | 138 ex, add to Layer 2 |
| 3.4.4   | Pawn promotion tactics      | CT-ART 4.0  | 52 ex |
| 3.4.5   | Trapping and encirclement   | CT-ART 4.0  | board geometry |
| 3.4.6   | Stalemate trap              | CT-ART 4.0  | defensive resource |
| 3.4.7   | Opening of a file           | CT-ART 4.0  | tactical pawn sac |
| 3.4.8   | Pursuit                     | CT-ART 4.0  | chasing pieces |
| 3.4.9   | Combination of methods      | CT-ART 4.0  | multi-tactic |
| 4.5.8   | Karlsbad pawn structure     | Kalinin     | minority attack plan |
| 4.5.9   | Hedgehog formation          | Kalinin     | elastic defense |
| 4.5.10  | Mobile center               | Kalinin     | central pawn advance |

---

### concept_study_mapping Summary

77 rows seeded (May 2026) covering:
- Tactics: Level 2–10 (0–2400 Elo)
- Endgames: Level 3–10 (1000–2400 Elo), rook endings prioritised
- Positional: Level 5–8 (1200–2000 Elo)
- Openings: Level 2–10 (600–2400 Elo)
- Psychological: Time pressure + tilt (200–2400 Elo)

Source data extracted from Chess King University product interfaces, May 2026.
Not all concept codes have mappings yet — the 176-concept ontology is broader
than any single curriculum. Missing mappings default to no study prescription
until manually added or ML-derived from player data.

---

*Last updated: May 10, 2026*
*Session context: Full project conversation captured.*
*Next action: Full parallel analysis run completing. Run recalc_chesscom_accuracy.py + pattern_detector.py after.*
*Then: Build weakness_graph aggregator, study module prescriptions.*
