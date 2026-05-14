import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Home from './pages/Home.jsx'
import DrillBoard from './pages/DrillBoard.jsx'
import Learn from './pages/Learn.jsx'
import GamesList from './pages/GamesList.jsx'
import GameReview from './pages/GameReview.jsx'
import Profile from './pages/Profile.jsx'
import WeaknessDetail from './pages/WeaknessDetail.jsx'

const TAB_LINKS = [
  { to: '/',        label: 'Home',    icon: '⌂',  end: true },
  { to: '/study',   label: 'Study',   icon: '♟' },
  { to: '/learn',   label: 'Learn',   icon: '📖' },
  { to: '/games',   label: 'Games',   icon: '🎯' },
  { to: '/profile', label: 'Profile', icon: '👤' },
]

function Nav() {
  const cls = ({ isActive }) => isActive ? 'nav-link active' : 'nav-link'
  return (
    <>
      <nav className="top-nav">
        <span className="nav-brand">ChessEDU</span>
        {TAB_LINKS.map(t => (
          <NavLink key={t.to} to={t.to} className={cls} end={t.end}>
            {t.label}
          </NavLink>
        ))}
      </nav>
      <nav className="bottom-nav">
        {TAB_LINKS.map(t => (
          <NavLink key={t.to} to={t.to} className={cls} end={t.end}>
            <span className="bottom-nav-icon">{t.icon}</span>
            <span className="bottom-nav-label">{t.label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  )
}

const PLAYER_ID = 1

export default function App() {
  const [profileData,      setProfileData]      = useState(null)
  const [prescriptionData, setPrescriptionData] = useState(null)

  return (
    <BrowserRouter>
      <Nav />
      <main className="page-content">
        <Routes>
          <Route path="/" element={
            <Home playerId={PLAYER_ID}
              profileData={profileData} prescriptionData={prescriptionData}
              onProfileLoad={setProfileData} onPrescriptionLoad={setPrescriptionData}
            />
          } />
          <Route path="/study" element={<DrillBoard />} />
          <Route path="/drill" element={<Navigate to="/study" replace />} />
          <Route path="/learn" element={<Learn playerId={PLAYER_ID} prescriptionData={prescriptionData} />} />
          <Route path="/games" element={<GamesList playerId={PLAYER_ID} />} />
          <Route path="/games/:gameId" element={<GameReview playerId={PLAYER_ID} />} />
          <Route path="/profile" element={
            <Profile playerId={PLAYER_ID}
              profileData={profileData} prescriptionData={prescriptionData}
              onProfileLoad={setProfileData} onPrescriptionLoad={setPrescriptionData}
            />
          } />
          <Route path="/weakness/:code" element={<WeaknessDetail playerId={PLAYER_ID} />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
