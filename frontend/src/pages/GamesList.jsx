import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'

const PLAYER_ID = 1
const PAGE_SIZE = 20

function resultBadge(result) {
  if (!result) return <span className="badge badge-gray">?</span>
  if (result === 'win')  return <span className="badge badge-green">Win</span>
  if (result === 'loss') return <span className="badge badge-red">Loss</span>
  return <span className="badge badge-gray">Draw</span>
}

function accuracyColor(pct) {
  if (pct == null) return 'var(--text-2)'
  if (pct >= 85) return 'var(--green)'
  if (pct >= 70) return 'var(--yellow)'
  return 'var(--red)'
}

export default function GamesList() {
  const [games,   setGames]   = useState([])
  const [offset,  setOffset]  = useState(0)
  const [loading, setLoading] = useState(true)
  const [filter,  setFilter]  = useState('')
  const nav = useNavigate()

  function load(off, gt) {
    setLoading(true)
    const params = { limit: PAGE_SIZE, offset: off }
    if (gt) params.game_type = gt
    axios.get(`/api/players/${PLAYER_ID}/games`, { params })
      .then(r => setGames(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(0, filter) }, [])

  function applyFilter(gt) {
    setFilter(gt)
    setOffset(0)
    load(0, gt)
  }

  function prev() { const o = Math.max(0, offset - PAGE_SIZE); setOffset(o); load(o, filter) }
  function next() { const o = offset + PAGE_SIZE; setOffset(o); load(o, filter) }

  return (
    <div>
      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {['', 'rapid', 'blitz', 'bullet', 'classical'].map(t => (
          <button
            key={t}
            className={`btn ${filter === t ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '6px 14px' }}
            onClick={() => applyFilter(t)}
          >
            {t || 'All'}
          </button>
        ))}
      </div>

      <div className="card">
        <div className="card-title">
          Recent Games {offset > 0 && `(${offset + 1}–${offset + games.length})`}
        </div>

        {loading ? (
          <div className="loading">Loading games...</div>
        ) : games.length === 0 ? (
          <div className="empty">No games found.</div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Type</th>
                <th>Result</th>
                <th>ELO</th>
                <th>Opp</th>
                <th>Opening</th>
                <th>Accuracy</th>
                <th>Maia WP</th>
              </tr>
            </thead>
            <tbody>
              {games.map(g => (
                <tr key={g.game_id} style={{ cursor: 'pointer' }}>
                  <td style={{ color: 'var(--text-2)', fontSize: 12 }}>
                    {g.played_at ? g.played_at.slice(0, 10) : '—'}
                  </td>
                  <td><span className="badge badge-gray">{g.game_type || '?'}</span></td>
                  <td>{resultBadge(g.result)}</td>
                  <td>{g.player_elo ?? '—'}</td>
                  <td>{g.opponent_elo ?? '—'}</td>
                  <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
                    {g.opening_name || g.opening_eco || '—'}
                  </td>
                  <td style={{ color: accuracyColor(g.accuracy_pct), fontWeight: 600 }}>
                    {g.accuracy_pct != null ? `${g.accuracy_pct.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ color: g.avg_maia_win_prob != null ? 'var(--accent)' : 'var(--text-2)' }}>
                    {g.avg_maia_win_prob != null ? (g.avg_maia_win_prob * 100).toFixed(0) + '%' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        <div style={{ display: 'flex', gap: 10, marginTop: 16, justifyContent: 'flex-end' }}>
          <button className="btn btn-secondary" onClick={prev} disabled={offset === 0}>← Prev</button>
          <button className="btn btn-secondary" onClick={next} disabled={games.length < PAGE_SIZE}>Next →</button>
        </div>
      </div>
    </div>
  )
}
