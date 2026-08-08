import { useCallback, useEffect, useState } from 'react'
import { API_BASE, apiFetch } from './api.js'

// Long enough for a cold backend, short enough that a hung server surfaces
// as an error instead of a spinner that never resolves.
const CATALOG_TIMEOUT_MS = 15000

export function useToolFamilies() {
  const [families, setFamilies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [reloadToken, setReloadToken] = useState(0)

  const reload = useCallback(() => setReloadToken((n) => n + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), CATALOG_TIMEOUT_MS)
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const res = await apiFetch(`${API_BASE}/api/plugins`, { signal: controller.signal })
        // Without this, an error body parses fine as JSON and lands in
        // `families` as a non-array, and the first `.find()` on it throws —
        // which white-screened the whole app.
        if (!res.ok) throw new Error(`API returned ${res.status}`)
        const data = await res.json()
        if (!Array.isArray(data)) throw new Error('unexpected response from /api/plugins')
        if (!cancelled) setFamilies(data)
      } catch (err) {
        if (cancelled || err.name === 'AbortError') {
          if (!cancelled) setError('The ArgusTrace API did not respond in time.')
          return
        }
        setError('Could not reach the ArgusTrace API. Is it running?')
      } finally {
        clearTimeout(timer)
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => {
      cancelled = true
      clearTimeout(timer)
      controller.abort()
    }
  }, [reloadToken])

  return { families, loading, error, setFamilies, reload }
}
