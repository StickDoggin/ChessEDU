import { useEffect, useRef, useState, useCallback } from 'react'
import axios from 'axios'
import { Chessground } from 'chessground'
import 'chessground/assets/chessground.base.css'
import 'chessground/assets/chessground.brown.css'
import 'chessground/assets/chessground.cburnett.css'

const PLAYER_ID = 1
const HINTS = [
  { label: 'Hint 1 — There is a tactical opportunity', cost: '−10% XP' },
  { label: 'Hint 2 — Look for a forcing move', cost: '−30% XP' },
  { label: 'Hint 3 — Check, capture, or threat', cost: '−60% XP' },
]

function parseFen(fen) {
  if (!fen) return { turn: 'white' }
  const parts = fen.split(' ')
  return { turn: parts[1] === 'b' ? 'black' : 'white' }
}

function uciToMove(uci) {
  if (!uci || uci.length < 4) return null
  return { from: uci.slice(0, 2), to: uci.slice(2, 4) }
}

export default function DrillBoard() {
  const boardRef  = useRef(null)
  const cgRef     = useRef(null)

  const [session,  setSession]  = useState([])
  const [idx,      setIdx]      = useState(0)
  const [loading,  setLoading]  = useState(true)
  const [feedback, setFeedback] = useState(null)  // 'correct' | 'incorrect' | null
  const [bestMove, setBestMove] = useState(null)
  const [hintIdx,  setHintIdx]  = useState(-1)    // which hints are shown
  const [done,     setDone]     = useState(false)
  const [solvedCount, setSolvedCount] = useState(0)
  const [startMs, setStartMs]  = useState(Date.now())

  const current = session[idx] || null

  // Load session
  useEffect(() => {
    axios.get(`/api/players/${PLAYER_ID}/drill-session?length_mins=15`)
      .then(r => {
        setSession(r.data.positions || [])
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [])

  // Mount / update chessground
  useEffect(() => {
    if (!boardRef.current || !current) return

    const { turn } = parseFen(current.fen)

    if (!cgRef.current) {
      cgRef.current = Chessground(boardRef.current, {
        fen: current.fen,
        orientation: turn,
        turnColor: turn,
        movable: {
          color: turn,
          free: false,
          events: { after: handleMove },
        },
        animation: { enabled: true, duration: 200 },
        highlight: { lastMove: true, check: true },
        premovable: { enabled: false },
      })
    } else {
      cgRef.current.set({
        fen: current.fen,
        orientation: turn,
        turnColor: turn,
        movable: { color: turn, free: false, events: { after: handleMove } },
        lastMove: undefined,
        selected: undefined,
      })
    }
    setFeedback(null)
    setBestMove(null)
    setHintIdx(-1)
    setStartMs(Date.now())
  }, [current?.drill_id])

  const handleMove = useCallback((orig, dest) => {
    if (!current) return
    const played  = orig + dest
    const correct = current.correct_move

    const isCorrect = played === correct || played.startsWith(correct.split(' ')[0])
    const elapsed   = Date.now() - startMs

    setFeedback(isCorrect ? 'correct' : 'incorrect')
    if (!isCorrect) {
      const bm = uciToMove(correct)
      if (bm && cgRef.current) {
        cgRef.current.set({ lastMove: [bm.from, bm.to] })
      }
      setBestMove(current.correct_move_san || correct)
    }

    axios.post(`/api/players/${PLAYER_ID}/drill-attempt`, {
      drill_id: current.drill_id,
      was_correct: isCorrect,
      time_spent_ms: elapsed,
      move_played: played,
      solution_depth: current.solution_depth,
    }).catch(() => {})

    if (isCorrect) setSolvedCount(n => n + 1)

    // Disable board after answer
    if (cgRef.current) {
      cgRef.current.set({ movable: { color: 'none' } })
    }
  }, [current, startMs])

  function nextPosition() {
    const next = idx + 1
    if (next >= session.length) {
      setDone(true)
    } else {
      setIdx(next)
    }
  }

  if (loading) return <div className="loading">Loading drill session...</div>

  if (done || session.length === 0) {
    return (
      <div className="card" style={{ maxWidth: 480, margin: '40px auto', textAlign: 'center' }}>
        <div className="card-title">Session Complete</div>
        <div className="stat-value" style={{ fontSize: 48, color: 'var(--green)', margin: '20px 0' }}>
          {solvedCount} / {session.length}
        </div>
        <div style={{ color: 'var(--text-1)', marginBottom: 24 }}>positions solved correctly</div>
        <button className="btn btn-primary" onClick={() => window.location.reload()}>
          New Session
        </button>
      </div>
    )
  }

  const progress = idx / session.length

  return (
    <div>
      {/* Progress bar */}
      <div className="progress-bar-wrap mb-16">
        <div className="progress-bar" style={{ width: `${progress * 100}%` }} />
      </div>

      <div style={{ marginBottom: 8, color: 'var(--text-2)', fontSize: 12 }}>
        Position {idx + 1} of {session.length} — {solvedCount} solved
      </div>

      <div className="board-wrap">
        {/* Chess board */}
        <div className="board-col">
          <div className="cg-wrap" ref={boardRef} />
          {current?.visualization_mode && (
            <div className="alert alert-blue" style={{ marginTop: 10, fontSize: 11 }}>
              Visualization mode — this is a deep tactical sequence (rated {current.puzzle_rating}+). Try to calculate the full line before moving.
            </div>
          )}
        </div>

        {/* Drill panel */}
        <div className="drill-panel">
          {current && (
            <>
              <div className="drill-concept">{current.concept_code} — {current.concept_name}</div>
              <div className="drill-prompt">
                {parseFen(current.fen).turn === 'white' ? 'White' : 'Black'} to move. Find the best move.
              </div>

              {feedback && (
                <div className={`drill-feedback ${feedback}`}>
                  {feedback === 'correct' ? '✓ Correct!' : `✗ Incorrect — best was ${bestMove || current.correct_move}`}
                </div>
              )}

              {feedback ? (
                <button className="btn btn-primary" style={{ width: '100%', marginTop: 8 }} onClick={nextPosition}>
                  Next Position →
                </button>
              ) : (
                <div className="hint-ladder">
                  {HINTS.map((h, i) => (
                    <div key={i}>
                      {hintIdx >= i ? (
                        <div className="hint-text">{h.label} <span style={{ color: 'var(--red)', fontSize: 11 }}>{h.cost}</span></div>
                      ) : (
                        i === hintIdx + 1 && (
                          <button className="hint-btn" onClick={() => setHintIdx(i)}>
                            {h.label} <span style={{ color: 'var(--text-2)' }}>{h.cost}</span>
                          </button>
                        )
                      )}
                    </div>
                  ))}
                  {hintIdx === -1 && (
                    <button className="hint-btn" onClick={() => setHintIdx(0)}>
                      Need a hint? (−10% XP)
                    </button>
                  )}
                </div>
              )}

              <div style={{ marginTop: 20, paddingTop: 12, borderTop: '1px solid var(--border)', fontSize: 11, color: 'var(--text-2)' }}>
                Difficulty: {((current.difficulty || 0.5) * 100).toFixed(0)}%
                {current.puzzle_rating && <> · Rating: {current.puzzle_rating}</>}
                {current.solution_depth > 1 && <> · Depth: {current.solution_depth}</>}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
