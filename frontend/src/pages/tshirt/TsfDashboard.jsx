import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../services/api'
import StatCard from '../../components/StatCard'
import LoadingSpinner from '../../components/LoadingSpinner'
import {
  Shirt, TrendingUp, Brain, RotateCcw, Zap, Calendar,
  Target, AlertTriangle, CheckCircle, BarChart3, Wallet
} from 'lucide-react'

export default function TsfDashboard() {
  const [data, setData] = useState(null)
  const [sales, setSales] = useState(null)
  const [planner, setPlanner] = useState(null)
  const [candidates, setCandidates] = useState(null)
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
    try {
      const s = await api.tsf.getSalesSummary()
      setSales(s)
    } catch (err) {
      console.error('Sales summary load failed:', err)
    }
    try {
      const pl = await api.tsf.getSeasonalPlanner()
      setPlanner(pl)
    } catch (err) {
      console.error('Planner load failed:', err)
    }
    try {
      const c = await api.tsf.getCandidates(null, 10)
      setCandidates(c)
    } catch (err) {
      console.error('Candidates load failed:', err)
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

      {/* Winner-Cockpit: Saison-Planer + Top-Kandidaten */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Calendar size={20} className="text-amber-600" /> Was jetzt erstellen (Lead-Time)
          </h2>
          <div className="space-y-2">
            {(planner?.recommend_now || []).slice(0, 6).map((p, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-amber-50 rounded-lg">
                <div>
                  <span className="font-medium">{p.name}</span>
                  <span className="ml-2 text-xs text-gray-500">{(p.niches || []).slice(0, 2).join(', ')}</span>
                </div>
                <span className="text-sm font-medium text-amber-700">{p.days_until_peak} Tage bis Peak</span>
              </div>
            ))}
            {(!planner?.recommend_now || planner.recommend_now.length === 0) && (
              <p className="text-gray-400 text-center py-4">Kein offenes Saison-Fenster gerade.</p>
            )}
          </div>
        </div>
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <CheckCircle size={20} className="text-green-600" /> Top Upload-Kandidaten (Know-how-Fit)
          </h2>
          <div className="space-y-2">
            {(candidates || []).slice(0, 8).map((c, i) => (
              <div key={i} className="flex items-center justify-between p-2 border-b last:border-0">
                <div className="min-w-0">
                  <div className="font-medium truncate">{c.primary_text}</div>
                  <div className="text-xs text-gray-500 truncate">{c.niche || '—'} · {c.font}</div>
                </div>
                <span className={`ml-2 text-sm font-semibold ${c.fit_score >= 0.6 ? 'text-green-600' : c.fit_score >= 0.3 ? 'text-amber-600' : 'text-gray-400'}`}>
                  {Math.round((c.fit_score || 0) * 100)}%
                </span>
              </div>
            ))}
            {(!candidates || candidates.length === 0) && (
              <p className="text-gray-400 text-center py-4">Noch keine Kandidaten.</p>
            )}
          </div>
        </div>
      </div>

      {/* Konto-Umsatz: echte MBA-Verkaeufe (design-unabhaengig) */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Wallet size={20} className="text-emerald-600" /> Konto-Umsatz (echte MBA-Verkäufe)
        </h2>
        {sales && sales.total_units > 0 ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
              <StatCard label="Σ Umsatz (≈ EUR)" value={`€${(sales.combined_eur_estimate || 0).toFixed(2)}`} icon={<Wallet size={20} className="text-emerald-500" />} />
              <StatCard label="Verkaufte Einheiten" value={sales.total_units || 0} icon={<TrendingUp size={20} className="text-blue-500" />} />
              <StatCard label="Produkte" value={sales.distinct_products || 0} icon={<Shirt size={20} className="text-purple-500" />} />
              <StatCard label="Umsatz nach Währung" value={Object.entries(sales.totals_by_currency || {}).map(([c, v]) => `${v.toFixed(2)} ${c}`).join(' · ') || '—'} icon={<BarChart3 size={20} className="text-green-500" />} />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="py-2">Top-Produkt</th><th>ASIN</th><th className="text-right">Units</th><th className="text-right">≈ EUR</th>
                  </tr>
                </thead>
                <tbody>
                  {(sales.top_products || []).map((prod, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-2 pr-2">{prod.title}</td>
                      <td className="text-gray-500">{prod.asin}</td>
                      <td className="text-right">{prod.units}</td>
                      <td className="text-right">€{(prod.earnings_eur || 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-xs text-gray-400 mt-3">{sales.fx_note}</p>
          </>
        ) : (
          <p className="text-gray-400 text-center py-4">
            Noch keine Konto-Verkäufe importiert.
          </p>
        )}
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
