import { useEffect, useState } from 'react'
import axios from 'axios'

const PLAYER_ID = 1

export default function Openings() {
  const [gaps,    setGaps]    = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    axios.get(`/api/players/${PLAYER_ID}/opening-gaps`)
      .then(r => setGaps(r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <div className="coach-message-box" style={{ marginBottom: 16 }}>
        <div className="coach-avatar-wrap">
          <div className="coach-avatar">♟</div>
        </div>
        <div style={{ flex: 1 }}>
          <div className="coach-name">Coach</div>
          <div className="coach-message-text">
            Personalized opening roadmaps are coming soon. Here are your current opening gaps — the lines where you're losing most often.
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Opening Gaps</div>
        {loading ? (
          <div className="loading">Loading…</div>
        ) : gaps.length === 0 ? (
          <div className="empty">No opening gaps detected yet. Play more games to build data.</div>
        ) : (
          gaps.map(g => (
            <div key={g.eco} className="opening-row">
              <span className="eco-badge">{g.eco}</span>
              <span className="opening-name">{g.opening_name || g.eco}</span>
              <span className="opening-loss">{Math.round(g.gap_score * 100)}% gap</span>
              <span className="opening-days">{g.games_seen} games</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
