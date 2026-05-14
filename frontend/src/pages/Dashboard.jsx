import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { conceptName, conceptColor } from '../concepts.js'

function masteryColor(score) {
  if (score >= 0.8) return 'var(--green)'
  if (score >= 0.55) return '#f0c040'
  if (score >= 0.3) return 'var(--orange)'
  return 'var(--red)'
}

function trendIcon(label) {
  if (label === 'improving') return <span style={{ color: 'var(--green)', fontSize: 13 }}>↑</span>
  if (label === 'worsening') return <span style={{ color: 'var(--red)',   fontSize: 13 }}>↓</span>
  return <span style={{ color: 'var(--text-2)', fontSize: 13 }}>→</span>
}

function WeaknessCard({ item, onDive, onDrill }) {
  const mastery  = item.mastery_score || 0
  const missRate = item.occurrence_rate || 0
  const color    = conceptColor(item.concept_code)
  const mColor   = masteryColor(mastery)

  return (
    <div className="weakness-card" style={{ borderLeft: `3px solid ${color}` }}>
      <div className="wc-header">
        <div className="wc-name">{conceptName(item.concept_code)}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {trendIcon(item.trend_label)}
          <span className={`badge ${item.status === 'improving' ? 'badge-green' : item.status === 'active' ? 'badge-red' : 'badge-gray'}`}>
            {item.status}
          </span>
        </div>
      </div>

      {/* Mastery bar */}
      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-2)', marginBottom: 4 }}>
          <span>Mastery</span>
          <span style={{ color: mColor, fontWeight: 700 }}>{Math.round(mastery * 100)}%</span>
        </div>
        <div style={{ height: 5, background: 'var(--bg-3)', borderRadius: 3 }}>
          <div style={{ height: '100%', width: `${mastery * 100}%`, background: mColor, borderRadius: 3, transition: 'width 0.4s' }} />
        </div>
      </div>

      <div className="wc-stats">
        <div className="wc-stat">
          <span className="wc-stat-label">Miss rate</span>
          <span className="wc-stat-val" style={{ color: missRate > 0.3 ? 'var(--red)' : 'var(--text-1)' }}>
            {(missRate * 100).toFixed(0)}%
          </span>
        </div>
        {item.occurrence_count != null && (
          <div className="wc-stat">
            <span className="wc-stat-label">Appearances</span>
            <span className="wc-stat-val">{item.occurrence_count}</span>
          </div>
        )}
      </div>

      <div className="wc-actions">
        <button className="btn btn-secondary wc-btn" onClick={() => onDive(item.concept_code)}>
          Deep Dive ↗
        </button>
        <button className="btn btn-primary wc-btn" onClick={() => onDrill(item.concept_code)}>
          Practice →
        </button>
      </div>
    </div>
  )
}

export default function Dashboard({ playerId, profileData, prescriptionData, onProfileLoad, onPrescriptionLoad }) {
  const [profile,  setProfile]  = useState(profileData)
  const [rx,       setRx]       = useState(prescriptionData)
  const [loading,  setLoading]  = useState(!profileData || !prescriptionData)
  const [error,    setError]    = useState(null)
  const [showResolved, setShowResolved] = useState(false)
  const nav = useNavigate()

  function fetchData() {
    setLoading(true)
    setError(null)
    Promise.all([
      axios.get(`/api/players/${playerId}/profile`),
      axios.get(`/api/players/${playerId}/prescription`),
    ])
      .then(([pRes, rxRes]) => {
        setProfile(pRes.data)
        setRx(rxRes.data)
        onProfileLoad?.(pRes.data)
        onPrescriptionLoad?.(rxRes.data)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (!profileData || !prescriptionData) fetchData()
  }, [])

  if (loading) return <div className="loading">Loading dashboard…</div>
  if (error)   return (
    <div className="loading" style={{ color: 'var(--red)' }}>
      Error: {error}
      <button className="btn btn-secondary" style={{ marginLeft: 12 }} onClick={fetchData}>Retry</button>
    </div>
  )
  if (!profile) return null

  const ratingMap = {}
  for (const r of (profile.ratings || [])) ratingMap[r.game_type] = r.current_elo
  const tiltPct    = (profile.tilt_rate    || 0).toFixed(1)
  const fatiguePct = (profile.fatigue_rate || 0).toFixed(1)

  // 60/40 priority sort: mastery × 0.6 + normalized_efficiency × 0.4
  const activeRx    = (rx || []).filter(r => r.status !== 'resolved')
  const resolvedRx  = (rx || []).filter(r => r.status === 'resolved')

  const maxEff = Math.max(...activeRx.map(r => r.study_efficiency || 0), 1)
  const sorted = [...activeRx].sort((a, b) => {
    const sa = (a.mastery_score || 0) * 0.6 + ((a.study_efficiency || 0) / maxEff) * 0.4
    const sb = (b.mastery_score || 0) * 0.6 + ((b.study_efficiency || 0) / maxEff) * 0.4
    return sb - sa
  })

  const topCode = sorted[0]?.concept_code

  return (
    <div>
      {/* Alerts */}
      {(profile.tilt_rate || 0) > 10 && (
        <div className="alert alert-red mb-16">
          Tilt detected — accuracy drops {tiltPct}% after losses. Consider breaks between games.
        </div>
      )}
      {(profile.fatigue_rate || 0) > 15 && (
        <div className="alert alert-yellow mb-16">
          Fatigue detected in {fatiguePct}% of sessions. Try limiting to 4 games per sitting.
        </div>
      )}

      {/* Slim header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          {ratingMap['rapid'] && (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Rapid</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{ratingMap['rapid']}</div>
            </div>
          )}
          {ratingMap['blitz'] && (
            <div>
              <div style={{ fontSize: 11, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Blitz</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>{ratingMap['blitz']}</div>
            </div>
          )}
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Games</div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{(profile.games_analyzed || 0).toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Tilt</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: parseFloat(tiltPct) > 10 ? 'var(--red)' : 'var(--green)' }}>{tiltPct}%</div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.4px' }}>Fatigue</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: parseFloat(fatiguePct) > 15 ? 'var(--yellow)' : 'var(--green)' }}>{fatiguePct}%</div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <button className="btn btn-secondary" style={{ fontSize: 12, padding: '6px 12px' }} onClick={fetchData} title="Refresh">
            ↺ Refresh
          </button>
          <button className="btn btn-primary" onClick={() => nav('/drill')}>
            Start Best Session →
          </button>
        </div>
      </div>

      {/* Weakness Cards */}
      <div style={{ marginBottom: 8, fontSize: 13, color: 'var(--text-2)' }}>
        {sorted.length} active weakness{sorted.length !== 1 ? 'es' : ''} — sorted by learning priority
      </div>

      {sorted.length === 0 ? (
        <div className="card empty">No active weaknesses. Run weakness_aggregator.py to analyze your games.</div>
      ) : (
        <div className="weakness-grid">
          {sorted.map(item => (
            <WeaknessCard
              key={item.concept_code}
              item={item}
              onDive={code  => nav(`/weakness/${encodeURIComponent(code)}`)}
              onDrill={code => nav('/drill')}
            />
          ))}
        </div>
      )}

      {/* Resolved section */}
      {resolvedRx.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <button
            className="btn btn-secondary"
            style={{ fontSize: 12, padding: '6px 14px' }}
            onClick={() => setShowResolved(v => !v)}
          >
            {showResolved ? '▲' : '▼'} {resolvedRx.length} resolved weakness{resolvedRx.length !== 1 ? 'es' : ''}
          </button>
          {showResolved && (
            <div className="weakness-grid" style={{ marginTop: 12, opacity: 0.6 }}>
              {resolvedRx.map(item => (
                <WeaknessCard
                  key={item.concept_code}
                  item={item}
                  onDive={code  => nav(`/weakness/${encodeURIComponent(code)}`)}
                  onDrill={code => nav('/drill')}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
