import { useState } from 'react'

const STORAGE_KEY = 'kdp_api_token'

export function getStoredToken() {
  return localStorage.getItem(STORAGE_KEY) || ''
}

export function clearStoredToken() {
  localStorage.removeItem(STORAGE_KEY)
}

export default function TokenGate({ children }) {
  const [hasToken, setHasToken] = useState(!!getStoredToken())
  const [input, setInput] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (hasToken) return children

  const submit = async (e) => {
    e.preventDefault()
    const token = input.trim()
    if (!token) return
    setBusy(true)
    setError('')
    try {
      const resp = await fetch('/api/v1/dashboard/stats', {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (resp.status === 401) {
        setError('Token ungültig')
        return
      }
      if (!resp.ok && resp.status !== 503) {
        setError(`Server-Fehler (${resp.status})`)
        return
      }
      localStorage.setItem(STORAGE_KEY, token)
      setHasToken(true)
    } catch (e) {
      setError('Verbindung fehlgeschlagen')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-kdp-900">
      <form onSubmit={submit} className="bg-white p-8 rounded-lg shadow-xl max-w-md w-full">
        <h1 className="text-2xl font-bold mb-2">ooopppmmm Tools</h1>
        <p className="text-sm text-gray-600 mb-6">Bitte API-Token eingeben.</p>
        <input
          type="password"
          autoFocus
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="w-full border border-gray-300 rounded px-3 py-2 mb-3 font-mono text-sm focus:border-kdp-600 focus:ring-1 focus:ring-kdp-600 outline-none"
          placeholder="Bearer-Token"
          disabled={busy}
        />
        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="w-full bg-kdp-700 text-white py-2 rounded hover:bg-kdp-600 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy ? 'Prüfe...' : 'Anmelden'}
        </button>
      </form>
    </div>
  )
}
