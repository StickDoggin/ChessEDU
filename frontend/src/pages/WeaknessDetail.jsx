import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { conceptName, conceptColor, conceptShort } from '../concepts.js'

function StatPill({ label, value, valueColor }) {
  return (
    <div className="stat-pill">
      {label}: <strong style={valueColor ? { color: valueColor } : {}}>{value}</strong>
    </div>
  )
}

function masteryColor(score) {
  if (score >= 0.8) return 'var(--green)'
  if (score >= 0.55) return '#f0c040'
  if (score >= 0.3) return 'var(--orange)'
  return 'var(--red)'
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

  const trendChartData = (data.monthly_trend || []).map((pt, i) => ({
    month: pt.month || `M${i + 1}`,
    miss:  Math.round((pt.miss_rate || 0) * 100),
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
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn btn-primary" onClick={() => nav('/drill')}>Practice Now →</button>
          {data.status !== 'resolved' && (
            <button className="btn btn-secondary" onClick={handleResolve} disabled={resolving}
                    style={{ fontSize: 12 }}>
              {resolving ? 'Marking…' : 'Mark Resolved ✓'}
            </button>
          )}
        </div>
      </div>

      {/* Mastery status */}
      <div className="card detail-section">
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text-2)', marginBottom: 6 }}>
              <span>Mastery</span>
              <span style={{ color: mColor, fontWeight: 700 }}>{Math.round(mastery * 100)}%</span>
            </div>
            <div style={{ height: 8, background: 'var(--bg-3)', borderRadius: 4 }}>
              <div style={{ height: '100%', width: `${mastery * 100}%`, background: mColor, borderRadius: 4, transition: 'width 0.5s' }} />
            </div>
          </div>
          <span className={`badge ${data.status === 'improving' ? 'badge-green' : data.status === 'active' ? 'badge-red' : 'badge-gray'}`}
                style={{ fontSize: 12, padding: '4px 10px' }}>
            {data.status}
          </span>
          {data.trend_label && (
            <span style={{ fontSize: 13, color: data.trend_label === 'improving' ? 'var(--green)' : data.trend_label === 'worsening' ? 'var(--red)' : 'var(--text-2)' }}>
              {data.trend_label === 'improving' ? '↑ Improving' : data.trend_label === 'worsening' ? '↓ Worsening' : '→ Stable'}
            </span>
          )}
        </div>
      </div>

      {/* Stats row */}
      <div className="detail-section">
        <div className="detail-section-title">Your Statistics</div>
        <div className="stat-row">
          <StatPill label="Appearances" value={data.total_appearances ?? '—'} />
          <StatPill label="Miss rate" value={`${((data.miss_rate || 0) * 100).toFixed(0)}%`}
                    valueColor={(data.miss_rate || 0) > 0.3 ? 'var(--red)' : null} />
          <StatPill label="Find rate" value={`${((data.find_rate || 0) * 100).toFixed(0)}%`}
                    valueColor={(data.find_rate || 0) > 0.6 ? 'var(--green)' : null} />
          {data.loss_rate_when_missed != null && (
            <StatPill label="Loss rate when missed" value={`${((data.loss_rate_when_missed) * 100).toFixed(0)}%`}
                      valueColor={data.loss_rate_when_missed > 0.4 ? 'var(--red)' : null} />
          )}
          {data.avg_cpl_when_missed != null && (
            <StatPill label="Avg pawns lost" value={`${(data.avg_cpl_when_missed / 100).toFixed(2)}`} />
          )}
        </div>

        {data.personal_context && (
          <div className="context-box">{data.personal_context}</div>
        )}
      </div>

      {/* Trend chart */}
      {trendChartData.length > 1 && (
        <div className="detail-section card">
          <div className="detail-section-title">Miss Rate Over Time (lower = better)</div>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={trendChartData} margin={{ top: 4, right: 12, bottom: 0, left: -10 }}>
              <XAxis dataKey="month" tick={{ fill: 'var(--text-2)', fontSize: 10 }} />
              <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-2)', fontSize: 10 }} unit="%" />
              <Tooltip
                contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                formatter={v => [`${v}%`, 'Miss rate']}
              />
              <Line type="monotone" dataKey="miss" stroke={color} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
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
            <div className="context-box" style={{ background: 'rgba(92,143,232,0.05)', borderColor: 'rgba(92,143,232,0.25)' }}>
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
            <div key={i} className="context-box" style={{ marginBottom: 8, fontSize: 12 }}>
              <span style={{ color: 'var(--text-2)' }}>{ex.played_at?.slice(0, 10) || 'Game'}</span>
              {ex.opening_name && <span style={{ marginLeft: 8, color: 'var(--text-1)' }}> · {ex.opening_name}</span>}
              {ex.centipawn_loss != null && (
                <span style={{ marginLeft: 8, color: 'var(--red)' }}> −{(ex.centipawn_loss / 100).toFixed(2)} pawns</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
