import { useEffect, useState } from 'react'
import './App.css'

const API_BASE = 'http://127.0.0.1:8000'

const STATUS_LABEL = {
  FOUND: 'Found',
  NOT_FOUND: 'Not found',
  ERROR: 'Error',
}

function App() {
  const [plugins, setPlugins] = useState([])
  const [plugin, setPlugin] = useState('mock')
  const [entity, setEntity] = useState('')
  const [findings, setFindings] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/plugins`)
      .then((res) => res.json())
      .then((names) => {
        setPlugins(names)
        if (names.length > 0) setPlugin(names[0])
      })
      .catch(() => setError('Could not reach the ArgusTrace API. Is it running?'))
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setFindings(null)
    try {
      const res = await fetch(`${API_BASE}/api/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity, plugin }),
      })
      if (!res.ok) {
        throw new Error(`API returned ${res.status}`)
      }
      setFindings(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <h1>ArgusTrace</h1>

      <form onSubmit={handleSubmit} className="investigate-form">
        <input
          type="text"
          placeholder="username, email, or phone"
          value={entity}
          onChange={(e) => setEntity(e.target.value)}
          required
        />
        <select value={plugin} onChange={(e) => setPlugin(e.target.value)}>
          {plugins.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
        </select>
        <button type="submit" disabled={loading}>
          {loading ? 'Running...' : 'Investigate'}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {findings && (
        <table className="findings">
          <thead>
            <tr>
              <th>Source</th>
              <th>Status</th>
              <th>URL</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((f, i) => (
              <tr key={i} className={`status-${f.status.toLowerCase()}`}>
                <td>{f.source}</td>
                <td>{STATUS_LABEL[f.status]}</td>
                <td>{f.url ? <a href={f.url} target="_blank" rel="noreferrer">{f.url}</a> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default App
