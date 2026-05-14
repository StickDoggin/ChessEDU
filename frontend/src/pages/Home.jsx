import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { conceptName, conceptColor } from '../concepts.js'

const PSYCH_CODES = new Set(['7.3.1', '7.1.1', '7.1.2'])
const PLAYER_ID = 1

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins < 2)   return 'just now'
  if (mins < 60)  return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'Yesterday'
  if (days < 7)   return `${days}d ago`
  return dateStr.slice(0, 10)
}

function accuracyColor(pct) {
  if (pct == null) return 'var(--text-2)'
  if (pct >= 85) return 'var(--green)'
  if (pct >= 70) return 'var(--yellow)'
  return 'var(--red)'
}

// SVG ring component
function Ring({ value, max, color, label, size = 72, stroke = 7 }) {
  const r     = (size - stroke) / 2
  const circ  = 2 * Math.PI * r
  const pct   = value != null ? Math.min(Math.max(value / (max || 100), 0), 1) : 0
  const dash  = pct * circ
  const displayVal = value != null
    ? (max === 100 ? `${Math.round(value)}%` : String(value))
    : '--'

  return (
    <div style={{ textAlign: 'center' }}>
      <svg width={size} height={size} style={{ display: 'block', margin: '0 auto' }}>
        <circle cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="var(--bg-3)" strokeWidth={stroke} />
        {value != null && (
          <circle cx={size / 2} cy={size / 2} r={r}
            fill="none" stroke={color} strokeWidth={stroke}
            strokeDasharray={`${dash} ${circ}`}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        )}
        <text x={size / 2} y={size / 2 + 5} textAnchor="middle"
          fill="var(--text-0)" fontSize="13" fontWeight="700">
          {displayVal}
        </text>
      </svg>
      <div style={{ fontSize: 10, color: 'var(--text-2)', textTransform: 'uppercase',
        letterSpacing: '0.3px', marginTop: 4 }}>
        {label}
      </div>
    </div>
  )
}

export default function Home({ playerId, profileData, prescriptionData, onProfileLoad, onPrescriptionLoad }) {
  const [profile,  setProfile]   = useState(profileData)
  const [rx,       setRx]        = useState(prescriptionData)
  const [games,    setGames]     = useState([])
  const [gaps,     setGaps]      = useState([])
  const [week,     setWeek]      = useState(null)
  const [loading,  setLoading]   = useState(!profileData || !prescriptionData)
  const nav = useNavigate()

  useEffect(() => {
    const fetches = []

    if (!profileData || !prescriptionData) {
      fetches.push(
        axios.get(`/api/players/${PLAYER_ID}/profile`),
        axios.get(`/api/players/${PLAYER_ID}/prescription`),
      )
    }

    Promise.all([
      profileData
        ? Promise.resolve({ data: profileData })
        : axios.get(`/api/players/${PLAYER_ID}/profile`),
      prescriptionData
        ? Promise.resolve({ data: prescriptionData })
        : axios.get(`/api/players/${PLAYER_ID}/prescription`),
      axios.get(`/api/players/${PLAYER_ID}/games?limit=3`).catch(() => ({ data: [] })),
      axios.get(`/api/players/${PLAYER_ID}/opening-gaps`).catch(() => ({ data: [] })),
      axios.get(`/api/players/${PLAYER_ID}/this-week`).catch(() => ({ data: null })),
    ]).then(([pRes, rxRes, gRes, gapRes, wRes]) => {
      setProfile(pRes.data)
      setRx(rxRes.data)
      setGames(gRes.data || [])
      setGaps(gapRes.data || [])
      setWeek(wRes.data)
      onProfileLoad?.(pRes.data)
      onPrescriptionLoad?.(rxRes.data)
    }).catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading">Loading…</div>

  const allRx     = rx || []
  const trainable = allRx.filter(r => !PSYCH_CODES.has(r.concept_code) && r.status !== 'resolved')
  const sorted    = [...trainable].sort((a, b) => (b.pct_games_affected || 0) - (a.pct_games_affected || 0))
  const topWeak   = sorted[0]
  const topGap    = gaps[0] || null

  const ratingMap = {}
  for (const r of (profile?.ratings || [])) ratingMap[r.game_type] = r.current_elo
  const elo = ratingMap['rapid'] || ratingMap['blitz'] || null

  // Coach message — priority: recent losses > opening gap > top weakness
  let coachMsg = ''
  if (topWeak) {
    const pct = topWeak.pct_games_affected?.toFixed(0) || '?'
    coachMsg = `${conceptName(topWeak.concept_code)} is showing up in ${pct}% of your games. I've prepared positions to help you fix it.`
  } else if (topGap) {
    const lossPct = topGap.gap_score ? Math.round(topGap.gap_score * 100) : null
    coachMsg = `You're losing${lossPct ? ` ${lossPct}%` : ''} of your ${topGap.opening_name || topGap.eco} games. Let's build confidence there.`
  } else {
    coachMsg = "You're all caught up! Keep studying to maintain your edge."
  }

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'
  const username = profile?.username || 'Player'

  return (
    <div>
      {/* ── HEADER ────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: 24 }}>♛</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-0)', lineHeight: 1.2 }}>
            {username}
            {elo && <span style={{ fontSize: 14, color: 'var(--accent)', fontWeight: 600, marginLeft: 10 }}>
              {ratingMap['rapid'] ? 'Rapid' : 'Blitz'} {elo}
            </span>}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 2 }}>
            {(profile?.games_analyzed || 0).toLocaleString()} games analyzed
          </div>
        </div>
        <button className="btn btn-secondary" style={{ padding: '6px 12px', fontSize: 12 }}
                onClick={() => nav('/profile')}>
          ⚙ Profile
        </button>
      </div>

      {/* ── COACH MESSAGE ─────────────────────────────────────── */}
      <div className="coach-message-box">
        <div className="coach-avatar-wrap">
          <div className="coach-avatar">♟</div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span className="coach-name">Coach</span>
            <span className="coach-time">{greeting}</span>
          </div>
          <div className="coach-message-text">{coachMsg}</div>
        </div>
      </div>

      {/* ── ACTION TILES ──────────────────────────────────────── */}
      <div className="action-grid">
        <button className="action-tile action-tile-primary"
                onClick={() => nav('/study')}>
          <span className="action-tile-icon">♟</span>
          <span className="action-tile-label">Practice</span>
          <span className="action-tile-sub">Today's session</span>
        </button>

        <button className="action-tile action-tile-secondary"
                onClick={() => nav('/study')}>
          <span className="action-tile-icon">🎯</span>
          <span className="action-tile-label">Daily Focus</span>
          <span className="action-tile-sub" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
            {topWeak ? conceptName(topWeak.concept_code) : 'No active weakness'}
          </span>
        </button>

        <button className="action-tile"
                onClick={() => nav('/learn')}>
          <span className="action-tile-icon">📖</span>
          <span className="action-tile-label">Study Opening</span>
          <span className="action-tile-sub" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '100%' }}>
            {topGap
              ? `${topGap.opening_name || topGap.eco} · ${topGap.gap_score ? Math.round(topGap.gap_score * 100) : '?'}% loss`
              : 'Browse library'}
          </span>
        </button>

        <button className="action-tile"
                onClick={() => nav('/profile')}>
          <span className="action-tile-icon">📊</span>
          <span className="action-tile-label">View Stats</span>
          <span className="action-tile-sub">
            {trainable.length} active weakness{trainable.length !== 1 ? 'es' : ''}
          </span>
        </button>
      </div>

      {/* ── THIS WEEK ─────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-header" style={{ marginBottom: 0 }}>
          <span className="section-title">This Week</span>
          {week?.games_played > 0 && (
            <span style={{ fontSize: 12, color: 'var(--text-2)' }}>
              {week.games_played} game{week.games_played !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="rings-row">
          <Ring
            value={week?.win_rate}
            max={100}
            color="var(--yellow)"
            label="Win Rate"
          />
          <Ring
            value={week?.avg_accuracy}
            max={100}
            color="var(--accent)"
            label="Accuracy"
          />
          <Ring
            value={week?.positions_drilled}
            max={Math.max(week?.positions_drilled || 0, 50)}
            color="var(--green)"
            label="Drilled"
          />
          <Ring
            value={week?.avg_maia_wp}
            max={100}
            color="var(--purple)"
            label="Maia WP"
          />
        </div>
      </div>

      {/* ── WEAKNESS ANALYSIS ─────────────────────────────────── */}
      {sorted.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="section-header">
            <span className="section-title">Weakness Analysis</span>
            <button className="section-link" onClick={() => nav('/profile')}>View all →</button>
          </div>
          {sorted.slice(0, 3).map(w => {
            const color     = conceptColor(w.concept_code)
            const trend30   = w.trend_label
            const pct       = w.pct_games_affected || 0
            return (
              <div key={w.concept_code} className="weakness-bar-row"
                   style={{ cursor: 'pointer' }}
                   onClick={() => nav(`/weakness/${encodeURIComponent(w.concept_code)}`)}>
                <div className="weakness-bar-accent" style={{ background: color }} />
                <div className="weakness-bar-info">
                  <div className="weakness-bar-name">{conceptName(w.concept_code)}</div>
                  <div className="weakness-bar-sub">
                    {w.occurrence_count?.toLocaleString() || '?'} relevant games
                  </div>
                </div>
                <span className={`trend-badge ${
                  trend30 === 'improving' ? 'trend-pos' :
                  trend30 === 'worsening' ? 'trend-neg' : 'trend-neu'
                }`}>
                  {trend30 === 'improving' ? '↑ Improving' :
                   trend30 === 'worsening' ? '↓ Worsening' :
                   `${pct.toFixed(0)}% of games`}
                </span>
              </div>
            )
          })}
        </div>
      )}

      {/* ── RECENT GAMES ──────────────────────────────────────── */}
      {games.length > 0 && (
        <div className="card">
          <div className="section-header">
            <span className="section-title">Recent Games</span>
            <button className="section-link" onClick={() => nav('/games')}>See all →</button>
          </div>
          {games.map(g => {
            const acc = g.accuracy_pct
            const accColor = accuracyColor(acc)
            const resultClass = g.result === 'win' ? 'result-win' :
                                g.result === 'loss' ? 'result-loss' : 'result-draw'
            const resultLetter = g.result === 'win' ? 'W' : g.result === 'loss' ? 'L' : 'D'
            return (
              <div key={g.game_id} className="game-row"
                   onClick={() => nav(`/games/${g.game_id}`)}>
                <div className={`game-result-circle ${resultClass}`}>{resultLetter}</div>
                <div className="game-row-info">
                  <div className="game-row-opponent">
                    Opponent ({g.opponent_elo ?? '?'})
                  </div>
                  <div className="game-row-meta">
                    {g.opening_name ? g.opening_name.slice(0, 35) : (g.opening_eco || '—')}
                    {acc != null && ` · ${acc.toFixed(0)}% accuracy`}
                  </div>
                </div>
                <div className="game-row-right">
                  <div className="game-row-acc" style={{ color: accColor }}>
                    {acc != null ? `${acc.toFixed(1)}%` : '—'}
                  </div>
                  <div className="game-row-time">{timeAgo(g.played_at)}</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
