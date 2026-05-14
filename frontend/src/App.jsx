import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Home from './pages/Home.jsx'
import DrillBoard from './pages/DrillBoard.jsx'
import Learn from './pages/Learn.jsx'
import GamesList from './pages/GamesList.jsx'
import GameReview from './pages/GameReview.jsx'
import Profile from './pages/Profile.jsx'
import WeaknessDetail from './pages/WeaknessDetail.jsx'
import Openings from './pages/Openings.jsx'

const TAB_LINKS = [
  { to: '/',         label: 'Coach',    icon: '♟',  end: true },
  { to: '/training', label: 'Training', icon: '🎓' },
  { to: '/games',    label: 'Games',    icon: '🎮' },
  { to: '/concepts', label: 'Concepts', icon: '📖' },
  { to: '/openings', label: 'Openings', icon: '🌐' },
]

function Nav() {
  const tabCls = ({ isActive }) => `bottom-nav-item${isActive ? ' active' : ''}`
  return (
    <>
      <nav className="top-nav">
        <span className="nav-brand">ChessEDU</span>
        <NavLink to="/profile" className="profile-icon-btn">👤</NavLink>
      </nav>
      <nav className="bottom-nav">
        {TAB_LINKS.map(t => (
          <NavLink key={t.to} to={t.to} className={tabCls} end={t.end}>
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
          <Route path="/training" element={<DrillBoard />} />
          <Route path="/games"    element={<GamesList playerId={PLAYER_ID} />} />
          <Route path="/games/:gameId" element={<GameReview playerId={PLAYER_ID} />} />
          <Route path="/concepts" element={<Learn playerId={PLAYER_ID} prescriptionData={prescriptionData} />} />
          <Route path="/openings" element={<Openings playerId={PLAYER_ID} />} />
          <Route path="/profile"  element={
            <Profile playerId={PLAYER_ID}
              profileData={profileData} prescriptionData={prescriptionData}
              onProfileLoad={setProfileData} onPrescriptionLoad={setPrescriptionData}
            />
          } />
          <Route path="/weakness/:code" element={<WeaknessDetail playerId={PLAYER_ID} />} />
          {/* Legacy redirects */}
          <Route path="/drill" element={<Navigate to="/training" replace />} />
          <Route path="/study" element={<Navigate to="/training" replace />} />
          <Route path="/learn" element={<Navigate to="/concepts" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
