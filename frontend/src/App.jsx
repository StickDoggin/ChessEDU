import { useState } from 'react'
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import DrillBoard from './pages/DrillBoard.jsx'
import GamesList from './pages/GamesList.jsx'
import WeaknessDetail from './pages/WeaknessDetail.jsx'

function Nav() {
  const link = ({ isActive }) => isActive ? 'nav-link active' : 'nav-link'
  return (
    <nav className="top-nav">
      <span className="nav-brand">ChessEDU</span>
      <NavLink to="/" className={link} end>Dashboard</NavLink>
      <NavLink to="/drill" className={link}>Drill</NavLink>
      <NavLink to="/games" className={link}>Games</NavLink>
    </nav>
  )
}

const PLAYER_ID = 1

export default function App() {
  const [profileData,      setProfileData]      = useState(null)
  const [prescriptionData, setPrescriptionData] = useState(null)
  const [gamesData,        setGamesData]        = useState(null)

  return (
    <BrowserRouter>
      <Nav />
      <main className="page-content">
        <Routes>
          <Route path="/" element={
            <Dashboard
              playerId={PLAYER_ID}
              profileData={profileData}
              prescriptionData={prescriptionData}
              onProfileLoad={setProfileData}
              onPrescriptionLoad={setPrescriptionData}
            />
          } />
          <Route path="/drill" element={<DrillBoard />} />
          <Route path="/games" element={
            <GamesList
              playerId={PLAYER_ID}
              gamesData={gamesData}
              onGamesLoad={setGamesData}
            />
          } />
          <Route path="/weakness/:code" element={<WeaknessDetail playerId={PLAYER_ID} />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
