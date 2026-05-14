import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { conceptName, conceptColor } from '../concepts.js'

const PSYCH_CODES = new Set(['7.3.1', '7.1.1', '7.1.2'])

function masteryColor(score) {
  if (score >= 0.8)  return 'var(--green)'
  if (score >= 0.55) return '#f0c040'
  if (score >= 0.3)  return 'var(--orange)'
  return 'var(--red)'
}

function trendArrow(label) {
  if (label === 'improving') return <span style={{ color: 'var(--green)' }}>↑</span>
  if (label === 'worsening') return <span style={{ color: 'var(--red)'   }}>↓</span>
  return <span style={{ color: 'var(--text-2)' }}>→</span>
}

function PriorityRow({ item, rank, onDive, onDrill }) {
  const color   = conceptColor(item.concept_code)
  const mastery = item.mastery_score || 0
  const mColor  = masteryColor(mastery)
  const eloNum  = Math.round(item.estimated_elo_impact || 0)
  const pawns   = item.avg_pawns_lost != null ? `${item.avg_pawns_lost} pawns` : null
  const pct     = item.pct_games_affected != null ? `${item.pct_games_affected}% of games` : null

  return (
    <div className="priority-row">
      <div className="priority-top">
        <span className="priority-rank">#{rank}</span>
        <span className="priority-dot" style={{ background: color }} />
        <span className="priority-name">{conceptName(item.concept_code)}</span>
        <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          {trendArrow(item.trend_label)}
          <span className="priority-elo">+{eloNum} Elo</span>
        </span>
      </div>

      {(pawns || pct) && (
        <div className="priority-stats">
          {[pawns, pct].filter(Boolean).join(' · ')}
        </div>
      )}

      <div className="priority-bottom">
        <div className="priority-mastery-wrap">
          <div className="priority-mastery-label">
            {mastery === 0 ? 'Not yet drilled' : `Mastery ${Math.round(mastery * 100)}%`}
          </div>
          {mastery > 0 && (
            <div className="priority-mastery-bar">
              <div className="priority-mastery-fill"
                   style={{ width: `${mastery * 100}%`, background: mColor }} />
            </div>
          )}
        </div>
        <div className="priority-actions">
          <button className="btn btn-secondary" style={{ fontSize: 11, padding: '5px 10px' }}
                  onClick={() => onDive(item.concept_code)}>
            Deep Dive ↗
          </button>
          <button className="btn btn-primary" style={{ fontSize: 11, padding: '5px 10px' }}
                  onClick={() => onDrill(item.concept_code)}>
            Study →
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Dashboard({ playerId, profileData, prescriptionData, onProfileLoad, onPrescriptionLoad }) {
  const [profile,  setProfile]   = useState(profileData)
  const [rx,       setRx]        = useState(prescriptionData)
  const [gaps,     setGaps]      = useState([])
  const [loading,  setLoading]   = useState(!profileData || !prescriptionData)
  const [error,    setError]     = useState(null)
  const [showAll,  setShowAll]   = useState(false)
  const nav = useNavigate()

  function fetchData() {
    setLoading(true)
    setError(null)
    Promise.all([
      axios.get(`/api/players/${playerId}/profile`),
      axios.get(`/api/players/${playerId}/prescription`),
      axios.get(`/api/players/${playerId}/opening-gaps`).catch(() => ({ data: [] })),
    ])
      .then(([pRes, rxRes, gapRes]) => {
        setProfile(pRes.data)
        setRx(rxRes.data)
        setGaps(gapRes.data || [])
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
  const tiltPct    = ((profile.tilt_rate    || 0) * 100).toFixed(1)
  const fatiguePct = ((profile.fatigue_rate || 0) * 100).toFixed(1)

  // Trainable weaknesses only (exclude 7.x.x psychological)
  const allRx     = rx || []
  const trainable = allRx.filter(r => !PSYCH_CODES.has(r.concept_code) && r.status !== 'resolved')
  const psych     = allRx.filter(r =>  PSYCH_CODES.has(r.concept_code))

  // Sort by estimated_elo_impact DESC for dashboard
  const priorityRx = [...trainable].sort((a, b) =>
    (b.estimated_elo_impact || 0) - (a.estimated_elo_impact || 0)
  )
  const displayed = showAll ? priorityRx : priorityRx.slice(0, 5)

  // Elo summary bar (trainable weaknesses only, capped at +300 for progress display)
  const totalEloGain   = trainable.reduce((s, r) => s + (r.estimated_elo_impact || 0), 0)
  const currentElo     = ratingMap['rapid'] || ratingMap['blitz'] || 1500
  const goalElo        = currentElo + Math.round(totalEloGain)
  const progressPct    = Math.min((totalEloGain / 300) * 100, 100)

  return (
    <div>
      {/* ── ZONE 1 — HEADER ─────────────────────────────────── */}
      <div className="dash-header">
        <div className="dash-identity">
          <span className="dash-username">{profile.username}</span>
          {ratingMap['rapid'] && (
            <span className="dash-rating">Rapid {ratingMap['rapid']}</span>
          )}
          {ratingMap['blitz'] && (
            <span className="dash-rating">Blitz {ratingMap['blitz']}</span>
          )}
          <span className="dash-games">{(profile.games_analyzed || 0).toLocaleString()} games</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" style={{ fontSize: 12, padding: '6px 12px' }}
                  onClick={fetchData} title="Refresh data">
            ↺ Refresh
          </button>
          <button className="btn btn-primary" onClick={() => nav('/drill')}>
            Start Today's Session →
          </button>
        </div>
      </div>

      {/* ── ZONE 2 — ELO IMPACT SUMMARY ─────────────────────── */}
      {totalEloGain > 0 && (
        <div className="elo-summary">
          <div className="elo-summary-label">Estimated Elo gain if all weaknesses fixed</div>
          <div className="elo-summary-value">+{Math.round(totalEloGain)}</div>
          <div className="elo-progress-bar">
            <div className="elo-progress-fill" style={{ width: `${progressPct}%` }} />
          </div>
          <div className="elo-progress-labels">
            <span>Current: {currentElo}</span>
            <span>Goal: {goalElo}</span>
          </div>
        </div>
      )}

      {/* ── ZONE 3 — PRIORITY LIST ───────────────────────────── */}
      <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-2)', marginBottom: 12 }}>
        Where your Elo is going
      </div>

      {priorityRx.length === 0 ? (
        <div className="card empty">No active weaknesses found. Run weakness_aggregator.py to analyze your games.</div>
      ) : (
        <>
          <div className="priority-list">
            {displayed.map((item, i) => (
              <PriorityRow
                key={item.concept_code}
                item={item}
                rank={i + 1}
                onDive={code => nav(`/weakness/${encodeURIComponent(code)}`)}
                onDrill={() => nav('/drill')}
              />
            ))}
          </div>

          {priorityRx.length > 5 && (
            <button
              className="btn btn-secondary"
              style={{ fontSize: 12, padding: '6px 14px' }}
              onClick={() => setShowAll(v => !v)}
            >
              {showAll ? '▲ Show less' : `▼ Show all ${priorityRx.length} weaknesses`}
            </button>
          )}
        </>
      )}

      {/* ── ZONE 4 — OPENING GAPS ───────────────────────────── */}
      {gaps.length > 0 && (
        <div className="opening-section">
          <div className="opening-section-label">📖 Prescribed Opening Study</div>
          {gaps.slice(0, 5).map((g, i) => {
            const lossPct = g.gap_score != null ? Math.round(g.gap_score * 100) : null
            const daysAgo = g.deviation_count
            return (
              <div key={i} className="opening-row">
                <span className="eco-badge">{g.eco}</span>
                <span className="opening-name">{g.opening_name || g.eco}</span>
                {lossPct != null && (
                  <span className="opening-loss">{lossPct}% loss rate</span>
                )}
                {daysAgo > 0 && (
                  <span className="opening-days">{daysAgo}d ago</span>
                )}
                <button className="btn btn-secondary"
                        style={{ fontSize: 11, padding: '4px 10px', flexShrink: 0 }}
                        onClick={() => nav(`/opening/${g.eco}`)}>
                  Study →
                </button>
              </div>
            )
          })}
        </div>
      )}

      {/* ── FOOTNOTE — PSYCHOLOGICAL OBSERVATIONS ───────────── */}
      {(parseFloat(tiltPct) > 0 || parseFloat(fatiguePct) > 0 || psych.length > 0) && (
        <div className="dash-footnote">
          Note:{' '}
          {parseFloat(tiltPct) > 0 && `Tilt detected in ${tiltPct}% of sessions. `}
          {parseFloat(fatiguePct) > 0 && `Fatigue detected in ${fatiguePct}% of sessions. `}
          Consider taking breaks between games.
        </div>
      )}
    </div>
  )
}
