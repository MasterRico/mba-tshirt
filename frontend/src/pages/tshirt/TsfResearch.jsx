import { useState, useEffect } from 'react'
import { api } from '../../services/api'
import LoadingSpinner from '../../components/LoadingSpinner'
import { TrendingUp, Search, RefreshCw, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react'

const DIRECTION_ICONS = {
  rising: <ArrowUpRight size={16} className="text-green-500" />,
  declining: <ArrowDownRight size={16} className="text-red-500" />,
  stable: <Minus size={16} className="text-gray-400" />,
}

export default function TsfResearch() {
  const [tab, setTab] = useState('trends')
  const [trends, setTrends] = useState([])
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [researching, setResearching] = useState(false)
  const [kwInput, setKwInput] = useState('')
  const [suggestions, setSuggestions] = useState([])

  useEffect(() => {
    if (tab === 'trends') loadTrends()
    else loadItems()
  }, [tab])

  async function loadTrends() {
    setLoading(true)
    try {
      setTrends(await api.tsf.getTrends())
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  async function loadItems() {
    setLoading(true)
    try {
      setItems(await api.tsf.getResearchItems())
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
  }

  async function runResearch() {
    setResearching(true)
    try {
      await api.tsf.runResearch()
      if (tab === 'trends') await loadTrends()
      else await loadItems()
    } catch (err) { console.error(err) }
    finally { setResearching(false) }
  }

  async function searchSuggestions() {
    if (!kwInput.trim()) return
    try {
      const data = await api.tsf.getSuggestions(kwInput)
      setSuggestions(data.suggestions || [])
    } catch (err) { console.error(err) }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <TrendingUp className="text-blue-600" /> Market Research
        </h1>
        <button onClick={runResearch} disabled={researching}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
          <RefreshCw size={18} className={researching ? 'animate-spin' : ''} />
          {researching ? 'Researching...' : 'Research starten'}
        </button>
      </div>

      {/* Keyword Suggestions */}
      <div className="bg-white rounded-xl shadow-sm border p-6">
        <h3 className="font-semibold mb-3">Amazon Keyword-Suggestions</h3>
        <div className="flex gap-2">
          <input type="text" value={kwInput} onChange={e => setKwInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && searchSuggestions()}
            placeholder="Keyword eingeben..."
            className="flex-1 px-3 py-2 border rounded-lg" />
          <button onClick={searchSuggestions}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <Search size={18} />
          </button>
        </div>
        {suggestions.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {suggestions.map((s, i) => (
              <span key={i} className="text-sm bg-blue-50 text-blue-700 px-3 py-1 rounded-full">{s}</span>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button onClick={() => setTab('trends')}
          className={`px-4 py-2 rounded-lg ${tab === 'trends' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}>
          Trends
        </button>
        <button onClick={() => setTab('items')}
          className={`px-4 py-2 rounded-lg ${tab === 'items' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}>
          Bestseller-Items
        </button>
      </div>

      {tab === 'trends' ? (
        <div className="bg-white rounded-xl shadow-sm border divide-y">
          {trends.map((t, i) => (
            <div key={i} className="flex items-center justify-between p-4">
              <div className="flex items-center gap-3">
                {DIRECTION_ICONS[t.trend_direction] || DIRECTION_ICONS.stable}
                <div>
                  <span className="font-medium">{t.keyword}</span>
                  <span className="text-xs text-gray-400 ml-2">{t.source}</span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="text-sm">
                  <span className="font-medium">{t.interest_score?.toFixed(0)}</span>
                  <span className="text-gray-400 ml-1">Interest</span>
                </div>
                {t.related_keywords?.length > 0 && (
                  <div className="flex gap-1">
                    {t.related_keywords.slice(0, 3).map((r, j) => (
                      <span key={j} className="text-xs bg-gray-100 px-2 py-0.5 rounded">{r}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {trends.length === 0 && (
            <p className="p-8 text-center text-gray-400">Keine Trend-Daten. Starte die Research!</p>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border divide-y">
          {items.map((item, i) => (
            <div key={i} className="flex items-center justify-between p-4">
              <div className="flex-1">
                <span className="font-medium">{item.title}</span>
                <div className="flex gap-3 mt-1 text-xs text-gray-500">
                  <span>{item.source}</span>
                  {item.bsr && <span>BSR: {item.bsr.toLocaleString()}</span>}
                  {item.design_type && <span>{item.design_type}</span>}
                </div>
              </div>
              {item.keywords?.length > 0 && (
                <div className="flex gap-1 ml-4">
                  {item.keywords.slice(0, 4).map((kw, j) => (
                    <span key={j} className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded">{kw}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
          {items.length === 0 && (
            <p className="p-8 text-center text-gray-400">Keine Research-Items. Starte die Research!</p>
          )}
        </div>
      )}
    </div>
  )
}
