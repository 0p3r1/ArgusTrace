import { useState } from 'react'
import { API_BASE, apiFetch } from './api.js'

// A version check is three upstream HTTP calls behind our own API; past this
// it is not coming back.
const VERSION_CHECK_TIMEOUT_MS = 20000

export function useVersionCheck(setFamilies) {
  const [checkingFamily, setCheckingFamily] = useState(null)
  const [error, setError] = useState(null)

  async function checkVersion(family) {
    setCheckingFamily(family)
    setError(null)
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), VERSION_CHECK_TIMEOUT_MS)
    try {
      const res = await apiFetch(`${API_BASE}/api/tools/${family}/version-check`, {
        method: 'POST',
        signal: controller.signal,
      })
      // Previously this had a `finally` but no `catch`: a failure became an
      // unhandled rejection, and an error body was written into the family's
      // `version` as though it were a real result.
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const version = await res.json()
      setFamilies((prev) => prev.map((f) => (f.family === family ? { ...f, version } : f)))
    } catch (err) {
      setError(err.name === 'AbortError' ? 'Version check timed out.' : 'Version check failed.')
    } finally {
      clearTimeout(timer)
      setCheckingFamily(null)
    }
  }

  return { checkVersion, checkingFamily, error }
}
