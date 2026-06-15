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
  const [gaps, setGaps] = useState(null)
  const [genImg, setGenImg] = useState({})
  const [genErr, setGenErr] = useState({})
  const [genBusy, setGenBusy] = useState(null)
  const [listing, setListing] = useState({})
  const [listBusy, setListBusy] = useState(null)
  const [loading, setLoading] = useState(true)

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
    try {
      const g = await api.tsf.getGaps(null, 12)
      setGaps(g)
    } catch (err) {
      console.error('Gaps load failed:', err)
    }
  }

  async function makeImage(id) {
    setGenBusy(id)
    setGenErr((prev) => ({ ...prev, [id]: null }))
    try {
      const r = await api.tsf.generateImage(id)
      setGenImg((prev) => ({ ...prev, [id]: r.image_url }))
    } catch (err) {
      setGenErr((prev) => ({ ...prev, [id]: err.message || 'Fehler' }))
    } finally {
      setGenBusy(null)
    }
  }

  async function makeListing(id) {
    setListBusy(id)
    setListing((prev) => ({ ...prev, [id]: { error: null } }))
    try {
      const r = await api.tsf.listingByVision(id)
      setListing((prev) => ({ ...prev, [id]: r }))
    } catch (err) {
      setListing((prev) => ({ ...prev, [id]: { error: err.message || 'Fehler' } }))
    } finally {
      setListBusy(null)
    }
  }

  if (loading) return <LoadingSpinner />

  const seasonal = data?.seasonal_upcoming || []

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shirt className="text-purple-600" /> T-Shirt Design Factory
          </h1>
          <p className="text-gray-500 mt-1">MBA Tier 100 — Winner-Cockpit</p>
        </div>
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
              <div key={i} className="p-2 border-b last:border-0">
                <div className="flex items-center justify-between">
                  <div className="min-w-0">
                    <div className="font-medium truncate">{c.primary_text}</div>
                    <div className="text-xs text-gray-500 truncate">{c.niche || '—'} · {c.font}</div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`text-sm font-semibold ${c.fit_score >= 0.6 ? 'text-green-600' : c.fit_score >= 0.3 ? 'text-amber-600' : 'text-gray-400'}`}>
                      {Math.round((c.fit_score || 0) * 100)}%
                    </span>
                    <button
                      onClick={() => makeImage(c.id)}
                      disabled={genBusy === c.id}
                      className="text-xs px-2 py-1 bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50"
                    >
                      {genBusy === c.id ? '…' : 'Bild'}
                    </button>
                    <button
                      onClick={() => makeListing(c.id)}
                      disabled={listBusy === c.id}
                      className="text-xs px-2 py-1 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
                    >
                      {listBusy === c.id ? '…' : 'Listing'}
                    </button>
                  </div>
                </div>
                {genErr[c.id] && (
                  <div className="mt-2 text-xs text-rose-700 bg-rose-50 rounded p-2">⚠ {genErr[c.id]}</div>
                )}
                {genImg[c.id] && (
                  <img src={genImg[c.id]} alt="" className="mt-2 w-28 h-28 object-cover rounded border" />
                )}
                {listing[c.id] && (
                  <ListingPanel data={listing[c.id]} />
                )}
              </div>
            ))}
            {(!candidates || candidates.length === 0) && (
              <p className="text-gray-400 text-center py-4">Noch keine Kandidaten.</p>
            )}
          </div>
        </div>
      </div>

      {/* Luecken-Finder: davon mehr machen */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <Target size={20} className="text-rose-600" /> Lücken: davon solltest du mehr machen
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {(gaps || []).slice(0, 12).map((g, i) => (
            <div key={i} className="p-3 bg-rose-50 rounded-lg">
              <div className="text-sm font-medium">{g.action}</div>
              <div className="text-xs text-gray-500 mt-1">{g.niche} · {g.dimension}</div>
            </div>
          ))}
          {(!gaps || gaps.length === 0) && (
            <p className="text-gray-400 text-center py-4 col-span-full">Keine offenen Lücken erkannt (oder noch zu wenig Know-how-Daten).</p>
          )}
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
      </div>
    </div>
  )
}

function ListingPanel({ data }) {
  const [lang, setLang] = useState('en')
  if (data.error) {
    return <div className="mt-2 text-xs text-rose-700 bg-rose-50 rounded p-2">⚠ {data.error}</div>
  }
  const block = data[lang] || {}
  const limits = data.limits || {}
  const fields = [
    ['brand', 'Brand'], ['title', 'Title'],
    ['bullet1', 'Bullet 1'], ['bullet2', 'Bullet 2'], ['description', 'Description'],
  ]
  const copy = (t) => navigator.clipboard && navigator.clipboard.writeText(t || '')
  return (
    <div className="mt-2 bg-gray-50 border rounded p-3 text-xs">
      <div className="flex items-center justify-between mb-2">
        <div className="flex gap-1">
          {['en', 'de'].map((l) => (
            <button key={l} onClick={() => setLang(l)}
              className={`px-2 py-0.5 rounded uppercase ${lang === l ? 'bg-indigo-600 text-white' : 'bg-white border text-gray-600'}`}>
              {l}
            </button>
          ))}
        </div>
        {data.compliant
          ? <span className="text-green-700 bg-green-100 px-2 py-0.5 rounded">✓ TM clear</span>
          : <span className="text-rose-700 bg-rose-100 px-2 py-0.5 rounded">⚠ TM: {(data.flagged || []).join(', ')}</span>}
      </div>
      {fields.map(([key, label]) => (
        <div key={key} className="mb-2">
          <div className="flex items-center justify-between text-[10px] text-gray-500">
            <span>{label} <span className="text-gray-400">({(block[key] || '').length}/{limits[key]})</span></span>
            <button onClick={() => copy(block[key])} className="text-indigo-600 hover:underline">copy</button>
          </div>
          <div className="bg-white border rounded px-2 py-1 whitespace-pre-wrap">{block[key] || '—'}</div>
        </div>
      ))}
    </div>
  )
}
