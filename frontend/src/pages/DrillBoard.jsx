import { useEffect, useRef, useState, useCallback } from 'react'
import axios from 'axios'
import { Chess } from 'chess.js'
import { Chessground } from 'chessground'
import 'chessground/assets/chessground.base.css'
import 'chessground/assets/chessground.brown.css'
import 'chessground/assets/chessground.cburnett.css'
import { conceptName } from '../concepts.js'

const PLAYER_ID = 1
const MAX_ATTEMPTS = 3

const ENCOURAGEMENT = [
  'Not quite — think about checks, captures, and threats first.',
  'Good try! Look for the most forcing move available.',
  "Almost — what's the piece your opponent can't protect?",
]

const CONCEPT_HINTS = {
  '3.1.1':   ['Look for a piece that attacks two enemy pieces simultaneously', 'Knights can fork from unexpected squares — check all knight jumps'],
  '3.1.3':   ['A skewer attacks a valuable piece, which must move, losing the one behind it', 'Bishops and rooks deliver skewers on open diagonals and files'],
  '3.1.4':   ['Moving one piece reveals an attack from another behind it', 'Look for pieces lined up on the same diagonal, file, or rank'],
  '3.1.7':   ['An absolute pin means the pinned piece cannot legally move', 'Pin pieces against the king or queen to win material'],
  '3.1.8':   ['Find the defender doing two jobs at once — remove one and the other falls', 'Overloaded pieces often guard key squares and valuable pieces simultaneously'],
  '3.3.3':   ['Check every check, capture, and threat before considering quiet moves', 'Forcing moves force your opponent to respond — look for them first'],
  '3.3.6.a': ['Map out the exact sequence: what do I play, what do they play, what next?', 'Count forcing moves 2-3 deep — checks, recaptures, threats'],
  '3.3.6.b': ['Find the quiet move that makes the combination work', 'What move removes a defender or sets up a fork/pin?'],
  '3.3.6.c': ['Calculate methodically — one branch at a time', 'Use forcing moves to keep the tree narrow: checks and captures first'],
  '3.3.6.d': ['When under attack, look for stalemate tricks, perpetual check, or resource moves', 'Every position has saving moves — find the most forcing defensive idea'],
  '3.4.2.a': ['What is your opponent threatening? Play to prevent it now', 'Prophylaxis means seeing and stopping threats before they become real'],
  '3.4.2.b': ['Which of your pieces is doing the least? Find it a better square', 'A piece on its best square often decides the game'],
  '3.4.2.c': ['The quiet first move often goes unnoticed by the opponent', 'Look for a move that both improves a piece and threatens something'],
  '3.4.2.e': ['Can your king be attacked? Fix that first', 'King safety moves often involve castling, fianchettoing, or clearing escape squares'],
}

function difficultyLabel(pos) {
  if (pos.puzzle_rating) return `Rating ${pos.puzzle_rating}`
  const d = pos.difficulty || 0.5
  if (d >= 0.75) return 'Hard'
  if (d >= 0.45) return 'Medium'
  return 'Easy'
}

function buildDests(fen) {
  const chess = new Chess(fen)
  const dests = new Map()
  chess.moves({ verbose: true }).forEach(m => {
    if (!dests.has(m.from)) dests.set(m.from, [])
    dests.get(m.from).push(m.to)
  })
  return dests
}

function parseTurn(fen) {
  if (!fen) return 'white'
  return fen.split(' ')[1] === 'b' ? 'black' : 'white'
}


export default function DrillBoard() {
  const boardRef = useRef(null)
  const cgRef    = useRef(null)

  const startMsRef    = useRef(Date.now())
  const wrongRef      = useRef(0)
  const currentPosRef = useRef(null)

  const [session,       setSession]       = useState([])
  const [idx,           setIdx]           = useState(0)
  const [loading,       setLoading]       = useState(true)
  const [feedback,      setFeedback]      = useState(null)
  const [wrongAttempts, setWrongAttempts] = useState(0)
  const [hintIdx,       setHintIdx]       = useState(-1)
  const [done,          setDone]          = useState(false)
  const [solvedCount,   setSolvedCount]   = useState(0)
  const [timedMode,     setTimedMode]     = useState(false)
  const [timeLeft,      setTimeLeft]      = useState(null)
  const timerRef = useRef(null)

  // Coach bubble state
  const [weaknessCache,  setWeaknessCache]  = useState({})
  const [weaknessDetail, setWeaknessDetail] = useState(null)

  // AI explanation state
  const [explanation,    setExplanation]    = useState(null)
  const [explainLoading, setExplainLoading] = useState(false)

  const current = session[idx] || null

  useEffect(() => {
    axios.get(`/api/players/${PLAYER_ID}/drill-session?length_mins=15`)
      .then(r => {
        setSession(r.data.positions || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  // Fetch weakness detail for coach bubble, cached by concept code
  useEffect(() => {
    if (!current?.concept_code) return
    const code = current.concept_code
    if (weaknessCache[code]) {
      setWeaknessDetail(weaknessCache[code])
      return
    }
    axios.get(`/api/players/${PLAYER_ID}/weakness/${encodeURIComponent(code)}/detail`)
      .then(r => {
        setWeaknessCache(c => ({ ...c, [code]: r.data }))
        setWeaknessDetail(r.data)
      })
      .catch(() => {})
  }, [current?.concept_code])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleMove = useCallback((orig, dest) => {
    const pos = currentPosRef.current
    if (!pos) return
    const played  = orig + dest
    const correct = pos.correct_move
    const isRight = played === correct || played.startsWith(correct.split(' ')[0])
    const elapsed = Date.now() - startMsRef.current

    if (isRight) {
      setFeedback('correct')
      setSolvedCount(n => n + 1)
      if (cgRef.current) cgRef.current.set({ movable: { color: 'none' } })
      axios.post(`/api/players/${PLAYER_ID}/drill-attempt`, {
        drill_id: pos.drill_id, was_correct: true,
        time_spent_ms: elapsed, move_played: played,
        solution_depth: pos.solution_depth,
      }).catch(() => {})
    } else {
      wrongRef.current += 1
      const attempts = wrongRef.current
      setWrongAttempts(attempts)

      if (attempts >= MAX_ATTEMPTS) {
        setFeedback('show-answer')
        if (cgRef.current) {
          cgRef.current.set({
            movable: { color: 'none' },
            selected: correct.slice(0, 2),
          })
        }
        axios.post(`/api/players/${PLAYER_ID}/drill-attempt`, {
          drill_id: pos.drill_id, was_correct: false,
          time_spent_ms: elapsed, move_played: played,
          solution_depth: pos.solution_depth,
        }).catch(() => {})
      } else {
        setFeedback('try-again')
        setTimeout(() => {
          mountBoard(pos)
          setFeedback(null)
        }, 900)
      }
    }
  }, []) // stable — reads refs only

  const mountBoard = useCallback((pos) => {
    if (!boardRef.current || !pos) return
    const turn  = parseTurn(pos.fen)
    const dests = buildDests(pos.fen)

    if (cgRef.current) {
      cgRef.current.destroy()
      cgRef.current = null
    }

    cgRef.current = Chessground(boardRef.current, {
      fen: pos.fen, orientation: turn, turnColor: turn,
      movable: {
        color: turn, free: false, dests,
        events: { after: handleMove },
      },
      animation:  { enabled: true, duration: 180 },
      highlight:  { lastMove: true, check: true },
      premovable: { enabled: false },
    })
  }, [handleMove])

  useEffect(() => {
    if (!current) return
    currentPosRef.current = current
    wrongRef.current      = 0
    startMsRef.current    = Date.now()
    mountBoard(current)
    setFeedback(null)
    setWrongAttempts(0)
    setHintIdx(-1)
    setExplanation(null)
    setExplainLoading(false)

    if (timedMode) {
      const secs = Math.round((current.difficulty || 0.5) * 30 + 15)
      setTimeLeft(secs)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [current?.drill_id, timedMode])  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!timedMode || timeLeft === null || feedback) return
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) {
          clearInterval(timerRef.current)
          setFeedback('show-answer')
          if (cgRef.current) cgRef.current.set({ movable: { color: 'none' } })
          return 0
        }
        return t - 1
      })
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [timedMode, timeLeft, feedback])

  function fetchExplanation() {
    if (!current) return
    setExplainLoading(true)
    axios.get(`/api/players/${PLAYER_ID}/drill/${current.drill_id}/explain`)
      .then(r => { setExplanation(r.data); setExplainLoading(false) })
      .catch(() => setExplainLoading(false))
  }

  function nextPosition() {
    const next = idx + 1
    if (next >= session.length) setDone(true)
    else setIdx(next)
  }

  if (loading) return <div className="loading">Loading drill session…</div>

  // Empty session — no positions due for review
  if (!loading && session.length === 0) {
    return (
      <div className="session-complete">
        <div style={{ fontSize: 40 }}>📭</div>
        <h2 style={{ color: 'var(--text-1)' }}>No positions due</h2>
        <div style={{ color: 'var(--text-2)', marginBottom: 24 }}>
          All caught up! Come back later for your next review.
        </div>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>
          Check Again
        </button>
      </div>
    )
  }

  // Session complete
  if (done) {
    const pct = Math.round((solvedCount / session.length) * 100)
    return (
      <div className="session-complete">
        <div style={{ fontSize: 48 }}>🎉</div>
        <h2>Session Complete!</h2>
        <div style={{ fontSize: 32, fontWeight: 800, color: 'var(--green)', margin: '8px 0' }}>
          {solvedCount} / {session.length}
        </div>
        <div style={{ color: 'var(--text-2)', marginBottom: 20 }}>positions solved correctly</div>

        <div style={{ maxWidth: 280, margin: '0 auto 28px', background: 'var(--bg-2)', borderRadius: 4, height: 8 }}>
          <div style={{ height: '100%', width: `${pct}%`, background: 'var(--green)', borderRadius: 4 }} />
        </div>

        <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
          <button className="btn btn-secondary" onClick={() => window.location.reload()}>Study Again</button>
          <button className="btn btn-primary" onClick={() => window.location.href = '/'}>← Dashboard</button>
        </div>
      </div>
    )
  }

  const progress  = idx / session.length
  const turn      = current ? parseTurn(current.fen) : 'white'
  const isOwnGame = current?.source_move_id != null
  const resolved  = feedback === 'correct' || feedback === 'show-answer'

  const wd = weaknessDetail
  const coachPct  = wd?.pct_games_affected?.toFixed(1)
  const coachLoss = wd?.loss_rate != null ? Math.round(wd.loss_rate * 100) : null

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ color: 'var(--text-2)', fontSize: 12 }}>
          Position {idx + 1} / {session.length} &nbsp;·&nbsp; {solvedCount} solved
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-1)', cursor: 'pointer' }}>
          <input type="checkbox" checked={timedMode} onChange={e => setTimedMode(e.target.checked)} />
          Timed mode
        </label>
      </div>

      <div className="progress-bar-wrap mb-16">
        <div className="progress-bar" style={{ width: `${progress * 100}%` }} />
      </div>

      <div className="board-wrap">
        {/* Board */}
        <div className="board-col">
          <div className="cg-wrap" ref={boardRef} style={{ position: 'relative' }} />
          {timedMode && timeLeft !== null && !resolved && (
            <div style={{
              marginTop: 8, textAlign: 'center', fontSize: 14, fontWeight: 700,
              color: timeLeft <= 10 ? 'var(--red)' : 'var(--text-1)',
            }}>
              ⏱ {timeLeft}s
            </div>
          )}
        </div>

        {/* Coach panel */}
        <div className="drill-panel">
          {current && (
            <>
              <div className="drill-concept">{conceptName(current.concept_code)}</div>

              <div className="drill-prompt">
                {turn === 'white' ? 'White' : 'Black'} to move.
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12, fontSize: 12, color: 'var(--text-2)' }}>
                <span className={`badge ${isOwnGame ? 'badge-blue' : 'badge-gray'}`}>
                  {isOwnGame ? 'From your game' : 'Lichess puzzle'}
                </span>
                <span>{difficultyLabel(current)}</span>
              </div>

              {/* Coach bubble */}
              {(coachPct || coachLoss) && (
                <div className="coach-bubble">
                  <div className="coach-label">♟ Your Coach</div>
                  <p style={{ margin: '0 0 8px' }}>
                    {coachPct && `This pattern appears in ${coachPct}% of your games. `}
                    {coachLoss != null && `When it arises, you lose ${coachLoss}% of the time.`}
                  </p>
                  <p style={{ margin: 0, fontSize: 12, color: 'var(--text-2)' }}>
                    {isOwnGame
                      ? 'This position is from one of your own games — the best positions to study.'
                      : 'This puzzle targets the exact same weakness found in your game history.'}
                  </p>
                </div>
              )}

              {/* Feedback */}
              {feedback === 'correct' && (
                <div className="drill-feedback correct">✓ Correct!</div>
              )}
              {feedback === 'try-again' && (
                <div className="drill-feedback incorrect">
                  {ENCOURAGEMENT[(wrongAttempts - 1) % ENCOURAGEMENT.length]}
                  <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-2)' }}>
                    {MAX_ATTEMPTS - wrongAttempts} attempt{MAX_ATTEMPTS - wrongAttempts !== 1 ? 's' : ''} left
                  </div>
                </div>
              )}
              {feedback === 'show-answer' && (
                <div className="drill-feedback incorrect">
                  Best: <strong>{current.correct_move_san || current.correct_move}</strong>
                  <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-2)', fontWeight: 400 }}>
                    Look for the {conceptName(current.concept_code)} pattern here.
                  </div>
                </div>
              )}

              {/* AI Explanation (after show-answer) */}
              {feedback === 'show-answer' && (
                <div style={{ marginTop: 10 }}>
                  {!explanation && (
                    <button className="btn btn-secondary"
                            style={{ width: '100%', fontSize: 12, marginBottom: 8 }}
                            onClick={fetchExplanation}
                            disabled={explainLoading}>
                      {explainLoading ? 'Generating explanation…' : '💡 Explain this position'}
                    </button>
                  )}
                  {explanation && (
                    <div className="coach-bubble" style={{ marginTop: 8 }}>
                      <div className="coach-label">💡 Position Analysis</div>
                      {explanation.idea && (
                        <p style={{ margin: '0 0 8px' }}><strong>Idea:</strong> {explanation.idea}</p>
                      )}
                      {explanation.problem && (
                        <p style={{ margin: '0 0 8px' }}>⚠️ {explanation.problem}</p>
                      )}
                      {explanation.solution && (
                        <p style={{ margin: '0 0 8px' }}>✅ {explanation.solution}</p>
                      )}
                      {explanation.pay_attention?.length > 0 && (
                        <div>
                          <div style={{ fontSize: 11, color: 'var(--text-2)', marginBottom: 4 }}>📋 Pay attention to:</div>
                          <ul style={{ margin: 0, paddingLeft: 16 }}>
                            {explanation.pay_attention.map((pt, i) => (
                              <li key={i} style={{ fontSize: 12, marginBottom: 3 }}>{pt}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {resolved ? (
                <button className="btn btn-primary" style={{ width: '100%', marginTop: 10 }}
                        onClick={nextPosition}>
                  Next Position →
                </button>
              ) : (
                <div className="hint-ladder">
                  {hintIdx === -1 && (
                    <button className="hint-btn" onClick={() => setHintIdx(0)}>
                      Need a hint?
                    </button>
                  )}
                  {hintIdx >= 0 && (
                    <div className="hint-text">
                      {CONCEPT_HINTS[current.concept_code]?.[0]
                        || (current.concept_code?.startsWith('3.1')
                          ? 'Look for checks, captures, and threats before quiet moves.'
                          : 'Find the move that improves your position most.')}
                    </div>
                  )}
                  {hintIdx === 0 && (
                    <button className="hint-btn" style={{ marginTop: 6 }} onClick={() => setHintIdx(1)}>
                      More detail?
                    </button>
                  )}
                  {hintIdx >= 1 && (
                    <div className="hint-text" style={{ marginTop: 6 }}>
                      {CONCEPT_HINTS[current.concept_code]?.[1]
                        || <>Theme: <strong>{conceptName(current.concept_code)}</strong></>}
                    </div>
                  )}
                </div>
              )}

              {current.solution_depth > 1 && (
                <div style={{ marginTop: 16, paddingTop: 12, borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-2)' }}>
                  Depth: {current.solution_depth} moves
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
