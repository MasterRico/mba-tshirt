import { useState, useEffect } from 'react'
import { api } from '../../services/api'
import LoadingSpinner from '../../components/LoadingSpinner'
import StatCard from '../../components/StatCard'
import {
  BarChart3, Upload, TrendingUp, Target, DollarSign, Award, RotateCcw
} from 'lucide-react'

export default function TsfPerformance() {
  const [summary, setSummary] = useState(null)
  const [nichePerf, setNichePerf] = useState([])
  const [rotationCandidates, setRotationCandidates] = useState([])
  const [slotRecs, setSlotRecs] = useState(null)
  const [loading, setLoading] = useState(true)
  const [csvInput, setCsvInput] = useState('')
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState(null)

  useEffect(() => { loadData() }, [])

  async function loadData() {
    try {
      const [s, np, rc, sr] = await Promise.all([
        api.tsf.getPerformanceSummary(),
        api.tsf.getNichePerformance(),
        api.tsf.getRotationCandidates(),
        api.tsf.getSlotRecommendations(),
      ])
      setSummary(s)
      setNichePerf(np)
      setRotationCandidates(rc)
      setSlotRecs(sr)
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  async function importCsv() {
    if (!csvInput.trim()) return
    setImporting(true)
    try {
      const result = await api.tsf.importCsv(csvInput)
      setImportResult(result)
      setCsvInput('')
      await loadData()
    } catch (err) { console.error(err) }
    finally { setImporting(false) }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <BarChart3 className="text-green-600" /> Performance & Slot-Management
      </h1>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Tracked" value={summary.total_tracked}
            icon={<Target size={20} className="text-blue-500" />} />
          <StatCard label="Winners" value={summary.winners}
            icon={<Award size={20} className="text-green-500" />} />
          <StatCard label="Win-Rate" value={`${summary.win_rate}%`}
            icon={<TrendingUp size={20} className="text-purple-500" />} />
          <StatCard label="Umsatz" value={`$${summary.total_revenue}`}
            icon={<DollarSign size={20} className="text-green-500" />} />
          <StatCard label="Einheiten" value={summary.total_units}
            icon={<BarChart3 size={20} className="text-blue-500" />} />
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Niche Performance */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold mb-4">Performance nach Nische</h2>
          <div className="space-y-2">
            {nichePerf.map((np, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <span className="font-medium">Nische #{np.niche_id}</span>
                  <span className="text-xs ml-2 text-gray-500">{np.designs} Designs</span>
                </div>
                <div className="text-right text-sm">
                  <div className="text-green-600 font-medium">${np.revenue}</div>
                  <div className="text-gray-500">{np.win_rate}% Win-Rate</div>
                </div>
              </div>
            ))}
            {nichePerf.length === 0 && (
              <p className="text-gray-400 text-center py-4">Noch keine Performance-Daten</p>
            )}
          </div>
        </div>

        {/* Rotation Candidates */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold mb-4 flex items-center gap-2">
            <RotateCcw size={18} /> Rotations-Kandidaten
          </h2>
          <div className="space-y-2">
            {rotationCandidates.map((rc, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-orange-50 rounded-lg border border-orange-200">
                <div>
                  <span className="font-medium text-sm">"{rc.primary_text}"</span>
                  <div className="text-xs text-gray-500 mt-1">
                    {rc.days_live} Tage live | {rc.units_sold} Verkäufe
                  </div>
                </div>
                <div className="text-xs text-orange-600">{rc.reason}</div>
              </div>
            ))}
            {rotationCandidates.length === 0 && (
              <p className="text-gray-400 text-center py-4">Keine Rotations-Kandidaten</p>
            )}
          </div>
        </div>
      </div>

      {/* Slot Recommendations */}
      {slotRecs && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold mb-4">Slot-Empfehlungen ({slotRecs.available_slots} Slots frei)</h2>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(slotRecs.recommendations || []).filter(r => r.action !== 'hold').map((rec, i) => (
              <div key={i} className={`p-3 rounded-lg border ${
                rec.action === 'add' ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
              }`}>
                <div className="font-medium">{rec.niche}</div>
                <div className="text-sm text-gray-600">
                  {rec.current_slots} → {rec.ideal_slots} Slots
                  <span className="ml-2 font-medium">
                    ({rec.action === 'add' ? `+${rec.designs_to_add}` : 'reduzieren'})
                  </span>
                </div>
                <div className="text-xs text-gray-500">Win-Rate: {(rec.win_rate * 100).toFixed(0)}%</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CSV Import */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h2 className="font-semibold mb-4 flex items-center gap-2">
          <Upload size={18} /> MBA Sales CSV importieren
        </h2>
        <p className="text-sm text-gray-500 mb-3">
          Exportiere deinen MBA Sales Report und füge den CSV-Inhalt hier ein.
        </p>
        <textarea
          value={csvInput}
          onChange={e => setCsvInput(e.target.value)}
          placeholder="ASIN,Title,Units Ordered,Royalties..."
          rows={6}
          className="w-full px-4 py-3 border rounded-lg font-mono text-xs resize-y"
        />
        <button onClick={importCsv} disabled={importing || !csvInput.trim()}
          className="mt-3 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50">
          {importing ? 'Importiere...' : 'CSV importieren'}
        </button>
        {importResult && (
          <div className="mt-3 p-3 bg-green-50 rounded-lg text-sm">
            Aktualisiert: {importResult.updated} | Nicht gefunden: {importResult.not_found} | Fehler: {importResult.errors}
          </div>
        )}
      </div>
    </div>
  )
}
