import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { BrandMark } from './icons.jsx'
import StatusBadge from './StatusBadge.jsx'

const API_BASE = 'http://127.0.0.1:8000'

function ToolCard({ tool, selected, onSelect }) {
  return (
    <button
      type="button"
      className={`tool-card${selected ? ' selected' : ''}`}
      onClick={() => onSelect(tool.key)}
    >
      <div className="tool-card-head">
        <span className="tool-label">{tool.label}</span>
        <span className="tool-speed">{tool.speed}</span>
      </div>
      <p className="tool-description">{tool.description}</p>
      <span className="tool-entity">{tool.entity_type}</span>
    </button>
  )
}

const STATUS_FILTERS = [
  { status: 'FOUND', label: 'found' },
  { status: 'NOT_FOUND', label: 'not found' },
  { status: 'ERROR', label: 'error' },
]

function ResultsSummary({ findings, activeFilter, onToggleFilter }) {
  const counts = useMemo(() => {
    const c = { FOUND: 0, NOT_FOUND: 0, ERROR: 0 }
    for (const f of findings) c[f.status]++
    return c
  }, [findings])

  return (
    <div className="results-summary">
      {STATUS_FILTERS.map(({ status, label }) => (
        <button
          key={status}
          type="button"
          className={`summary-pill status-${status.toLowerCase()}${activeFilter === status ? ' active' : ''}`}
          onClick={() => onToggleFilter(status)}
        >
          {counts[status]} {label}
        </button>
      ))}
      {activeFilter && (
        <button type="button" className="summary-pill clear-filter" onClick={() => onToggleFilter(null)}>
          Clear filter
        </button>
      )}
    </div>
  )
}

function App() {
  const [tools, setTools] = useState([])
  const [plugin, setPlugin] = useState('mock')
  const [entity, setEntity] = useState('')
  const [findings, setFindings] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/plugins`)
      .then((res) => res.json())
      .then((data) => {
        setTools(data)
        if (data.length > 0) setPlugin(data[0].key)
      })
      .catch(() => setError('Could not reach the ArgusTrace API. Is it running?'))
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setFindings(null)
    setStatusFilter(null)
    try {
      const res = await fetch(`${API_BASE}/api/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entity, plugin }),
      })
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      setFindings(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <header className="site-header">
        <div className="brand">
          <BrandMark />
          <h1>ArgusTrace</h1>
        </div>
        <p className="tagline">Modular OSINT investigation, one entity at a time.</p>
      </header>

      <main>
        <form className="investigate-panel" onSubmit={handleSubmit}>
          <label htmlFor="entity-input" className="field-label">Entity to investigate</label>
          <input
            id="entity-input"
            type="text"
            placeholder="username, email, or phone number"
            value={entity}
            onChange={(e) => setEntity(e.target.value)}
            required
          />

          <div className="tool-grid">
            {tools.map((tool) => (
              <ToolCard
                key={tool.key}
                tool={tool}
                selected={plugin === tool.key}
                onSelect={setPlugin}
              />
            ))}
          </div>

          <button type="submit" className="submit-button" disabled={loading}>
            {loading ? 'Investigating…' : 'Investigate'}
          </button>
        </form>

        {error && <p className="error-message">{error}</p>}

        {findings && (
          <section className="results">
            <ResultsSummary
              findings={findings}
              activeFilter={statusFilter}
              onToggleFilter={(status) => setStatusFilter((prev) => (prev === status ? null : status))}
            />
            <table className="findings-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Status</th>
                  <th>URL</th>
                </tr>
              </thead>
              <tbody>
                {findings
                  .filter((f) => !statusFilter || f.status === statusFilter)
                  .map((f, i) => (
                  <tr key={i}>
                    <td>{f.source}</td>
                    <td><StatusBadge status={f.status} /></td>
                    <td>
                      {f.url
                        ? <a href={f.url} target="_blank" rel="noreferrer">{f.url}</a>
                        : <span className="muted">—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
