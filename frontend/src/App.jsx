import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import { BarChart3, Shirt, TrendingUp, Shield, LogOut } from 'lucide-react'
import TsfDashboard from './pages/tshirt/TsfDashboard'
import TsfDesigns from './pages/tshirt/TsfDesigns'
import TsfResearch from './pages/tshirt/TsfResearch'
import TsfCompliance from './pages/tshirt/TsfCompliance'
import TsfPerformance from './pages/tshirt/TsfPerformance'
import TokenGate, { clearStoredToken } from './components/TokenGate'

const navItems = [
  { to: '/tsf', icon: Shirt, label: 'Dashboard' },
  { to: '/tsf/designs', icon: Shirt, label: 'Designs' },
  { to: '/tsf/research', icon: TrendingUp, label: 'Research' },
  { to: '/tsf/compliance', icon: Shield, label: 'Trademark-Check' },
  { to: '/tsf/performance', icon: BarChart3, label: 'Performance' },
]

function logout() {
  clearStoredToken()
  window.location.reload()
}

export default function App() {
  return (
    <TokenGate>
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-purple-900 text-white flex flex-col">
        <div className="p-6 border-b border-purple-700">
          <h1 className="text-xl font-bold">MBA T-Shirt Factory</h1>
          <p className="text-sm text-purple-200 mt-1">Design Automation</p>
        </div>
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink key={to} to={to} end={to === '/tsf'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 rounded-lg transition-colors text-sm ${
                  isActive ? 'bg-purple-700 text-white' : 'text-purple-200 hover:bg-purple-800 hover:text-white'
                }`
              }>
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <button
          onClick={logout}
          className="mx-4 mb-2 flex items-center gap-2 text-xs text-purple-300 hover:text-white"
        >
          <LogOut size={14} /> Abmelden
        </button>
        <div className="p-4 text-xs text-purple-300 border-t border-purple-700">
          v1.0.0 — MBA Automation
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-7xl mx-auto p-6">
          <Routes>
            <Route path="/" element={<Navigate to="/tsf" replace />} />
            <Route path="/tsf" element={<TsfDashboard />} />
            <Route path="/tsf/designs" element={<TsfDesigns />} />
            <Route path="/tsf/research" element={<TsfResearch />} />
            <Route path="/tsf/compliance" element={<TsfCompliance />} />
            <Route path="/tsf/performance" element={<TsfPerformance />} />
          </Routes>
        </div>
      </main>
    </div>
    </TokenGate>
  )
}
