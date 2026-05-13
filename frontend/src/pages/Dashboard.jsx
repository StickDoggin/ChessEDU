import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const PLAYER_ID = 1

export default function Dashboard() {
  const [profile, setProfile]   = useState(null)
  const [rx, setRx]             = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const nav = useNavigate()

  useEffect(() => {
    Promise.all([
      axios.get(`/api/players/${PLAYER_ID}/profile`),
      axios.get(`/api/players/${PLAYER_ID}/prescription`),
    ])
      .then(([pRes, rxRes]) => {
        setProfile(pRes.data)
        setRx(rxRes.data)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading">Loading dashboard...</div>
  if (error)   return <div className="loading" style={{ color: 'var(--red)' }}>Error: {error}</div>
  if (!profile) return null

  const chartData = rx.slice(0, 8).map(r => ({
    name: r.concept_code,
    elo: Math.round(r.estimated_elo_impact || 0),
    personal: r.personal_count || 0,
  }))

  // tilt_rate and fatigue_rate are already percentages (e.g. 14.68 = 14.68%)
  const tiltPct    = (profile.tilt_rate || 0).toFixed(1)
  const fatiguePct = (profile.fatigue_rate || 0).toFixed(1)

  // Extract ELO from ratings array
  const ratingMap = {}
  for (const r of (profile.ratings || [])) ratingMap[r.game_type] = r.current_elo

  return (
    <div>
      {/* Tilt / Fatigue alerts */}
      {(profile.tilt_rate || 0) > 10 && (
        <div className="alert alert-red mb-16">
          Tilt detected in {tiltPct}% of sessions — consider shorter sessions and breaks after losses.
        </div>
      )}
      {(profile.fatigue_rate || 0) > 15 && (
        <div className="alert alert-yellow mb-16">
          Fatigue detected in {fatiguePct}% of sessions — try limiting yourself to 4 games per sitting.
        </div>
      )}

      {/* Stat row */}
      <div className="stat-grid mb-24">
        <div className="stat-box">
          <div className="stat-label">Rapid ELO</div>
          <div className="stat-value">{ratingMap['rapid'] ?? '—'}</div>
          <div className="stat-sub">Chess.com</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Games Analyzed</div>
          <div className="stat-value">{(profile.games_analyzed || 0).toLocaleString()}</div>
          <div className="stat-sub">total</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Elo Potential</div>
          <div className="stat-value">+{Math.round(profile.estimated_elo_gain || 0)}</div>
          <div className="stat-sub">if all weaknesses fixed</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Study Hours</div>
          <div className="stat-value">{Math.round(profile.study_hours_needed || 0)}</div>
          <div className="stat-sub">estimated</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Tilt Rate</div>
          <div className="stat-value" style={{ color: parseFloat(tiltPct) > 10 ? 'var(--red)' : 'var(--green)' }}>
            {tiltPct}%
          </div>
          <div className="stat-sub">blitz / rapid</div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Fatigue Rate</div>
          <div className="stat-value" style={{ color: parseFloat(fatiguePct) > 15 ? 'var(--yellow)' : 'var(--green)' }}>
            {fatiguePct}%
          </div>
          <div className="stat-sub">of sessions</div>
        </div>
      </div>

      <div className="grid-2 mb-24">
        {/* Weakness chart */}
        <div className="card">
          <div className="card-title">Top Weaknesses — Elo Impact</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 0, right: 20 }}>
              <XAxis type="number" tick={{ fill: 'var(--text-2)', fontSize: 11 }} />
              <YAxis type="category" dataKey="name" width={60} tick={{ fill: 'var(--text-1)', fontSize: 11 }} />
              <Tooltip
                contentStyle={{ background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 6, fontSize: 12 }}
                labelStyle={{ color: 'var(--text-0)' }}
              />
              <Bar dataKey="elo" name="Elo impact" radius={[0, 4, 4, 0]}>
                {chartData.map((_, i) => (
                  <Cell key={i} fill={i === 0 ? 'var(--red)' : i < 3 ? 'var(--orange)' : 'var(--accent-dim)'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Prescription table */}
        <div className="card">
          <div className="card-title">Study Prescription</div>
          {rx.length === 0 ? (
            <div className="empty">No prescriptions. Run weakness_aggregator.py first.</div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Weakness</th>
                  <th>+Elo</th>
                  <th>Mastery</th>
                </tr>
              </thead>
              <tbody>
                {rx.slice(0, 10).map((r, i) => (
                  <tr key={i}>
                    <td><span className="badge badge-blue">{r.concept_code}</span></td>
                    <td style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {r.concept_name}
                    </td>
                    <td style={{ color: 'var(--green)', fontWeight: 600 }}>+{Math.round(r.estimated_elo_impact || 0)}</td>
                    <td>
                      <span className={`badge ${(r.mastery_score || 0) >= 0.8 ? 'badge-green' : (r.mastery_score || 0) >= 0.4 ? 'badge-yellow' : 'badge-gray'}`}>
                        {Math.round((r.mastery_score || 0) * 100)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div style={{ marginTop: 16 }}>
            <button className="btn btn-primary" onClick={() => nav('/drill')}>
              Start Drill Session
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
