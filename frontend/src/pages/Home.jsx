import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { conceptName, conceptColor } from '../concepts.js'

const PSYCH_CODES = new Set(['7.3.1', '7.1.1', '7.1.2'])

function timeOfDay() {
  const h = new Date().getHours()
  if (h < 12) return 'morning'
  if (h < 17) return 'afternoon'
  return 'evening'
}

export default function Home({ playerId, profileData, prescriptionData, onProfileLoad, onPrescriptionLoad }) {
  const [profile,  setProfile]  = useState(profileData)
  const [rx,       setRx]       = useState(prescriptionData)
  const [drillDue, setDrillDue] = useState(null)
  const [loading,  setLoading]  = useState(!profileData || !prescriptionData)
  const nav = useNavigate()

  useEffect(() => {
    if (profileData && prescriptionData) {
      setProfile(profileData)
      setRx(prescriptionData)
      setLoading(false)
      return
    }
    setLoading(true)
    Promise.all([
      axios.get(`/api/players/${playerId}/profile`),
      axios.get(`/api/players/${playerId}/prescription`),
      axios.get(`/api/players/${playerId}/drill-session?length_mins=1`).catch(() => ({ data: { positions: [] } })),
    ]).then(([pRes, rxRes, drillRes]) => {
      setProfile(pRes.data)
      setRx(rxRes.data)
      setDrillDue((drillRes.data.positions || []).length)
      onProfileLoad?.(pRes.data)
      onPrescriptionLoad?.(rxRes.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading">Loading…</div>

  const allRx     = rx || []
  const trainable = allRx.filter(r => !PSYCH_CODES.has(r.concept_code) && r.status !== 'resolved')
  const topWeak   = [...trainable].sort((a, b) =>
    (b.pct_games_affected || 0) - (a.pct_games_affected || 0)
  )[0]
  const improving = trainable.find(r => r.trend_label === 'improving')

  const username = profile?.username || 'Player'
  const ratingMap = {}
  for (const r of (profile?.ratings || [])) ratingMap[r.game_type] = r.current_elo
  const elo = ratingMap['rapid'] || ratingMap['blitz'] || null

  // Build coach message
  let coachMsg = `Good ${timeOfDay()}, ${username}! `
  if (topWeak) {
    const pct = topWeak.pct_games_affected?.toFixed(0) || '?'
    coachMsg += `Your biggest challenge right now is ${conceptName(topWeak.concept_code)} — it's showing up in ${pct}% of your games. `
  }
  if (improving) {
    coachMsg += `The good news: your ${conceptName(improving.concept_code)} is improving. Keep at it!`
  } else if (!topWeak) {
    coachMsg += `You're all caught up! Keep studying to maintain your edge.`
  } else {
    coachMsg += `Let's work on it together.`
  }

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      {/* Coach message */}
      <div className="coach-message-box">
        <div className="coach-avatar-wrap">
          <div className="coach-avatar">♟</div>
        </div>
        <div>
          <div className="coach-name">Your Chess Coach</div>
          <div className="coach-message-text">{coachMsg}</div>
        </div>
      </div>

      {/* CTA */}
      <button className="btn btn-primary"
              style={{ width: '100%', fontSize: 16, padding: '14px', marginBottom: 24, marginTop: 8 }}
              onClick={() => nav('/study')}>
        Start Today's Session →
      </button>

      {/* Quick stats */}
      <div className="quick-stats-grid">
        <div className="quick-stat">
          <div className="quick-stat-value">{(profile?.games_analyzed || 0).toLocaleString()}</div>
          <div className="quick-stat-label">Games analyzed</div>
        </div>
        <div className="quick-stat">
          <div className="quick-stat-value">{trainable.length}</div>
          <div className="quick-stat-label">Active weaknesses</div>
        </div>
        {drillDue !== null && (
          <div className="quick-stat">
            <div className="quick-stat-value" style={{ color: drillDue > 0 ? 'var(--accent)' : 'var(--green)' }}>
              {drillDue > 0 ? drillDue : '✓'}
            </div>
            <div className="quick-stat-label">{drillDue > 0 ? 'Drills due' : 'All caught up'}</div>
          </div>
        )}
        {elo && (
          <div className="quick-stat">
            <div className="quick-stat-value">{elo}</div>
            <div className="quick-stat-label">{ratingMap['rapid'] ? 'Rapid Elo' : 'Blitz Elo'}</div>
          </div>
        )}
      </div>

      {/* Top priority */}
      {topWeak && (
        <div style={{ marginTop: 24 }}>
          <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-2)', marginBottom: 10 }}>
            Top Priority
          </div>
          <div className="priority-row" style={{ borderLeftColor: conceptColor(topWeak.concept_code), borderLeftWidth: 3, borderLeftStyle: 'solid' }}>
            <div className="priority-top">
              <span className="priority-dot" style={{ background: conceptColor(topWeak.concept_code) }} />
              <span className="priority-name">{conceptName(topWeak.concept_code)}</span>
              <span className="priority-pct" style={{ marginLeft: 'auto' }}>
                {topWeak.pct_games_affected?.toFixed(0)}% of games
              </span>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button className="btn btn-secondary" style={{ flex: 1, fontSize: 12 }}
                      onClick={() => nav(`/weakness/${encodeURIComponent(topWeak.concept_code)}`)}>
                Deep Dive ↗
              </button>
              <button className="btn btn-primary" style={{ flex: 1, fontSize: 12 }}
                      onClick={() => nav('/study')}>
                Practice →
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
