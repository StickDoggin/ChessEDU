import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import { CONCEPTS, conceptName, conceptShort, conceptColor } from '../concepts.js'

const CATEGORIES = [
  {
    label: 'Tactics',
    codes: ['3.3.3', '3.1.1', '3.1.3', '3.1.4', '3.1.5', '3.1.6', '3.1.7',
            '3.1.8', '3.1.10', '3.1.11', '3.1.12', '3.1.13', '3.1.14', '3.2.1', '3.2.2'],
  },
  {
    label: 'Calculation',
    codes: ['3.3.6.a', '3.3.6.b', '3.3.6.c', '3.3.6.d'],
  },
  {
    label: 'Quiet Moves',
    codes: ['3.4.2.a', '3.4.2.b', '3.4.2.c', '3.4.2.d', '3.4.2.e', '3.4.2.f'],
  },
  {
    label: 'Positional',
    codes: ['4.1.4', '4.1.5', '4.2.3', '4.2.4', '4.4.3', '4.4.5'],
  },
  {
    label: 'Opening',
    codes: ['6.1'],
  },
]

export default function Learn({ playerId, prescriptionData }) {
  const [rx,      setRx]      = useState(prescriptionData || [])
  const [search,  setSearch]  = useState('')
  const nav = useNavigate()

  useEffect(() => {
    if (!prescriptionData) {
      axios.get(`/api/players/${playerId}/prescription`)
        .then(r => setRx(r.data || []))
        .catch(() => {})
    }
  }, [])

  const activeCodes = new Set(rx.map(r => r.concept_code))
  const q = search.toLowerCase()

  function matches(code) {
    if (!q) return true
    const c = CONCEPTS[code]
    if (!c) return false
    return c.name.toLowerCase().includes(q) || (c.short || '').toLowerCase().includes(q) || code.includes(q)
  }

  return (
    <div>
      <input
        className="learn-search"
        placeholder="Search concepts…"
        value={search}
        onChange={e => setSearch(e.target.value)}
      />

      {CATEGORIES.map(cat => {
        const visible = cat.codes.filter(c => CONCEPTS[c] && matches(c))
        if (!visible.length) return null
        return (
          <div key={cat.label} className="learn-category">
            <div className="learn-category-label">{cat.label}</div>
            {visible.map(code => {
              const isActive  = activeCodes.has(code)
              const color     = conceptColor(code)
              const shortDesc = conceptShort(code)
              return (
                <div key={code} className="learn-row">
                  <span className="learn-dot" style={{ background: color }} />
                  <div className="learn-info">
                    <div className="learn-name">
                      {conceptName(code)}
                      {isActive && <span className="badge badge-red" style={{ marginLeft: 8, fontSize: 10 }}>Active</span>}
                    </div>
                    {shortDesc && <div className="learn-short">{shortDesc}</div>}
                  </div>
                  <div className="learn-actions">
                    <button className="btn btn-secondary"
                            style={{ fontSize: 11, padding: '5px 10px' }}
                            onClick={() => nav(`/weakness/${encodeURIComponent(code)}`)}>
                      Deep Dive ↗
                    </button>
                    <button className="btn btn-primary"
                            style={{ fontSize: 11, padding: '5px 10px' }}
                            onClick={() => nav('/study')}>
                      Practice →
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )
      })}
    </div>
  )
}
