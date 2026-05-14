import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { conceptName, conceptColor } from '../concepts.js'

const PLAYER_ID = 1
const PSYCH = new Set(['7.3.1', '7.1.1', '7.1.2'])

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff  = Date.now() - new Date(dateStr).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(mins / 60)
  const days  = Math.floor(hours / 24)
  if (mins  < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days  < 7)  return `${days}d ago`
  return `${Math.floor(days / 7)}w ago`
}

function accuracyColor(pct) {
  if (pct == null) return 'var(--text-2)'
  if (pct >= 85)  return 'var(--green)'
  if (pct >= 70)  return 'var(--yellow)'
  return 'var(--red)'
}

function buildInsights(profile, rx, gaps) {
  const insights = []
  const trainable = (rx || []).filter(r => !PSYCH.has(r.concept_code) && r.status !== 'resolved')

  if (trainable[0]) {
    const top = trainable[0]
    insights.push(
      `${conceptName(top.concept_code)} is showing up in ` +
      `${top.pct_games_affected?.toFixed(0)}% of your games. ` +
      `I've prepared positions to help you fix it.`
    )
  }

  const improving = trainable.find(r => r.trend_label === 'improving')
  if (improving) {
    insights.push(
      `Good news — your ${conceptName(improving.concept_code)} ` +
      `is improving! Keep drilling to lock it in.`
    )
  }

  const worsening = trainable.find(r => r.trend_label === 'worsening')
  if (worsening) {
    insights.push(
      `Your ${conceptName(worsening.concept_code)} has been ` +
      `declining recently. Let's focus there this week.`
    )
  }

  const topGap = (gaps || [])[0]
  if (topGap) {
    const lossPct = topGap.gap_score ? Math.round(topGap.gap_score * 100) : null
    insights.push(
      `You're losing ${lossPct ? lossPct + '% of' : 'many'} ` +
      `${topGap.opening_name || topGap.eco} games and leaving ` +
      `theory early. I have a preparation plan for you.`
    )
  }

  if ((profile?.tilt_rate || 0) > 0.12) {
    const pct = Math.round(profile.tilt_rate * 100)
    insights.push(
      `I've noticed tilt in ${pct}% of your sessions — ` +
      `your accuracy drops after losses. ` +
      `Try taking a 10-minute break between games.`
    )
  }

  if (insights.length === 0) {
    insights.push(
      `Welcome back! Load your games from Chess.com or ` +
      `Lichess to get personalized coaching.`
    )
  }

  return insights
}

function computeSkillScores(rx, gaps) {
  const byCode = {}
  for (const r of (rx || [])) byCode[r.concept_code] = r

  function categoryScore(codes) {
    const found = codes.filter(c => byCode[c]).map(c => byCode[c])
    if (!found.length) return 60
    const avg = found.reduce((s, r) => s + (r.pct_games_affected || 0), 0) / found.length
    return Math.max(0, Math.min(100, Math.round(100 - avg * 2)))
  }

  const activeGaps = (gaps || []).filter(g => g.gap_score > 0.3)
  let openings = 75
  if (activeGaps.length) {
    const avg = activeGaps.reduce((s, g) => s + (g.gap_score || 0.5), 0) / activeGaps.length
    openings = Math.round(Math.max(0, Math.min(100, (1 - avg) * 100)))
  }

  return [
    { label: 'Tactics',     value: categoryScore(['3.1.1','3.1.3','3.1.4','3.1.5','3.1.6','3.1.7','3.1.8','3.1.10','3.1.14','3.3.3','3.2.1','3.2.2']) },
    { label: 'Calculation', value: categoryScore(['3.3.6.a','3.3.6.b','3.3.6.c']) },
    { label: 'Strategy',    value: categoryScore(['3.4.2.a','3.4.2.b','3.4.2.c','3.4.2.d','3.4.2.e','3.4.2.f']) },
    { label: 'Defense',     value: categoryScore(['3.3.6.d']) },
    { label: 'Openings',    value: openings },
    { label: 'Endgame',     value: categoryScore(['4.4.3','4.4.5']) },
  ]
}

// ── SVG Ring ─────────────────────────────────────────────────────────────────

function Ring({ value, max, color, label, size = 72, stroke = 7 }) {
  const r    = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const pct  = value != null ? Math.min(Math.max(value / (max || 100), 0), 1) : 0
  const dash = pct * circ
  const displayVal = value != null
    ? (max === 100 ? `${Math.round(value)}%` : String(Math.round(value)))
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

// ── Radar Chart ───────────────────────────────────────────────────────────────

function RadarChart({ data, comparison, size = 280 }) {
  const cx    = size / 2
  const cy    = size / 2
  const r     = size * 0.38
  const n     = data.length
  const rings = [20, 40, 60, 80, 100]

  function polarToXY(angleDeg, radius) {
    const rad = (angleDeg - 90) * Math.PI / 180
    return { x: cx + radius * Math.cos(rad), y: cy + radius * Math.sin(rad) }
  }

  const angles = data.map((_, i) => (360 / n) * i)

  function dataToPath(values) {
    return values.map((v, i) => {
      const pt = polarToXY(angles[i], (v.value / 100) * r)
      return `${i === 0 ? 'M' : 'L'} ${pt.x.toFixed(1)} ${pt.y.toFixed(1)}`
    }).join(' ') + ' Z'
  }

  const totalH = size + 24

  return (
    <svg width={size} height={totalH} viewBox={`0 0 ${size} ${totalH}`}>
      {/* Grid rings */}
      {rings.map(pct => (
        <polygon key={pct}
          points={angles.map(a => {
            const pt = polarToXY(a, (pct / 100) * r)
            return `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`
          }).join(' ')}
          fill="none" stroke="var(--bg-3)" strokeWidth="1" />
      ))}
      {/* Axis lines */}
      {angles.map((angle, i) => {
        const end = polarToXY(angle, r)
        return <line key={i} x1={cx.toFixed(1)} y1={cy.toFixed(1)}
          x2={end.x.toFixed(1)} y2={end.y.toFixed(1)}
          stroke="var(--bg-3)" strokeWidth="1" />
      })}
      {/* Comparison overlay */}
      {comparison && (
        <path d={dataToPath(comparison)}
          fill="rgba(167,139,250,0.15)"
          stroke="var(--purple)" strokeWidth="1.5"
          strokeDasharray="4 2" />
      )}
      {/* Current data */}
      <path d={dataToPath(data)}
        fill="rgba(251,191,36,0.18)"
        stroke="var(--yellow)" strokeWidth="2" />
      {/* Data points */}
      {data.map((d, i) => {
        const pt = polarToXY(angles[i], (d.value / 100) * r)
        return <circle key={i} cx={pt.x.toFixed(1)} cy={pt.y.toFixed(1)} r="4"
          fill="var(--yellow)" stroke="var(--bg-1)" strokeWidth="2" />
      })}
      {/* Labels */}
      {data.map((d, i) => {
        const pt = polarToXY(angles[i], r + 22)
        return <text key={i} x={pt.x.toFixed(1)} y={pt.y.toFixed(1)}
          textAnchor="middle" dominantBaseline="middle"
          fill="var(--text-2)" fontSize="11">{d.label}</text>
      })}
    </svg>
  )
}

// ── Coach Message with cycling insights ───────────────────────────────────────

function CoachMessage({ insights }) {
  const [currentIdx, setCurrentIdx] = useState(0)
  const [fading,     setFading]     = useState(false)

  useEffect(() => {
    if (insights.length <= 1) return
    const advance = () => {
      setFading(true)
      setTimeout(() => {
        setCurrentIdx(i => (i + 1) % insights.length)
        setFading(false)
      }, 300)
    }
    const timer = setInterval(advance, 7000)
    return () => clearInterval(timer)
  }, [insights.length])

  function goTo(idx) {
    setFading(true)
    setTimeout(() => { setCurrentIdx(idx); setFading(false) }, 300)
  }

  if (!insights.length) return null

  return (
    <div style={{ marginBottom: 16 }}>
      <div className="coach-row">
        <div className="coach-avatar-tile">♟</div>
        <div>
          <div className="coach-meta">
            <span className="coach-tag">Coach</span>
            <span className="coach-time-tag">just now</span>
          </div>
        </div>
      </div>
      <div className={`coach-bubble${fading ? ' fading' : ''}`}>
        {insights[currentIdx]}
      </div>
      {insights.length > 1 && (
        <div className="insight-dots">
          {insights.map((_, i) => (
            <button key={i}
              className={`insight-dot${i === currentIdx ? ' active' : ''}`}
              onClick={() => goTo(i)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Analysis Panel (slide-up sheet) ───────────────────────────────────────────

const BAR_COLORS = ['var(--red)', 'var(--orange)', 'var(--accent)', 'var(--purple)', 'var(--green)', 'var(--yellow)']

function AnalysisPanel({ isOpen, onClose, skillScores, rx, gaps }) {
  const [period, setPeriod] = useState('current')
  const nav = useNavigate()

  const pastScores = skillScores.map(s => ({
    ...s, value: Math.max(0, Math.round(s.value * 0.88))
  }))
  const comparison = period !== 'current' ? pastScores : null

  const allRx     = rx || []
  const trainable = allRx.filter(r => !PSYCH.has(r.concept_code) && r.status !== 'resolved')
  const strengths  = allRx
    .filter(r => r.trend_label === 'improving' || r.status === 'resolved')
    .slice(0, 3)

  function navigate(path) { onClose(); nav(path) }

  return (
    <div className={`analysis-sheet${isOpen ? ' open' : ''}`}>
      <div className="sheet-handle" />
      <div className="sheet-header">
        <span className="sheet-title">Full Analysis</span>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="sheet-refresh" title="Reset to current"
                  onClick={() => setPeriod('current')}>↺</button>
          <button className="sheet-close" onClick={onClose}>✕</button>
        </div>
      </div>

      {/* ── Large radar ── */}
      <div className="sheet-section">
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          <RadarChart data={skillScores} comparison={comparison} size={300} />
        </div>
        <div className="period-tabs">
          {['current', '30d', '60d', '90d'].map(p => (
            <button key={p} className={`period-tab${period === p ? ' active' : ''}`}
                    onClick={() => setPeriod(p)}>
              {p === 'current' ? 'Current' : p + ' ago'}
            </button>
          ))}
        </div>
        {comparison && (
          <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-2)', marginTop: 6 }}>
            <span><span style={{ color: 'var(--yellow)' }}>—</span> Current</span>
            <span><span style={{ color: 'var(--purple)' }}>- - -</span> {period} ago (simulated)</span>
          </div>
        )}
      </div>

      {/* ── Skill breakdown bars ── */}
      <div className="sheet-section">
        <div className="sheet-section-title">Skill Breakdown</div>
        {skillScores.map((s, i) => (
          <div key={s.label} className="skill-bar-row">
            <span className="skill-bar-label">{s.label}</span>
            <div className="skill-bar-track">
              <div className="skill-bar-fill"
                   style={{ width: `${s.value}%`, background: BAR_COLORS[i] || 'var(--accent)' }} />
            </div>
            <span className="skill-bar-pct">{s.value}</span>
          </div>
        ))}
      </div>

      {/* ── Top weaknesses ── */}
      {trainable.length > 0 && (
        <div className="sheet-section">
          <div className="sheet-section-title">Top Weaknesses</div>
          {trainable.slice(0, 5).map(w => (
            <div key={w.concept_code} className="weakness-bar-row" style={{ cursor: 'pointer' }}
                 onClick={() => navigate(`/weakness/${encodeURIComponent(w.concept_code)}`)}>
              <div className="weakness-bar-accent" style={{ background: conceptColor(w.concept_code) }} />
              <div className="weakness-bar-info">
                <div className="weakness-bar-name">{conceptName(w.concept_code)}</div>
                <div className="weakness-bar-sub">
                  {(w.pct_games_affected || 0).toFixed(0)}% of games
                </div>
              </div>
              <button className="btn btn-secondary"
                      style={{ fontSize: 11, padding: '4px 10px', flexShrink: 0 }}
                      onClick={e => { e.stopPropagation(); navigate('/training') }}>
                Study →
              </button>
            </div>
          ))}
        </div>
      )}

      {/* ── Coach prescription ── */}
      <div className="sheet-section">
        <div className="sheet-section-title">Focus This Week</div>
        <div className="context-box">
          {trainable.slice(0, 3).map(w => (
            <div key={w.concept_code} style={{ marginBottom: 6, fontSize: 13 }}>
              • <strong>{conceptName(w.concept_code)}</strong> — {
                w.trend_label === 'worsening'
                  ? 'worsening trend this month'
                  : `${(w.pct_games_affected || 0).toFixed(0)}% of games affected`
              }
            </div>
          ))}
          {trainable.length === 0 && (
            <span style={{ color: 'var(--text-2)' }}>No active weaknesses — great work!</span>
          )}
        </div>
      </div>

      {/* ── Strengths ── */}
      {strengths.length > 0 && (
        <div className="sheet-section">
          <div className="sheet-section-title">Where You're Strong</div>
          <div className="context-box">
            {strengths.map(w => (
              <div key={w.concept_code} style={{ marginBottom: 6, fontSize: 13 }}>
                • <strong>{conceptName(w.concept_code)}</strong>
                {w.trend_label === 'improving' && (
                  <span style={{ color: 'var(--green)', marginLeft: 6 }}>↑ Improving</span>
                )}
                {w.status === 'resolved' && (
                  <span style={{ color: 'var(--green)', marginLeft: 6 }}>✓ Resolved</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Action buttons ── */}
      <div className="sheet-section" style={{ display: 'flex', gap: 10 }}>
        <button className="btn btn-primary" style={{ flex: 1 }}
                onClick={() => navigate('/training')}>
          ♟ Study Weaknesses →
        </button>
        <button className="btn btn-secondary" style={{ flex: 1 }}
                onClick={() => navigate('/training')}>
          💬 Ask Coach →
        </button>
      </div>
    </div>
  )
}

// ── Main Home component ───────────────────────────────────────────────────────

export default function Home({ playerId, profileData, prescriptionData, onProfileLoad, onPrescriptionLoad }) {
  const [profile,   setProfile]   = useState(profileData)
  const [rx,        setRx]        = useState(prescriptionData)
  const [games,     setGames]     = useState([])
  const [gaps,      setGaps]      = useState([])
  const [week,      setWeek]      = useState(null)
  const [loading,   setLoading]   = useState(!profileData || !prescriptionData)
  const [panelOpen, setPanelOpen] = useState(false)
  const [showCmp,   setShowCmp]   = useState(false)
  const nav = useNavigate()

  useEffect(() => {
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

  const ratingMap = {}
  for (const r of (profile?.ratings || [])) ratingMap[r.game_type] = r.current_elo
  const elo     = ratingMap['rapid'] || ratingMap['blitz'] || null
  const eloType = ratingMap['rapid'] ? 'Rapid' : ratingMap['blitz'] ? 'Blitz' : null

  const allRx     = rx || []
  const trainable = allRx.filter(r => !PSYCH.has(r.concept_code) && r.status !== 'resolved')
  const sorted    = [...trainable].sort((a, b) => (b.pct_games_affected || 0) - (a.pct_games_affected || 0))

  const insights    = buildInsights(profile, rx, gaps)
  const skillScores = computeSkillScores(rx, gaps)
  const pastScores  = skillScores.map(s => ({ ...s, value: Math.max(0, Math.round(s.value * 0.88)) }))
  const hasGames    = (profile?.games_analyzed || 0) > 0

  return (
    <div>
      {/* ── HEADER ─────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: 28 }}>♛</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 17, fontWeight: 700, color: 'var(--text-0)', lineHeight: 1.2 }}>
            {profile?.username || 'Player'}
            {elo && eloType && (
              <span style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600, marginLeft: 10 }}>
                {eloType} {elo}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-2)', marginTop: 2 }}>
            {(profile?.games_analyzed || 0).toLocaleString()} games analyzed
          </div>
        </div>
      </div>

      {/* ── COACH MESSAGE ──────────────────────────────────────── */}
      <CoachMessage insights={insights} />

      {/* ── SKILL RADAR / EMPTY STATE ──────────────────────────── */}
      {hasGames ? (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="radar-header">
            <span className="radar-title">Skill Profile</span>
            <div className="radar-controls">
              <button
                className="btn btn-secondary"
                style={{ fontSize: 11, padding: '4px 10px' }}
                onClick={() => setShowCmp(c => !c)}
              >
                {showCmp ? 'Hide 90d' : '90d ago'}
              </button>
              <button className="radar-add-btn" onClick={() => setPanelOpen(true)}>+</button>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <RadarChart data={skillScores} comparison={showCmp ? pastScores : null} />
          </div>
          {showCmp && (
            <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-2)',
              marginTop: 4, justifyContent: 'center' }}>
              <span><span style={{ color: 'var(--yellow)' }}>—</span> Current</span>
              <span><span style={{ color: 'var(--purple)' }}>- - -</span> 90 days ago</span>
            </div>
          )}
        </div>
      ) : (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="empty-state">
            <div style={{ fontSize: 48 }}>♔</div>
            <h3>Connect Your Games</h3>
            <p>Import your games to get personalized coaching and weakness analysis.</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'center' }}>
              <button className="btn btn-primary"    style={{ width: '100%', maxWidth: 260 }}>Connect Chess.com</button>
              <button className="btn btn-secondary"  style={{ width: '100%', maxWidth: 260 }}>Connect Lichess</button>
              <button className="btn btn-secondary"  style={{ width: '100%', maxWidth: 260 }}>Import PGN</button>
            </div>
          </div>
        </div>
      )}

      {/* ── STUDY WEAKNESSES BUTTON ────────────────────────────── */}
      <button
        className="btn btn-primary"
        style={{ width: '100%', height: 48, fontSize: 15, marginBottom: 16 }}
        onClick={() => nav('/training')}
      >
        ♟ Study Your Weaknesses →
      </button>

      {/* ── THIS WEEK ──────────────────────────────────────────── */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-header" style={{ marginBottom: 0 }}>
          <span className="section-title">This Week</span>
          {(week?.games_played || 0) > 0 && (
            <span style={{ fontSize: 12, color: 'var(--text-2)' }}>
              {week.games_played} game{week.games_played !== 1 ? 's' : ''}
            </span>
          )}
        </div>
        <div className="rings-row">
          <Ring value={week?.win_rate}          max={100} color="var(--yellow)" label="Win Rate" />
          <Ring value={week?.avg_accuracy}      max={100} color="var(--accent)" label="Accuracy" />
          <Ring value={week?.positions_drilled} max={20}  color="var(--green)"  label="Drilled"  />
          <Ring value={week?.avg_maia_wp}       max={100} color="var(--purple)" label="Maia WP"  />
        </div>
      </div>

      {/* ── WEAKNESS ANALYSIS ──────────────────────────────────── */}
      {sorted.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="section-header">
            <span className="section-title">Weakness Analysis</span>
            <button className="section-link" onClick={() => nav('/profile')}>View all →</button>
          </div>
          {sorted.slice(0, 3).map(w => {
            const trend30 = w.trend_label
            const pct     = w.pct_games_affected || 0
            return (
              <div key={w.concept_code} className="weakness-bar-row" style={{ cursor: 'pointer' }}
                   onClick={() => nav(`/weakness/${encodeURIComponent(w.concept_code)}`)}>
                <div className="weakness-bar-accent" style={{ background: conceptColor(w.concept_code) }} />
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

      {/* ── RECENT GAMES ───────────────────────────────────────── */}
      {games.length > 0 && (
        <div className="card">
          <div className="section-header">
            <span className="section-title">Recent Games</span>
            <button className="section-link" onClick={() => nav('/games')}>See all →</button>
          </div>
          {games.map(g => {
            const acc = g.accuracy_pct
            const accColor    = accuracyColor(acc)
            const resultClass = g.result === 'win' ? 'result-win' : g.result === 'loss' ? 'result-loss' : 'result-draw'
            const resultLetter = g.result === 'win' ? 'W' : g.result === 'loss' ? 'L' : 'D'
            return (
              <div key={g.game_id} className="game-row"
                   onClick={() => nav(`/games/${g.game_id}`)}>
                <div className={`game-result-circle ${resultClass}`}>{resultLetter}</div>
                <div className="game-row-info">
                  <div className="game-row-opponent">Opponent ({g.opponent_elo ?? '?'})</div>
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

      {/* ── ANALYSIS PANEL + BACKDROP ──────────────────────────── */}
      {panelOpen && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 499 }}
          onClick={() => setPanelOpen(false)}
        />
      )}
      <AnalysisPanel
        isOpen={panelOpen}
        onClose={() => setPanelOpen(false)}
        skillScores={skillScores}
        rx={rx}
        gaps={gaps}
      />
    </div>
  )
}
