import { useEffect, useState } from 'react'
import { API_BASE } from './api.js'

export function useToolFamilies() {
  const [families, setFamilies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/plugins`)
      .then((res) => res.json())
      .then((data) => setFamilies(data))
      .catch(() => setError('Could not reach the ArgusTrace API. Is it running?'))
      .finally(() => setLoading(false))
  }, [])

  return { families, loading, error, setFamilies }
}
