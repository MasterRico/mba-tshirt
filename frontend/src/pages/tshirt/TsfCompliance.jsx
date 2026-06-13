import { useState } from 'react'
import { api } from '../../services/api'
import { Shield, AlertTriangle, CheckCircle, Search } from 'lucide-react'

export default function TsfCompliance() {
  const [input, setInput] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)

  async function checkTerms() {
    if (!input.trim()) return
    setLoading(true)
    try {
      const terms = input.split('\n').map(t => t.trim()).filter(Boolean)
      const data = await api.tsf.checkTrademarks(terms)
      setResults(data)
    } catch (err) {
      console.error('Check failed:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <Shield className="text-orange-600" /> Trademark-Check
      </h1>
      <p className="text-gray-500">
        Prüfe Wörter und Phrasen gegen die USPTO-Datenbank und bekannte Marken.
        Ein Wort pro Zeile eingeben.
      </p>

      <div className="bg-white rounded-xl shadow-sm border p-6">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          placeholder={"Disney\nBest Dad Ever\nCoffee Addict\nNike\n..."}
          rows={8}
          className="w-full px-4 py-3 border rounded-lg font-mono text-sm resize-y"
        />
        <button
          onClick={checkTerms}
          disabled={loading || !input.trim()}
          className="mt-4 flex items-center gap-2 px-6 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700 disabled:opacity-50"
        >
          <Search size={18} />
          {loading ? 'Prüfe...' : 'Trademark-Check starten'}
        </button>
      </div>

      {results.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold mb-4">Ergebnisse ({results.length} Begriffe)</h2>
          <div className="space-y-2">
            {results.map((r, i) => (
              <div key={i} className={`flex items-center justify-between p-3 rounded-lg ${
                r.is_trademarked ? 'bg-red-50 border border-red-200' : 'bg-green-50 border border-green-200'
              }`}>
                <div className="flex items-center gap-3">
                  {r.is_trademarked ? (
                    <AlertTriangle size={20} className="text-red-500" />
                  ) : (
                    <CheckCircle size={20} className="text-green-500" />
                  )}
                  <span className="font-medium">{r.term}</span>
                </div>
                <div className="text-sm">
                  {r.is_trademarked ? (
                    <span className="text-red-600">
                      GESCHÜTZT {r.trademark_owner ? `— ${r.trademark_owner}` : ''}
                    </span>
                  ) : (
                    <span className="text-green-600">Frei verwendbar</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
