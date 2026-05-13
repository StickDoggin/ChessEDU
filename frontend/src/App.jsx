import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import DrillBoard from './pages/DrillBoard.jsx'
import GamesList from './pages/GamesList.jsx'

function Nav() {
  const link = ({ isActive }) => isActive ? 'nav-link active' : 'nav-link'
  return (
    <nav className="top-nav">
      <span className="nav-brand">Chess Study Engine</span>
      <NavLink to="/" className={link} end>Dashboard</NavLink>
      <NavLink to="/drill" className={link}>Drill</NavLink>
      <NavLink to="/games" className={link}>Games</NavLink>
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <main className="page-content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/drill" element={<DrillBoard />} />
          <Route path="/games" element={<GamesList />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
