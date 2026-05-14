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
  "Almost — what's your opponent's biggest weakness right now?",
]

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

function starsFor(difficulty) {
  const filled = Math.round((difficulty || 0.5) * 5)
  return '★'.repeat(filled) + '☆'.repeat(5 - filled)
}

export default function DrillBoard() {
  const boardRef = useRef(null)
  const cgRef    = useRef(null)

  // Use refs for values read only inside event handlers (avoids stale closures)
  const startMsRef     = useRef(Date.now())
  const wrongRef       = useRef(0)
  const currentPosRef  = useRef(null)

  const [session,      setSession]      = useState([])
  const [idx,          setIdx]          = useState(0)
  const [loading,      setLoading]      = useState(true)
  const [feedback,     setFeedback]     = useState(null)   // 'correct' | 'try-again' | 'show-answer' | null
  const [wrongAttempts,setWrongAttempts]= useState(0)
  const [hintIdx,      setHintIdx]      = useState(-1)
  const [done,         setDone]         = useState(false)
  const [solvedCount,  setSolvedCount]  = useState(0)
  const [timedMode,    setTimedMode]    = useState(false)
  const [timeLeft,     setTimeLeft]     = useState(null)
  const timerRef = useRef(null)

  const current = session[idx] || null

  useEffect(() => {
    axios.get(`/api/players/${PLAYER_ID}/drill-session?length_mins=15`)
      .then(r => {
        setSession(r.data.positions || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  // Stable move handler — reads refs instead of capturing state snapshots
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
  }, []) // stable — only reads refs

  // Mounts (or re-mounts) the board for a given position
  const mountBoard = useCallback((pos) => {
    if (!boardRef.current || !pos) return
    const turn  = parseTurn(pos.fen)
    const dests = buildDests(pos.fen)

    if (cgRef.current) {
      cgRef.current.destroy()
      cgRef.current = null
    }

    cgRef.current = Chessground(boardRef.current, {
      fen:         pos.fen,
      orientation: turn,
      turnColor:   turn,
      movable: {
        color: turn,
        free:  false,
        dests,
        events: { after: handleMove },
      },
      animation:  { enabled: true, duration: 180 },
      highlight:  { lastMove: true, check: true },
      premovable: { enabled: false },
    })
  }, [handleMove])

  // New position: reset all per-position state
  useEffect(() => {
    if (!current) return
    currentPosRef.current = current
    wrongRef.current      = 0
    startMsRef.current    = Date.now()
    mountBoard(current)
    setFeedback(null)
    setWrongAttempts(0)
    setHintIdx(-1)

    if (timedMode) {
      const secs = Math.round((current.difficulty || 0.5) * 30 + 15)
      setTimeLeft(secs)
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [current?.drill_id, timedMode]) // eslint-disable-line react-hooks/exhaustive-deps

  // Countdown timer
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

  function nextPosition() {
    const next = idx + 1
    if (next >= session.length) setDone(true)
    else setIdx(next)
  }

  if (loading) return <div className="loading">Loading drill session…</div>

  if (done || session.length === 0) {
    return (
      <div className="card" style={{ maxWidth: 480, margin: '40px auto', textAlign: 'center' }}>
        <div className="card-title">Session Complete</div>
        <div className="stat-value" style={{ fontSize: 52, color: 'var(--green)', margin: '20px 0' }}>
          {solvedCount} / {session.length}
        </div>
        <div style={{ color: 'var(--text-1)', marginBottom: 24 }}>positions solved correctly</div>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>
          New Session
        </button>
      </div>
    )
  }

  const progress    = idx / session.length
  const turn        = current ? parseTurn(current.fen) : 'white'
  const isOwnGame   = current?.source_move_id != null
  const sourceLabel = isOwnGame ? 'From your game' : 'Lichess puzzle'
  const resolved    = feedback === 'correct' || feedback === 'show-answer'

  return (
    <div>
      {/* Top bar */}
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
        {/* Board column */}
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

              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16, fontSize: 12, color: 'var(--text-2)' }}>
                <span className={`badge ${isOwnGame ? 'badge-blue' : 'badge-gray'}`}>{sourceLabel}</span>
                <span style={{ color: '#f0c040', letterSpacing: 1 }}>{starsFor(current.difficulty)}</span>
                {current.puzzle_rating && <span>· {current.puzzle_rating}</span>}
              </div>

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

              {resolved ? (
                <button className="btn btn-primary" style={{ width: '100%', marginTop: 10 }}
                        onClick={nextPosition}>
                  Next Position →
                </button>
              ) : (
                <div className="hint-ladder">
                  {hintIdx === -1 && (
                    <button className="hint-btn" onClick={() => setHintIdx(0)}>
                      Need a hint? <span style={{ color: 'var(--text-2)' }}>−10% XP</span>
                    </button>
                  )}
                  {hintIdx >= 0 && (
                    <div className="hint-text">
                      Look for a {current.concept_code?.startsWith('3.1') ? 'tactical' : 'strategic'} opportunity — check forcing moves first.
                    </div>
                  )}
                  {hintIdx === 0 && (
                    <button className="hint-btn" style={{ marginTop: 6 }} onClick={() => setHintIdx(1)}>
                      More detail? <span style={{ color: 'var(--text-2)' }}>−30% XP</span>
                    </button>
                  )}
                  {hintIdx >= 1 && (
                    <div className="hint-text" style={{ marginTop: 6 }}>
                      Theme: <strong>{conceptName(current.concept_code)}</strong>
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
