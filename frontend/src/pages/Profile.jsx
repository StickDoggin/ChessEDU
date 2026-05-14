import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { conceptName, conceptColor } from '../concepts.js'

const PSYCH_CODES = new Set(['7.3.1', '7.1.1', '7.1.2'])
const PLAYER_ID = 1

function masteryColor(score) {
  if (score >= 0.8)  return 'var(--green)'
  if (score >= 0.55) return 'var(--yellow)'
  if (score >= 0.3)  return 'var(--orange)'
  return 'var(--red)'
}

// Map concept codes to skill categories
function computeSkillBreakdown(rx) {
  const cats = [
    { label: 'Tactics',       codes: c => c.startsWith('3.1') || c.startsWith('3.2') || c === '3.3.3', color: 'var(--red)' },
    { label: 'Calculation',   codes: c => c.startsWith('3.3.') && c !== '3.3.3',                       color: 'var(--orange)' },
    { label: 'Strategy',      codes: c => c.startsWith('3.4') || c.startsWith('4.'),                   color: 'var(--accent)' },
    { label: 'Openings',      codes: c => c.startsWith('6.'),                                           color: 'var(--green)' },
  ]

  return cats.map(cat => {
    const matching = rx.filter(r => cat.codes(r.concept_code))
    if (!matching.length) return { ...cat, pct: 0 }
    const avgMastery = matching.reduce((s, r) => s + (r.mastery_score || 0), 0) / matching.length
    return { ...cat, pct: Math.round(avgMastery * 100) }
  })
}

export default function Profile({ playerId, profileData, prescriptionData, onProfileLoad, onPrescriptionLoad }) {
  const [profile, setProfile] = useState(profileData)
  const [rx,      setRx]      = useState(prescriptionData)
  const [trend,   setTrend]   = useState([])
  const [loading, setLoading] = useState(!profileData || !prescriptionData)
  const nav = useNavigate()

  useEffect(() => {
    Promise.all([
      profileData
        ? Promise.resolve({ data: profileData })
        : axios.get(`/api/players/${PLAYER_ID}/profile`),
      prescriptionData
        ? Promise.resolve({ data: prescriptionData })
        : axios.get(`/api/players/${PLAYER_ID}/prescription`),
      axios.get(`/api/players/${PLAYER_ID}/performance-trend`).catch(() => ({ data: [] })),
    ]).then(([pRes, rxRes, tRes]) => {
      setProfile(pRes.data)
      setRx(rxRes.data)
      const raw = tRes.data || []
      setTrend(raw.map((pt, i) => ({
        label: `W${i + 1}`,
        win:   pt.win_rate,
        acc:   pt.accuracy,
        games: pt.games,
      })))
      onProfileLoad?.(pRes.data)
      onPrescriptionLoad?.(rxRes.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading">Loading profile…</div>
  if (!profile) return null

  const ratingMap = {}
  for (const r of (profile.ratings || [])) ratingMap[r.game_type] = r.current_elo

  const tiltPct    = ((profile.tilt_rate    || 0) * 100).toFixed(1)
  const fatiguePct = ((profile.fatigue_rate || 0) * 100).toFixed(1)

  const allRx     = rx || []
  const trainable = allRx
    .filter(r => !PSYCH_CODES.has(r.concept_code) && r.status !== 'resolved')
    .sort((a, b) => (b.pct_games_affected || 0) - (a.pct_games_affected || 0))

  const skills = computeSkillBreakdown(allRx)
  const avgSkill = skills.length
    ? Math.round(skills.reduce((s, c) => s + c.pct, 0) / skills.length)
    : 0

  return (
    <div>
      {/* ── PLAYER HEADER ─────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{ fontSize: 32 }}>♛</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-0)' }}>
              {profile.username}
            </div>
            <div style={{ display: 'flex', gap: 12, marginTop: 4, flexWrap: 'wrap' }}>
              {ratingMap['rapid'] && (
                <span style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>
                  Rapid {ratingMap['rapid']}
                </span>
              )}
              {ratingMap['blitz'] && (
                <span style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>
                  Blitz {ratingMap['blitz']}
                </span>
              )}
              <span style={{ fontSize: 12, color: 'var(--text-2)' }}>
                {(profile.games_analyzed || 0).toLocaleString()} games analyzed
              </span>
            </div>
          </div>
          <button className="btn btn-secondary" style={{ fontSize: 12, padding: '6px 12px' }}
                  onClick={() => nav('/games')}>
            Games →
          </button>
        </div>
      </div>

      {/* ── PERFORMANCE OVER TIME ──────────────────────────────── */}
      {trend.length >= 2 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="section-header">
            <span className="section-title">Performance Over Time</span>
            <span style={{ fontSize: 12, color: 'var(--text-2)' }}>Last 8 weeks</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={trend} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
              <XAxis dataKey="label" tick={{ fill: 'var(--text-2)', fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-2)', fontSize: 10 }}
                     tickFormatter={v => `${v}%`} />
              <Tooltip
                contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                formatter={(v, name) => [`${v?.toFixed(0)}%`, name === 'win' ? 'Win Rate' : 'Accuracy']}
              />
              <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                      formatter={v => v === 'win' ? 'Win Rate' : 'Accuracy'} />
              <Line type="monotone" dataKey="win" stroke="var(--yellow)"
                    strokeWidth={2} dot={false} name="win" />
              <Line type="monotone" dataKey="acc" stroke="var(--accent)"
                    strokeWidth={2} dot={false} name="acc" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* ── SKILL BREAKDOWN ───────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-header">
          <span className="section-title">Skill Breakdown</span>
          <span style={{ fontSize: 12, color: 'var(--text-2)' }}>Overall: {avgSkill}%</span>
        </div>
        {skills.map(s => (
          <div key={s.label} className="skill-bar-row">
            <span className="skill-bar-label">{s.label}</span>
            <div className="skill-bar-track">
              <div className="skill-bar-fill"
                   style={{ width: `${s.pct}%`, background: s.color }} />
            </div>
            <span className="skill-bar-pct">{s.pct}%</span>
          </div>
        ))}
        {avgSkill === 0 && (
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 8 }}>
            Complete drills to build up your mastery scores.
          </div>
        )}
      </div>

      {/* ── TOP WEAKNESSES ────────────────────────────────────── */}
      {trainable.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div className="section-header">
            <span className="section-title">Your Top Weaknesses</span>
            <button className="section-link" onClick={() => nav('/')}>Dashboard →</button>
          </div>
          {trainable.slice(0, 5).map((w, i) => {
            const color   = conceptColor(w.concept_code)
            const mastery = w.mastery_score || 0
            const pct     = w.pct_games_affected || 0
            const trend30 = w.trend_label
            return (
              <div key={w.concept_code} className="weakness-detail-card">
                <div className="weakness-detail-card-header">
                  <span className="weakness-detail-card-rank">#{i + 1}</span>
                  <span className="weakness-detail-card-name">{conceptName(w.concept_code)}</span>
                  <span className={`badge ${w.status === 'improving' ? 'badge-green' : 'badge-red'}`}>
                    {w.status}
                  </span>
                </div>

                <div className="weakness-detail-card-body">
                  This pattern appears in {pct.toFixed(0)}% of your games.
                  {w.avg_pawns_lost != null && ` Average loss: ${w.avg_pawns_lost} pawns.`}
                </div>

                <div className="weakness-detail-card-stats">
                  <div className="weakness-stat-item">
                    <span className="weakness-stat-label">In games</span>
                    <span className="weakness-stat-value">{pct.toFixed(0)}%</span>
                  </div>
                  <div className="weakness-stat-item">
                    <span className="weakness-stat-label">Avg loss</span>
                    <span className="weakness-stat-value">
                      {w.avg_pawns_lost != null ? `${w.avg_pawns_lost}p` : '—'}
                    </span>
                  </div>
                  <div className="weakness-stat-item">
                    <span className="weakness-stat-label">Trend</span>
                    <span className="weakness-stat-value" style={{
                      color: trend30 === 'improving' ? 'var(--green)' :
                             trend30 === 'worsening' ? 'var(--red)' : 'var(--text-2)'
                    }}>
                      {trend30 === 'improving' ? '↑' : trend30 === 'worsening' ? '↓' : '→'}
                    </span>
                  </div>
                </div>

                <div className="weakness-detail-card-footer">
                  <div className="weakness-mastery-bar">
                    <div className="weakness-mastery-fill"
                         style={{ width: `${mastery * 100}%`, background: masteryColor(mastery) }} />
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-2)', flexShrink: 0 }}>
                    {mastery > 0 ? `${Math.round(mastery * 100)}% mastery` : 'Not drilled'}
                  </span>
                </div>

                <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                  <button className="btn btn-secondary"
                          style={{ flex: 1, fontSize: 12 }}
                          onClick={() => nav(`/weakness/${encodeURIComponent(w.concept_code)}`)}>
                    Deep Dive ↗
                  </button>
                  <button className="btn btn-primary"
                          style={{ flex: 1, fontSize: 12 }}
                          onClick={() => nav('/study')}>
                    ▶ Practice
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* ── SESSION OBSERVATIONS ──────────────────────────────── */}
      {(parseFloat(tiltPct) > 0 || parseFloat(fatiguePct) > 0) && (
        <div className="card">
          <div className="section-title" style={{ marginBottom: 12 }}>Session Observations</div>
          {parseFloat(tiltPct) > 0 && (
            <div className="context-box" style={{ marginBottom: 10 }}>
              <strong>Tilt detected</strong> in {tiltPct}% of sessions.
              Accuracy drops noticeably after a loss. Consider resetting between games.
            </div>
          )}
          {parseFloat(fatiguePct) > 0 && (
            <div className="context-box">
              <strong>Fatigue detected</strong> in {fatiguePct}% of sessions.
              Play deteriorates in longer sessions. Try limiting sessions to 60–90 min.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
