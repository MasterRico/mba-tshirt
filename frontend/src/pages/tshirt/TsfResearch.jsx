import { useState, useEffect } from 'react'
import { api } from '../../services/api'
import LoadingSpinner from '../../components/LoadingSpinner'
import { TrendingUp, Search } from 'lucide-react'

export default function TsfResearch() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [kwInput, setKwInput] = useState('')
  const [suggestions, setSuggestions] = useState([])

  useEffect(() => {
    loadItems()
  }, [])

  async function loadItems() {
    setLoading(true)
    try {
      setItems(await api.tsf.getResearchItems())
    } catch (err) { console.error(err) }
    finally { setLoading(false) }
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
          <TrendingUp className="text-blue-600" /> Research
        </h1>
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

      {/* Eingelesene Winner (Vision-Ingest) */}
      <div>
        <h3 className="font-semibold mb-3">Eingelesene Winner (BSR-gewichtet)</h3>
        <div className="bg-white rounded-xl shadow-sm border divide-y">
          {items.map((item, i) => (
            <div key={i} className="flex items-center justify-between p-4">
              <div className="flex-1 min-w-0">
                <span className="font-medium">{item.title}</span>
                <div className="flex gap-3 mt-1 text-xs text-gray-500">
                  <span>{item.niche || item.source}</span>
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
            <p className="p-8 text-center text-gray-400">Noch keine eingelesenen Winner.</p>
          )}
        </div>
      </div>
    </div>
  )
}
