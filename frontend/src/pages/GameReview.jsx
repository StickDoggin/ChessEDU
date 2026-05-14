import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { Chess } from 'chess.js'
import { Chessground } from 'chessground'
import 'chessground/assets/chessground.base.css'
import 'chessground/assets/chessground.brown.css'
import 'chessground/assets/chessground.cburnett.css'

const PLAYER_ID = 1
const STARTING_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

function cplColor(cpl) {
  if (cpl == null) return 'var(--text-2)'
  if (cpl === 0)   return 'var(--green)'
  if (cpl <= 20)   return 'var(--text-1)'
  if (cpl <= 50)   return 'var(--yellow)'
  if (cpl <= 100)  return 'var(--orange)'
  return 'var(--red)'
}

function mistakeLabel(cls) {
  if (!cls || cls === 'ok') return null
  const map = { blunder: '??', mistake: '?', inaccuracy: '?!', best: '!', good: '!', brilliant: '!!' }
  return map[cls] || null
}

function evalToWinPct(cp) {
  if (cp == null) return 50
  const bounded = Math.max(-1000, Math.min(1000, cp))
  return Math.round(50 + 50 * (2 / (1 + Math.exp(-bounded / 400)) - 1))
}

function resultBadge(result) {
  if (result === 'win')  return <span className="badge badge-green">Win</span>
  if (result === 'loss') return <span className="badge badge-red">Loss</span>
  return <span className="badge badge-gray">Draw</span>
}

export default function GameReview({ playerId: _pid }) {
  const { gameId } = useParams()
  const nav = useNavigate()

  const boardRef = useRef(null)
  const cgRef    = useRef(null)

  const [game,    setGame]    = useState(null)
  const [moves,   setMoves]   = useState([])   // flat: white+black interleaved
  const [moveIdx, setMoveIdx] = useState(-1)   // -1 = starting position
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    Promise.all([
      axios.get(`/api/players/${PLAYER_ID}/games/${gameId}`),
      axios.get(`/api/players/${PLAYER_ID}/games/${gameId}/moves`),
    ]).then(([gRes, mRes]) => {
      setGame(gRes.data)
      // Sort by move_number then color (white before black)
      const sorted = [...(mRes.data || [])].sort((a, b) => {
        if (a.move_number !== b.move_number) return a.move_number - b.move_number
        return a.color === 'white' ? -1 : 1
      })
      setMoves(sorted)
      setLoading(false)
    }).catch(e => {
      setError(e.response?.data?.detail || e.message)
      setLoading(false)
    })
  }, [gameId])

  const mountBoard = useCallback((fen, lastUci) => {
    if (!boardRef.current) return
    if (cgRef.current) { cgRef.current.destroy(); cgRef.current = null }

    const turn = fen.split(' ')[1] === 'b' ? 'black' : 'white'
    const lastMove = lastUci ? [lastUci.slice(0, 2), lastUci.slice(2, 4)] : undefined

    cgRef.current = Chessground(boardRef.current, {
      fen, orientation: 'white', turnColor: turn,
      movable:    { color: 'none', free: false },
      animation:  { enabled: true, duration: 150 },
      highlight:  { lastMove: true, check: true },
      premovable: { enabled: false },
      lastMove,
    })
  }, [])

  useEffect(() => {
    if (loading || moves.length === 0) return
    const fen  = moveIdx === -1 ? STARTING_FEN : (moves[moveIdx]?.fen_after || STARTING_FEN)
    const uci  = moveIdx >= 0 ? moves[moveIdx]?.uci : undefined
    mountBoard(fen, uci)
  }, [moveIdx, loading, moves, mountBoard])

  // Keyboard navigation
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'ArrowLeft')  setMoveIdx(i => Math.max(-1, i - 1))
      if (e.key === 'ArrowRight') setMoveIdx(i => Math.min(moves.length - 1, i + 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [moves.length])

  if (loading) return <div className="loading">Loading game…</div>
  if (error)   return <div className="loading" style={{ color: 'var(--red)' }}>{error}</div>
  if (!game)   return null

  const currentMove = moveIdx >= 0 ? moves[moveIdx] : null
  const evalCp      = currentMove?.eval_after ?? currentMove?.eval_before ?? null
  const whitePct    = evalToWinPct(evalCp)

  // Build move list as pairs
  const pairs = []
  for (let i = 0; i < moves.length; i += 2) {
    pairs.push({ num: moves[i].move_number, white: moves[i], black: moves[i + 1] || null })
  }

  function MoveCell({ m, idx }) {
    if (!m) return <td />
    const lbl    = mistakeLabel(m.mistake_class)
    const active = moveIdx === idx
    return (
      <td
        onClick={() => setMoveIdx(idx)}
        style={{
          padding: '3px 8px', cursor: 'pointer', borderRadius: 4,
          background: active ? 'var(--accent-dim)' : 'transparent',
          color: active ? 'var(--text-0)' : cplColor(m.centipawn_loss),
          fontWeight: active ? 700 : 400,
          whiteSpace: 'nowrap',
        }}
      >
        {m.san}{lbl && <sup style={{ color: cplColor(m.centipawn_loss), fontSize: 9, marginLeft: 1 }}>{lbl}</sup>}
      </td>
    )
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <button className="btn btn-secondary" style={{ fontSize: 12, padding: '5px 12px' }}
                onClick={() => nav('/games')}>
          ← Games
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, color: 'var(--text-1)' }}>
            {game.opening_name || game.opening_eco || 'Unknown opening'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 2 }}>
            {game.played_at?.slice(0, 10)} · {game.game_type} · {game.player_elo} vs {game.opponent_elo}
          </div>
        </div>
        {resultBadge(game.result)}
      </div>

      <div className="board-wrap">
        {/* Eval bar + board */}
        <div className="board-col" style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
          {/* Eval bar */}
          <div className="eval-bar">
            <div className="eval-bar-white" style={{ height: `${whitePct}%` }} />
            <div className="eval-bar-black" style={{ height: `${100 - whitePct}%` }} />
          </div>
          <div className="cg-wrap" ref={boardRef} style={{ position: 'relative' }} />
        </div>

        {/* Right panel */}
        <div className="drill-panel" style={{ maxWidth: 340 }}>
          {/* Navigation */}
          <div className="review-nav">
            <button className="btn btn-secondary" style={{ flex: 1 }}
                    onClick={() => setMoveIdx(-1)} title="Start">⏮</button>
            <button className="btn btn-secondary" style={{ flex: 1 }}
                    onClick={() => setMoveIdx(i => Math.max(-1, i - 1))} title="Back">◀</button>
            <button className="btn btn-secondary" style={{ flex: 1 }}
                    onClick={() => setMoveIdx(i => Math.min(moves.length - 1, i + 1))} title="Forward">▶</button>
            <button className="btn btn-secondary" style={{ flex: 1 }}
                    onClick={() => setMoveIdx(moves.length - 1)} title="End">⏭</button>
          </div>

          {/* Coach commentary */}
          {currentMove && (currentMove.centipawn_loss > 0 || currentMove.mistake_class) && (
            <div className="coach-bubble" style={{ marginBottom: 12 }}>
              <div className="coach-label">♟ Coach</div>
              {currentMove.mistake_class && currentMove.mistake_class !== 'ok' && (
                <p style={{ margin: '0 0 6px', fontWeight: 600, color: cplColor(currentMove.centipawn_loss) }}>
                  {currentMove.mistake_class === 'blunder' ? '?? Blunder' :
                   currentMove.mistake_class === 'mistake' ? '? Mistake' :
                   currentMove.mistake_class === 'inaccuracy' ? '?! Inaccuracy' : currentMove.mistake_class}
                </p>
              )}
              {currentMove.centipawn_loss > 0 && (
                <p style={{ margin: '0 0 6px', fontSize: 12, color: 'var(--text-2)' }}>
                  Lost {(currentMove.centipawn_loss / 100).toFixed(2)} pawns
                  {currentMove.best_move_san && ` — best was ${currentMove.best_move_san}`}
                </p>
              )}
              {currentMove.phase && (
                <p style={{ margin: 0, fontSize: 11, color: 'var(--text-2)' }}>
                  {currentMove.phase.charAt(0).toUpperCase() + currentMove.phase.slice(1)}
                </p>
              )}
            </div>
          )}

          {/* Move list */}
          <div className="review-move-list">
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <tbody>
                {pairs.map(({ num, white, black }) => {
                  const wIdx = moves.indexOf(white)
                  const bIdx = black ? moves.indexOf(black) : -1
                  return (
                    <tr key={num}>
                      <td style={{ padding: '2px 6px', color: 'var(--text-2)', fontSize: 12, userSelect: 'none', width: 28 }}>
                        {num}.
                      </td>
                      <MoveCell m={white} idx={wIdx} />
                      <MoveCell m={black} idx={bIdx} />
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Accuracy */}
          {game.accuracy_pct != null && (
            <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-2)', borderTop: '1px solid var(--border)', paddingTop: 10 }}>
              Your accuracy: <strong style={{ color: 'var(--text-0)' }}>{game.accuracy_pct.toFixed(1)}%</strong>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
