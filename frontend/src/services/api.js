import { getStoredToken, clearStoredToken } from '../components/TokenGate'

const API_BASE = '/api/v1'

async function request(path, options = {}) {
  const token = getStoredToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers.Authorization = `Bearer ${token}`

  const resp = await fetch(`${API_BASE}${path}`, { headers, ...options })
  if (resp.status === 401) {
    clearStoredToken()
    window.location.reload()
    throw new Error('Authentication required')
  }
  if (!resp.ok) {
    const error = await resp.json().catch(() => ({ detail: resp.statusText }))
    throw new Error(error.detail || 'API request failed')
  }
  return resp.json()
}

export const api = {
  // ─── T-Shirt Factory ─────────────────────────────────────────
  tsf: {
    getDashboard: () => request('/tsf/dashboard'),
    runFullPipeline: () => request('/tsf/pipeline/full', { method: 'POST' }),
    runResearch: () => request('/tsf/pipeline/research', { method: 'POST' }),
    runAnalysis: () => request('/tsf/pipeline/analysis', { method: 'POST' }),

    // Designs
    generateDesigns: (params) => request('/tsf/designs/generate', { method: 'POST', body: JSON.stringify(params) }),
    getDesigns: (status, limit = 50) => request(`/tsf/designs?limit=${limit}${status ? `&status=${status}` : ''}`),
    getDesign: (id) => request(`/tsf/designs/${id}`),
    markUploaded: (id, asin) => request(`/tsf/designs/${id}/upload${asin ? `?asin=${asin}` : ''}`, { method: 'POST' }),
    rotateDesign: (id) => request(`/tsf/designs/${id}/rotate`, { method: 'POST' }),

    // Niches
    getNiches: () => request('/tsf/niches'),
    createNiche: (data) => request('/tsf/niches', { method: 'POST', body: JSON.stringify(data) }),
    initializeNiches: () => request('/tsf/niches/initialize', { method: 'POST' }),
    analyzeNiche: (id) => request(`/tsf/niches/${id}/analysis`),

    // Slots
    getSlotSummary: () => request('/tsf/slots/summary'),
    getSlotRecommendations: () => request('/tsf/slots/recommendations'),
    getRotationCandidates: () => request('/tsf/slots/rotation-candidates'),

    // Performance
    updatePerformance: (data) => request('/tsf/performance/update', { method: 'POST', body: JSON.stringify(data) }),
    importCsv: (csvData) => request('/tsf/performance/import-csv', { method: 'POST', body: JSON.stringify({ csv_data: csvData }) }),
    getPerformanceSummary: () => request('/tsf/performance/summary'),
    getNichePerformance: () => request('/tsf/performance/by-niche'),

    // MBA Account Sales (echte Konto-Zahlen, design-unabhaengig)
    getSalesSummary: () => request('/tsf/sales/summary'),
    importSales: (csvData) => request('/tsf/sales/import', { method: 'POST', body: JSON.stringify({ csv_data: csvData }) }),

    // Winner-Maschine: Kandidaten-Ranking + Saison-Planer
    getCandidates: (niche, limit = 20) => request(`/tsf/curation/candidates?limit=${limit}${niche ? `&niche=${encodeURIComponent(niche)}` : ''}`),
    getSeasonalPlanner: () => request('/tsf/planner/seasonal'),
    getGaps: (niche, limit = 12) => request(`/tsf/curation/gaps?limit=${limit}${niche ? `&niche=${encodeURIComponent(niche)}` : ''}`),
    generateImage: (id) => request(`/tsf/designs/${id}/generate-image`, { method: 'POST' }),

    // Compliance
    checkTrademarks: (terms) => request('/tsf/compliance/check', { method: 'POST', body: JSON.stringify({ terms }) }),

    // Research
    getResearchItems: (source, limit = 50) => request(`/tsf/research/items?limit=${limit}${source ? `&source=${source}` : ''}`),
    getTrends: (direction) => request(`/tsf/research/trends${direction ? `?direction=${direction}` : ''}`),

    // Learning
    getInsights: (category) => request(`/tsf/learning/insights${category ? `?category=${category}` : ''}`),
    getLearningSummary: () => request('/tsf/learning/summary'),
    runLearning: () => request('/tsf/learning/run', { method: 'POST' }),
    getGuidance: (niche) => request(`/tsf/learning/guidance${niche ? `?niche=${niche}` : ''}`),

    // Keywords
    researchKeywords: (niche) => request(`/tsf/keywords/research/${niche}`),
    getSuggestions: (keyword) => request(`/tsf/keywords/suggestions?keyword=${encodeURIComponent(keyword)}`),
  },
}
