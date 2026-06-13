import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../services/api'
import StatCard from '../../components/StatCard'
import LoadingSpinner from '../../components/LoadingSpinner'
import {
  Shirt, TrendingUp, Brain, RotateCcw, Zap, Calendar,
  Target, AlertTriangle, CheckCircle, BarChart3
} from 'lucide-react'

export default function TsfDashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [pipelineRunning, setPipelineRunning] = useState(false)

  useEffect(() => {
    loadDashboard()
  }, [])

  async function loadDashboard() {
    try {
      const result = await api.tsf.getDashboard()
      setData(result)
    } catch (err) {
      console.error('Dashboard load failed:', err)
    } finally {
      setLoading(false)
    }
  }

  async function runPipeline() {
    setPipelineRunning(true)
    try {
      await api.tsf.runFullPipeline()
      await loadDashboard()
    } catch (err) {
      console.error('Pipeline failed:', err)
    } finally {
      setPipelineRunning(false)
    }
  }

  if (loading) return <LoadingSpinner />

  const slots = data?.slots || {}
  const perf = data?.performance || {}
  const learning = data?.learning || {}
  const seasonal = data?.seasonal_upcoming || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shirt className="text-purple-600" /> T-Shirt Design Factory
          </h1>
          <p className="text-gray-500 mt-1">MBA Tier 100 — Automatische Design-Pipeline</p>
        </div>
        <button
          onClick={runPipeline}
          disabled={pipelineRunning}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
        >
          <Zap size={18} />
          {pipelineRunning ? 'Pipeline läuft...' : 'Pipeline starten'}
        </button>
      </div>

      {/* Slot Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Belegte Slots"
          value={`${slots.used_slots || 0} / ${slots.total_slots || 100}`}
          icon={<Target size={20} className="text-blue-500" />}
        />
        <StatCard
          label="Winner"
          value={slots.winners || 0}
          icon={<CheckCircle size={20} className="text-green-500" />}
        />
        <StatCard
          label="Underperformer"
          value={slots.underperformers || 0}
          icon={<AlertTriangle size={20} className="text-orange-500" />}
        />
        <StatCard
          label="Freie Slots"
          value={slots.available_slots || 100}
          icon={<Shirt size={20} className="text-purple-500" />}
        />
      </div>

      {/* Performance */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Gesamt-Umsatz"
          value={`$${(perf.total_revenue || 0).toFixed(2)}`}
          icon={<BarChart3 size={20} className="text-green-500" />}
        />
        <StatCard
          label="Verkaufte Einheiten"
          value={perf.total_units || 0}
          icon={<TrendingUp size={20} className="text-blue-500" />}
        />
        <StatCard
          label="Win-Rate"
          value={`${perf.win_rate || 0}%`}
          icon={<Target size={20} className="text-purple-500" />}
        />
        <StatCard
          label="Ø Umsatz/Design"
          value={`$${(perf.avg_revenue_per_design || 0).toFixed(2)}`}
          icon={<BarChart3 size={20} className="text-indigo-500" />}
        />
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Top Niches */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Target size={20} /> Top Nischen
          </h2>
          <div className="space-y-3">
            {(data?.top_niches || []).map((niche, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <span className="font-medium">{niche.name}</span>
                  <span className="ml-2 text-xs px-2 py-1 rounded-full bg-purple-100 text-purple-700">
                    {niche.category}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium text-green-600">
                    {(niche.win_rate * 100).toFixed(0)}% Win-Rate
                  </div>
                  <div className="text-xs text-gray-500">
                    {niche.competition || '?'} Competition
                  </div>
                </div>
              </div>
            ))}
            {(!data?.top_niches || data.top_niches.length === 0) && (
              <p className="text-gray-400 text-center py-4">
                Noch keine Nischen-Daten. Starte die Pipeline!
              </p>
            )}
          </div>
        </div>

        {/* Upcoming Seasonal */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Calendar size={20} /> Saisonale Events
          </h2>
          <div className="space-y-3">
            {seasonal.map((event, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <span className="font-medium">{event.name}</span>
                  <span className={`ml-2 text-xs px-2 py-1 rounded-full ${
                    event.priority === 'critical' ? 'bg-red-100 text-red-700' :
                    event.priority === 'high' ? 'bg-orange-100 text-orange-700' :
                    'bg-blue-100 text-blue-700'
                  }`}>
                    {event.priority}
                  </span>
                </div>
                <div className="text-right">
                  <div className="text-sm font-medium">
                    {event.days_until} Tage
                  </div>
                </div>
              </div>
            ))}
            {seasonal.length === 0 && (
              <p className="text-gray-400 text-center py-4">
                Keine anstehenden saisonalen Events
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Learning Insights */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Brain size={20} /> Self-Learning Insights
        </h2>
        {learning.total_insights > 0 ? (
          <div>
            <p className="text-gray-600 mb-3">
              {learning.total_insights} Insights aus {Object.keys(learning.categories || {}).length} Kategorien
            </p>
            <div className="space-y-2">
              {(learning.high_confidence || []).slice(0, 5).map((insight, i) => (
                <div key={i} className="flex items-start gap-3 p-3 bg-green-50 rounded-lg">
                  <CheckCircle size={16} className="text-green-500 mt-0.5 flex-shrink-0" />
                  <div>
                    <span className="text-sm font-medium text-gray-700">
                      [{insight.category}] {insight.key}:
                    </span>
                    <span className="text-sm text-gray-600 ml-1">{insight.value}</span>
                    <span className="text-xs text-green-600 ml-2">
                      ({(insight.confidence * 100).toFixed(0)}% Konfidenz)
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="text-gray-400 text-center py-4">
            Noch keine Learning-Daten. Das System lernt aus deinen Verkaufsdaten!
          </p>
        )}
      </div>

      {/* Quick Links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Link to="/tsf/designs" className="p-4 bg-white rounded-xl shadow-sm border hover:shadow-md transition-shadow text-center">
          <Shirt size={24} className="mx-auto text-purple-500 mb-2" />
          <span className="text-sm font-medium">Designs</span>
        </Link>
        <Link to="/tsf/research" className="p-4 bg-white rounded-xl shadow-sm border hover:shadow-md transition-shadow text-center">
          <TrendingUp size={24} className="mx-auto text-blue-500 mb-2" />
          <span className="text-sm font-medium">Research</span>
        </Link>
        <Link to="/tsf/compliance" className="p-4 bg-white rounded-xl shadow-sm border hover:shadow-md transition-shadow text-center">
          <AlertTriangle size={24} className="mx-auto text-orange-500 mb-2" />
          <span className="text-sm font-medium">Trademark-Check</span>
        </Link>
        <Link to="/tsf/performance" className="p-4 bg-white rounded-xl shadow-sm border hover:shadow-md transition-shadow text-center">
          <BarChart3 size={24} className="mx-auto text-green-500 mb-2" />
          <span className="text-sm font-medium">Performance</span>
        </Link>
      </div>
    </div>
  )
}
