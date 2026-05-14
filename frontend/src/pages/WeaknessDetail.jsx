import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { conceptName, conceptColor, conceptShort } from '../concepts.js'

function masteryLabel(score) {
  if (!score || score === 0) return 'Not yet drilled — start here'
  if (score < 0.5) return 'Early progress — keep drilling'
  if (score < 0.8) return "Making progress — you're improving"
  return 'Nearly mastered — almost resolved'
}

function masteryColor(score) {
  if (score >= 0.8)  return 'var(--green)'
  if (score >= 0.55) return '#f0c040'
  if (score >= 0.3)  return 'var(--orange)'
  return 'var(--red)'
}

function resultBadge(result) {
  if (result === 'win')  return <span className="badge badge-green">Win</span>
  if (result === 'loss') return <span className="badge badge-red">Loss</span>
  return <span className="badge badge-gray">Draw</span>
}

export default function WeaknessDetail({ playerId }) {
  const { code }    = useParams()
  const nav         = useNavigate()
  const [data,      setData]      = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState(null)
  const [resolving, setResolving] = useState(false)

  useEffect(() => {
    setLoading(true)
    axios.get(`/api/players/${playerId}/weakness/${encodeURIComponent(code)}/detail`)
      .then(r => setData(r.data))
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [code, playerId])

  function handleResolve() {
    setResolving(true)
    axios.post(`/api/players/${playerId}/weakness/${encodeURIComponent(code)}/resolve`)
      .then(() => nav('/'))
      .catch(() => setResolving(false))
  }

  if (loading) return <div className="loading">Loading…</div>
  if (error)   return <div className="loading" style={{ color: 'var(--red)' }}>{error}</div>
  if (!data)   return null

  const color   = conceptColor(code)
  const mastery = data.mastery_score || 0
  const mColor  = masteryColor(mastery)

  // Monthly trend — show oldest first for chart readability
  const trendChartData = [...(data.monthly_trend || [])].reverse().map(pt => ({
    month: pt.month || '',
    count: pt.count || 0,
  }))

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <button className="btn btn-secondary" style={{ fontSize: 12, padding: '5px 12px', marginBottom: 12 }}
                  onClick={() => nav('/')}>
            ← Dashboard
          </button>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: color, margin: 0 }}>
            {conceptName(code)}
          </h1>
          <div style={{ fontSize: 13, color: 'var(--text-2)', marginTop: 4 }}>{conceptShort(code)}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => nav('/drill')}>Practice Now →</button>
          {data.status !== 'resolved' && (
            <button className="btn btn-secondary" onClick={handleResolve} disabled={resolving}
                    style={{ fontSize: 12 }}>
              {resolving ? 'Marking…' : 'Mark Resolved ✓'}
            </button>
          )}
        </div>
      </div>

      {/* 2×2 stat grid */}
      <div className="stat-grid-2x2 detail-section">
        <div className="stat-cell">
          <div className="stat-cell-label">Est. Elo Impact</div>
          <div className="stat-cell-value" style={{ color: 'var(--green)' }}>
            +{Math.round(data.estimated_elo_impact || 0)}
          </div>
          <div className="stat-cell-sub">estimated rating points</div>
        </div>
        <div className="stat-cell">
          <div className="stat-cell-label">Games Affected</div>
          <div className="stat-cell-value">{data.total_game_appearances}</div>
          <div className="stat-cell-sub">{data.pct_games_affected?.toFixed(1)}% of your games</div>
        </div>
        <div className="stat-cell">
          <div className="stat-cell-label">Avg Loss</div>
          <div className="stat-cell-value">
            {data.avg_pawns_lost != null ? data.avg_pawns_lost.toFixed(1) : '—'}
          </div>
          <div className="stat-cell-sub">pawns per occurrence</div>
        </div>
        <div className="stat-cell">
          <div className="stat-cell-label">Game Loss Rate</div>
          <div className="stat-cell-value"
               style={{ color: data.loss_rate != null && data.loss_rate > 0.4 ? 'var(--red)' : undefined }}>
            {data.loss_rate != null ? `${(data.loss_rate * 100).toFixed(0)}%` : '—'}
          </div>
          <div className="stat-cell-sub">you lose when this occurs</div>
        </div>
      </div>

      {/* Personal context */}
      {data.personal_context && (
        <div className="detail-section">
          <div className="context-box">{data.personal_context}</div>
        </div>
      )}

      {/* Monthly trend chart */}
      {trendChartData.length > 1 && (
        <div className="detail-section card">
          <div className="detail-section-title">How often this appeared in your games</div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={trendChartData} margin={{ top: 4, right: 12, bottom: 0, left: -10 }}>
              <XAxis dataKey="month" tick={{ fill: 'var(--text-2)', fontSize: 10 }} />
              <YAxis tick={{ fill: 'var(--text-2)', fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                formatter={v => [v, 'Games']}
              />
              <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                {trendChartData.map((_, i) => (
                  <Cell key={i} fill={color} opacity={0.7 + (i / trendChartData.length) * 0.3} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <div style={{ fontSize: 11, color: 'var(--text-2)', marginTop: 8 }}>
            Lower means fewer occurrences — as your skill improves, this pattern should fire less often.
          </div>
        </div>
      )}

      {/* Study instruction */}
      {(data.instruction || data.why_it_works) && (
        <div className="detail-section">
          <div className="detail-section-title">How to Improve</div>
          {data.instruction && (
            <div className="context-box" style={{ marginBottom: 10 }}>{data.instruction}</div>
          )}
          {data.why_it_works && (
            <div className="context-box"
                 style={{ background: 'rgba(92,143,232,0.05)', borderColor: 'rgba(92,143,232,0.25)' }}>
              <strong style={{ color: 'var(--accent)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
                Why it works
              </strong>
              <div style={{ marginTop: 6 }}>{data.why_it_works}</div>
            </div>
          )}
        </div>
      )}

      {/* Recent examples */}
      {data.recent_examples?.length > 0 && (
        <div className="detail-section">
          <div className="detail-section-title">Recent Examples From Your Games</div>
          {data.recent_examples.map((ex, i) => (
            <div key={i} className="context-box"
                 style={{ marginBottom: 8, fontSize: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
              {ex.result && resultBadge(ex.result)}
              <span style={{ color: 'var(--text-2)' }}>{ex.played_at?.slice(0, 10) || 'Game'}</span>
              {ex.opening_name && (
                <span style={{ color: 'var(--text-1)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {ex.opening_name}
                </span>
              )}
              {ex.centipawn_loss != null && (
                <span style={{ color: 'var(--red)', flexShrink: 0 }}>
                  −{(ex.centipawn_loss / 100).toFixed(2)} pawns
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Mastery assessment */}
      <div className="detail-section card">
        <div className="detail-section-title">Mastery Assessment</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-2)', marginBottom: 6 }}>
              <span>{masteryLabel(mastery)}</span>
              {mastery > 0 && <span style={{ color: mColor, fontWeight: 700 }}>{Math.round(mastery * 100)}%</span>}
            </div>
            <div style={{ height: 8, background: 'var(--bg-3)', borderRadius: 4 }}>
              <div style={{ height: '100%', width: `${mastery * 100}%`, background: mColor, borderRadius: 4, transition: 'width 0.5s' }} />
            </div>
          </div>
          <span className={`badge ${data.status === 'improving' ? 'badge-green' : data.status === 'active' ? 'badge-red' : 'badge-gray'}`}
                style={{ fontSize: 12, padding: '4px 10px' }}>
            {data.status}
          </span>
        </div>
        {data.status !== 'resolved' && (
          <button className="btn btn-secondary" style={{ fontSize: 12 }}
                  onClick={handleResolve} disabled={resolving}>
            {resolving ? 'Marking…' : 'Mark Resolved ✓'}
          </button>
        )}
      </div>
    </div>
  )
}
