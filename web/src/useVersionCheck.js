import { useState } from 'react'
import { API_BASE } from './api.js'

export function useVersionCheck(setFamilies) {
  const [checkingFamily, setCheckingFamily] = useState(null)

  async function checkVersion(family) {
    setCheckingFamily(family)
    try {
      const res = await fetch(`${API_BASE}/api/tools/${family}/version-check`, { method: 'POST' })
      const version = await res.json()
      setFamilies((prev) => prev.map((f) => (f.family === family ? { ...f, version } : f)))
    } finally {
      setCheckingFamily(null)
    }
  }

  return { checkVersion, checkingFamily }
}
