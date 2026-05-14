import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import { conceptName, conceptColor } from '../concepts.js'

const PSYCH_CODES = new Set(['7.3.1', '7.1.1', '7.1.2'])

function masteryColor(score) {
  if (score >= 0.8)  return 'var(--green)'
  if (score >= 0.55) return '#f0c040'
  if (score >= 0.3)  return 'var(--orange)'
  return 'var(--red)'
}

export default function Profile({ playerId, profileData, prescriptionData, onProfileLoad, onPrescriptionLoad }) {
  const [profile, setProfile] = useState(profileData)
  const [rx,      setRx]      = useState(prescriptionData)
  const [loading, setLoading] = useState(!profileData || !prescriptionData)
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
    ]).then(([pRes, rxRes]) => {
      setProfile(pRes.data)
      setRx(rxRes.data)
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

  // Chart data — top 8 weaknesses
  const chartData = trainable.slice(0, 8).map(r => ({
    name: conceptName(r.concept_code).split(' ').slice(0, 2).join(' '),
    pct:  r.pct_games_affected || 0,
    code: r.concept_code,
  }))

  return (
    <div style={{ maxWidth: 700, margin: '0 auto' }}>
      {/* Player header */}
      <div className="dash-header">
        <div className="dash-identity">
          <span className="dash-username">{profile.username}</span>
          {ratingMap['rapid'] && <span className="dash-rating">Rapid {ratingMap['rapid']}</span>}
          {ratingMap['blitz'] && <span className="dash-rating">Blitz {ratingMap['blitz']}</span>}
          <span className="dash-games">{(profile.games_analyzed || 0).toLocaleString()} games</span>
        </div>
        <button className="btn btn-secondary" style={{ fontSize: 12, padding: '6px 12px' }}
                onClick={() => nav('/games')}>
          View Games →
        </button>
      </div>

      {/* Weakness frequency chart */}
      {chartData.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-title">Weaknesses by Frequency</div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={chartData} layout="vertical"
                      margin={{ top: 0, right: 40, bottom: 0, left: 8 }}>
              <XAxis type="number" tick={{ fill: 'var(--text-2)', fontSize: 10 }}
                     tickFormatter={v => `${v}%`} />
              <YAxis type="category" dataKey="name" width={120}
                     tick={{ fill: 'var(--text-1)', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                formatter={v => [`${v.toFixed(1)}%`, 'Games affected']}
              />
              <Bar dataKey="pct" radius={[0, 3, 3, 0]}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={conceptColor(d.code)} opacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Weakness table */}
      {trainable.length > 0 && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-title">All Weaknesses</div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Concept</th>
                <th>In your games</th>
                <th>Avg loss</th>
                <th>Mastery</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {trainable.map(r => (
                <tr key={r.concept_code} style={{ cursor: 'pointer' }}
                    onClick={() => nav(`/weakness/${encodeURIComponent(r.concept_code)}`)}>
                  <td>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: conceptColor(r.concept_code), display: 'inline-block', flexShrink: 0 }} />
                      {conceptName(r.concept_code)}
                    </span>
                  </td>
                  <td style={{ fontWeight: 600 }}>{r.pct_games_affected?.toFixed(1)}%</td>
                  <td style={{ color: 'var(--text-2)' }}>
                    {r.avg_pawns_lost != null ? `${r.avg_pawns_lost} pawns` : '—'}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ height: 4, width: 60, background: 'var(--bg-3)', borderRadius: 2, overflow: 'hidden' }}>
                        <div style={{ height: '100%', width: `${(r.mastery_score || 0) * 100}%`, background: masteryColor(r.mastery_score || 0), borderRadius: 2 }} />
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--text-2)' }}>
                        {Math.round((r.mastery_score || 0) * 100)}%
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${r.status === 'improving' ? 'badge-green' : 'badge-red'}`}>
                      {r.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Session observations */}
      {(parseFloat(tiltPct) > 0 || parseFloat(fatiguePct) > 0) && (
        <div className="card">
          <div className="card-title">Session Observations</div>
          {parseFloat(tiltPct) > 0 && (
            <div className="context-box" style={{ marginBottom: 10 }}>
              <strong>Tilt detected</strong> in {tiltPct}% of sessions.
              Your accuracy drops noticeably after a loss. Consider resetting between games with a short break.
            </div>
          )}
          {parseFloat(fatiguePct) > 0 && (
            <div className="context-box">
              <strong>Fatigue detected</strong> in {fatiguePct}% of sessions.
              Your play deteriorates in longer sessions. Try limiting sessions to 60–90 minutes.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
