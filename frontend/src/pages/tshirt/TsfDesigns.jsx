import { useState, useEffect } from 'react'
import { api } from '../../services/api'
import LoadingSpinner from '../../components/LoadingSpinner'
import {
  Shirt, Plus, CheckCircle, AlertTriangle, Upload, RotateCcw,
  Eye, Copy, Sparkles
} from 'lucide-react'

const STATUS_LABELS = {
  draft: { label: 'Entwurf', color: 'bg-gray-100 text-gray-700' },
  compliance_check: { label: 'Compliance', color: 'bg-yellow-100 text-yellow-700' },
  approved: { label: 'Freigegeben', color: 'bg-green-100 text-green-700' },
  uploaded: { label: 'Hochgeladen', color: 'bg-blue-100 text-blue-700' },
  live: { label: 'Live', color: 'bg-emerald-100 text-emerald-700' },
  underperforming: { label: 'Underperformer', color: 'bg-orange-100 text-orange-700' },
  rotated_out: { label: 'Rotiert', color: 'bg-red-100 text-red-700' },
}

export default function TsfDesigns() {
  const [designs, setDesigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [generating, setGenerating] = useState(false)
  const [genParams, setGenParams] = useState({ count: 5, niche_name: '', seasonal_event: '' })
  const [showGenerate, setShowGenerate] = useState(false)
  const [selectedDesign, setSelectedDesign] = useState(null)

  useEffect(() => { loadDesigns() }, [filter])

  async function loadDesigns() {
    try {
      const result = await api.tsf.getDesigns(filter || undefined)
      setDesigns(result)
    } catch (err) {
      console.error('Failed to load designs:', err)
    } finally {
      setLoading(false)
    }
  }

  async function generateDesigns() {
    setGenerating(true)
    try {
      await api.tsf.generateDesigns(genParams)
      await loadDesigns()
      setShowGenerate(false)
    } catch (err) {
      console.error('Generation failed:', err)
    } finally {
      setGenerating(false)
    }
  }

  async function markUploaded(id) {
    const asin = prompt('ASIN eingeben (optional):')
    try {
      await api.tsf.markUploaded(id, asin || undefined)
      await loadDesigns()
    } catch (err) {
      console.error('Upload marking failed:', err)
    }
  }

  async function rotateDesign(id) {
    if (!confirm('Design wirklich rotieren?')) return
    try {
      await api.tsf.rotateDesign(id)
      await loadDesigns()
    } catch (err) {
      console.error('Rotation failed:', err)
    }
  }

  function copyPrompt(design) {
    navigator.clipboard.writeText(design.prompt_text)
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Shirt className="text-purple-600" /> Design Prompts
        </h1>
        <button
          onClick={() => setShowGenerate(!showGenerate)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
        >
          <Sparkles size={18} /> Designs generieren
        </button>
      </div>

      {/* Generate Panel */}
      {showGenerate && (
        <div className="bg-purple-50 rounded-xl p-6 border border-purple-200">
          <h3 className="font-semibold mb-4">Neue Designs generieren</h3>
          <div className="grid md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Anzahl</label>
              <input type="number" min="1" max="20" value={genParams.count}
                onChange={e => setGenParams({...genParams, count: parseInt(e.target.value)})}
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Nische (optional)</label>
              <input type="text" value={genParams.niche_name}
                onChange={e => setGenParams({...genParams, niche_name: e.target.value})}
                placeholder="z.B. dad_jokes"
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Saison-Event (optional)</label>
              <input type="text" value={genParams.seasonal_event}
                onChange={e => setGenParams({...genParams, seasonal_event: e.target.value})}
                placeholder="z.B. christmas"
                className="w-full px-3 py-2 border rounded-lg"
              />
            </div>
            <div className="flex items-end">
              <button onClick={generateDesigns} disabled={generating}
                className="w-full px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {generating ? 'Generiere...' : 'Generieren'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filter */}
      <div className="flex gap-2 flex-wrap">
        {['', 'approved', 'uploaded', 'live', 'underperforming', 'draft'].map(s => (
          <button key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 rounded-full text-sm ${
              filter === s ? 'bg-purple-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {s ? (STATUS_LABELS[s]?.label || s) : 'Alle'}
          </button>
        ))}
      </div>

      {/* Design List */}
      <div className="space-y-4">
        {designs.map(design => (
          <div key={design.id} className="bg-white rounded-xl shadow-sm border p-5">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3 mb-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    STATUS_LABELS[design.status]?.color || 'bg-gray-100'
                  }`}>
                    {STATUS_LABELS[design.status]?.label || design.status}
                  </span>
                  <span className="text-xs text-gray-500">{design.design_type}</span>
                  {design.trademark_cleared && (
                    <span className="text-xs text-green-600 flex items-center gap-1">
                      <CheckCircle size={12} /> TM-frei
                    </span>
                  )}
                  <span className="text-xs text-purple-600 font-medium">
                    Score: {(design.composite_score * 100).toFixed(0)}%
                  </span>
                </div>
                <h3 className="text-lg font-bold text-gray-900">
                  "{design.primary_text}"
                </h3>
                {design.sub_text && (
                  <p className="text-gray-500 text-sm mt-1">{design.sub_text}</p>
                )}
                <div className="mt-2 text-sm text-gray-600">
                  <span className="font-medium">Zielgruppe:</span> {design.target_audience || '—'}
                  {design.seasonal_event && (
                    <span className="ml-3"><span className="font-medium">Event:</span> {design.seasonal_event}</span>
                  )}
                </div>
              </div>
              <div className="flex gap-2 ml-4">
                <button onClick={() => setSelectedDesign(selectedDesign?.id === design.id ? null : design)}
                  className="p-2 hover:bg-gray-100 rounded-lg" title="Details">
                  <Eye size={18} />
                </button>
                <button onClick={() => copyPrompt(design)}
                  className="p-2 hover:bg-gray-100 rounded-lg" title="Prompt kopieren">
                  <Copy size={18} />
                </button>
                {design.status === 'approved' && (
                  <button onClick={() => markUploaded(design.id)}
                    className="p-2 hover:bg-blue-100 rounded-lg text-blue-600" title="Als hochgeladen markieren">
                    <Upload size={18} />
                  </button>
                )}
                {(design.status === 'live' || design.status === 'underperforming') && (
                  <button onClick={() => rotateDesign(design.id)}
                    className="p-2 hover:bg-red-100 rounded-lg text-red-600" title="Rotieren">
                    <RotateCcw size={18} />
                  </button>
                )}
              </div>
            </div>

            {/* Expanded Details */}
            {selectedDesign?.id === design.id && (
              <div className="mt-4 pt-4 border-t space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-gray-500 mb-1">Design Prompt</h4>
                  <p className="text-sm bg-gray-50 p-3 rounded-lg whitespace-pre-wrap">{design.prompt_text}</p>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-500 mb-1">Listing Title</h4>
                    <p className="text-sm bg-gray-50 p-3 rounded-lg">{design.listing_title || '—'}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-gray-500 mb-1">Keywords</h4>
                    <div className="flex flex-wrap gap-1">
                      {(design.listing_keywords || []).map((kw, i) => (
                        <span key={i} className="text-xs bg-purple-50 text-purple-700 px-2 py-1 rounded">{kw}</span>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-sm font-semibold text-gray-500 mb-1">Bullet 1</h4>
                    <p className="text-sm bg-gray-50 p-3 rounded-lg">{design.listing_bullet1 || '—'}</p>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-gray-500 mb-1">Bullet 2</h4>
                    <p className="text-sm bg-gray-50 p-3 rounded-lg">{design.listing_bullet2 || '—'}</p>
                  </div>
                </div>
                {design.color_scheme && (
                  <div>
                    <h4 className="text-sm font-semibold text-gray-500 mb-1">Farbschema</h4>
                    <div className="flex gap-2">
                      {design.color_scheme.map((c, i) => (
                        <div key={i} className="flex items-center gap-1">
                          <div className="w-6 h-6 rounded border" style={{backgroundColor: c}} />
                          <span className="text-xs text-gray-500">{c}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
        {designs.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            Keine Designs gefunden. Generiere deine ersten Designs!
          </div>
        )}
      </div>
    </div>
  )
}
