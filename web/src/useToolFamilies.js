import { useEffect, useState } from 'react'
import { API_BASE, apiFetch } from './api.js'

export function useToolFamilies() {
  const [families, setFamilies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch(`${API_BASE}/api/plugins`)
      .then((res) => res.json())
      .then((data) => setFamilies(data))
      .catch(() => setError('Could not reach the ArgusTrace API. Is it running?'))
      .finally(() => setLoading(false))
  }, [])

  return { families, loading, error, setFamilies }
}
