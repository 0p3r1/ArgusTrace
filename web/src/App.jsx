import { useEffect, useMemo, useState } from 'react'
import './App.css'
import { BrandMark } from './icons.jsx'
import StatusBadge from './StatusBadge.jsx'

const API_BASE = 'http://127.0.0.1:8000'

function ToolCard({ family, selected, activeVariantKey, onSelectFamily, onSelectVariant }) {
  return (
    <div
      role="button"
      tabIndex={0}
      className={`tool-card${selected ? ' selected' : ''}`}
      onClick={() => onSelectFamily(family.family)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelectFamily(family.family)
        }
      }}
    >
      <div className="tool-card-head">
        <span className="tool-label">{family.label}</span>
        <span className="tool-entity">{family.entity_type}</span>
      </div>
      <p className="tool-description">{family.description}</p>

      {family.variants.length > 1 ? (
        <select
          className="variant-select"
          value={activeVariantKey}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => onSelectVariant(family.family, e.target.value)}
        >
          {family.variants.map((v) => (
            <option key={v.key} value={v.key}>
              {v.variant_label} — {v.speed}
            </option>
          ))}
        </select>
      ) : (
        <span className="tool-speed">{family.variants[0].speed}</span>
      )}
    </div>
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
  const [families, setFamilies] = useState([])
  const [entityFilter, setEntityFilter] = useState(null)
  const [selectedFamily, setSelectedFamily] = useState(null)
  const [variantByFamily, setVariantByFamily] = useState({})
  const [entity, setEntity] = useState('')
  const [findings, setFindings] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState(null)

  useEffect(() => {
    fetch(`${API_BASE}/api/plugins`)
      .then((res) => res.json())
      .then((data) => {
        setFamilies(data)
        if (data.length > 0) {
          setSelectedFamily(data[0].family)
          setVariantByFamily(Object.fromEntries(data.map((f) => [f.family, f.variants[0].key])))
        }
      })
      .catch(() => setError('Could not reach the ArgusTrace API. Is it running?'))
  }, [])

  const entityTypes = useMemo(() => {
    const seen = []
    for (const f of families) {
      if (f.entity_type !== 'any' && !seen.includes(f.entity_type)) seen.push(f.entity_type)
    }
    return seen
  }, [families])

  const visibleFamilies = useMemo(
    () => families.filter((f) => !entityFilter || f.entity_type === 'any' || f.entity_type === entityFilter),
    [families, entityFilter],
  )

  function handleEntityFilterChange(type) {
    setEntityFilter(type)
    const stillVisible = families.some(
      (f) => f.family === selectedFamily && (!type || f.entity_type === 'any' || f.entity_type === type),
    )
    if (!stillVisible) {
      const nextVisible = families.filter((f) => !type || f.entity_type === 'any' || f.entity_type === type)
      if (nextVisible.length > 0) setSelectedFamily(nextVisible[0].family)
    }
  }

  function handleSelectVariant(family, variantKey) {
    setSelectedFamily(family)
    setVariantByFamily((prev) => ({ ...prev, [family]: variantKey }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setFindings(null)
    setStatusFilter(null)
    const plugin = variantByFamily[selectedFamily]
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

          <div className="entity-filter">
            <button
              type="button"
              className={`filter-chip${!entityFilter ? ' active' : ''}`}
              onClick={() => handleEntityFilterChange(null)}
            >
              All
            </button>
            {entityTypes.map((type) => (
              <button
                key={type}
                type="button"
                className={`filter-chip${entityFilter === type ? ' active' : ''}`}
                onClick={() => handleEntityFilterChange(type)}
              >
                {type}
              </button>
            ))}
          </div>

          <div className="tool-grid">
            {visibleFamilies.map((family) => (
              <ToolCard
                key={family.family}
                family={family}
                selected={selectedFamily === family.family}
                activeVariantKey={variantByFamily[family.family]}
                onSelectFamily={setSelectedFamily}
                onSelectVariant={handleSelectVariant}
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
                      {f.url ? (
                        <a href={f.url} target="_blank" rel="noreferrer">{f.url}</a>
                      ) : f.evidence?.reason ? (
                        <span className="muted">{f.evidence.reason}</span>
                      ) : (
                        <span className="muted">—</span>
                      )}
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
