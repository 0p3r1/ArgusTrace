import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AdvancedOptionsPanel from './AdvancedOptionsPanel.jsx'
import './App.css'
import { API_BASE } from './api.js'
import StatusBadge from './StatusBadge.jsx'
import ToolBrowser from './ToolBrowser.jsx'
import { useToolFamilies } from './useToolFamilies.js'
import { useVersionCheck } from './useVersionCheck.js'
import VersionBadge from './VersionBadge.jsx'

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

function SelectedToolPanel({ family, variantKey, onSelectVariant, onCheckVersion, checkingVersion }) {
  if (!family) return null

  return (
    <div className="selected-tool-panel">
      <div className="selected-tool-head">
        <span className="field-label">Selected tool</span>
        <span className="selected-tool-label">{family.label}</span>
        <VersionBadge
          version={family.version}
          onCheck={family.version.status !== 'not_applicable' ? onCheckVersion : undefined}
          checking={checkingVersion}
        />
      </div>

      {family.variants.length > 1 && (
        <select
          className="variant-select"
          value={variantKey}
          onChange={(e) => onSelectVariant(e.target.value)}
        >
          {family.variants.map((v) => (
            <option key={v.key} value={v.key}>
              {v.variant_label} — {v.speed}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}

function InvestigatePage() {
  const { families, error: familiesError, setFamilies } = useToolFamilies()
  const { checkVersion, checkingFamily } = useVersionCheck(setFamilies)
  const [entityFilter, setEntityFilter] = useState(null)
  const [selectedFamily, setSelectedFamily] = useState(null)
  const [variantByFamily, setVariantByFamily] = useState({})
  const [optionsByFamily, setOptionsByFamily] = useState({})
  const [entity, setEntity] = useState('')
  const [findings, setFindings] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [statusFilter, setStatusFilter] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()

  useEffect(() => {
    if (families.length === 0 || selectedFamily) return
    setVariantByFamily(Object.fromEntries(families.map((f) => [f.family, f.variants[0].key])))

    // Handed off from a tool's info page ("Use this tool")?
    const requestedFamily = searchParams.get('family')
    const requestedVariant = searchParams.get('variant')
    const match = families.find((f) => f.family === requestedFamily)
    if (match) {
      setSelectedFamily(match.family)
      if (requestedVariant && match.variants.some((v) => v.key === requestedVariant)) {
        setVariantByFamily((prev) => ({ ...prev, [match.family]: requestedVariant }))
      }
      setSearchParams({}, { replace: true })
    } else {
      setSelectedFamily(families[0].family)
    }
  }, [families, selectedFamily, searchParams, setSearchParams])

  const entityTypes = useMemo(() => {
    const seen = []
    for (const f of families) {
      if (f.entity_type !== 'any' && !seen.includes(f.entity_type)) seen.push(f.entity_type)
    }
    return seen
  }, [families])

  const selectedFamilyData = families.find((f) => f.family === selectedFamily) ?? null

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

  function handleSelectVariant(variantKey) {
    setVariantByFamily((prev) => ({ ...prev, [selectedFamily]: variantKey }))
  }

  function handleOptionChange(name, value) {
    setOptionsByFamily((prev) => ({
      ...prev,
      [selectedFamily]: { ...prev[selectedFamily], [name]: value },
    }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    setFindings(null)
    setStatusFilter(null)
    const plugin = variantByFamily[selectedFamily]
    const rawOptions = optionsByFamily[selectedFamily] || {}
    const options = Object.fromEntries(Object.entries(rawOptions).filter(([, v]) => v !== undefined))
    try {
      const res = await fetch(`${API_BASE}/api/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity,
          plugin,
          options: Object.keys(options).length > 0 ? options : undefined,
        }),
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

        <ToolBrowser
          families={families}
          selectedFamily={selectedFamily}
          onSelectFamily={setSelectedFamily}
          entityFilter={entityFilter}
          onEntityFilterChange={handleEntityFilterChange}
          entityTypes={entityTypes}
        />

        <SelectedToolPanel
          family={selectedFamilyData}
          variantKey={variantByFamily[selectedFamily]}
          onSelectVariant={handleSelectVariant}
          onCheckVersion={() => checkVersion(selectedFamily)}
          checkingVersion={checkingFamily === selectedFamily}
        />

        <AdvancedOptionsPanel
          family={selectedFamilyData}
          values={optionsByFamily[selectedFamily] || {}}
          onChange={handleOptionChange}
        />

        <button type="submit" className="submit-button" disabled={loading}>
          {loading ? 'Investigating…' : 'Investigate'}
        </button>
      </form>

      {(error || familiesError) && <p className="error-message">{error || familiesError}</p>}

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
  )
}

export default InvestigatePage
