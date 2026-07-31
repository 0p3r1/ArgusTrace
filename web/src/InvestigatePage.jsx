import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import './App.css'
import { API_BASE } from './api.js'
import ResultsPanel from './ResultsPanel.jsx'
import ResultsTray from './ResultsTray.jsx'
import RunDrawer from './RunDrawer.jsx'
import ToolBrowser from './ToolBrowser.jsx'
import { useToolFamilies } from './useToolFamilies.js'
import { useVersionCheck } from './useVersionCheck.js'
import { fastVariant, slowVariant } from './variants.js'

let nextResultId = 1

function InvestigatePage() {
  const { families, error: familiesError, setFamilies } = useToolFamilies()
  const { checkVersion, checkingFamily } = useVersionCheck(setFamilies)
  const [entityFilter, setEntityFilter] = useState(null)
  const [openFamily, setOpenFamily] = useState(null)
  const [fastModeByFamily, setFastModeByFamily] = useState({})
  const [optionsByFamily, setOptionsByFamily] = useState({})
  const [entity, setEntity] = useState('')
  const [loading, setLoading] = useState(false)
  const [runResults, setRunResults] = useState([])
  const [activeResultId, setActiveResultId] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()

  const entityTypes = useMemo(() => {
    const seen = []
    for (const f of families) {
      if (f.hidden || f.entity_type === 'any') continue
      if (!seen.includes(f.entity_type)) seen.push(f.entity_type)
    }
    return seen
  }, [families])

  const openFamilyData = families.find((f) => f.family === openFamily) ?? null
  const activeResult = runResults.find((r) => r.id === activeResultId) ?? null
  const trayResults = runResults.filter((r) => r.id !== activeResultId)

  function openTool(familyKey, opts = {}) {
    const family = families.find((f) => f.family === familyKey)
    if (!family) return
    setOpenFamily(familyKey)
    setEntity('')
    setFastModeByFamily((prev) => ({ ...prev, [familyKey]: opts.fastMode ?? prev[familyKey] ?? true }))
  }

  // Handed off from a tool's info page ("Use this tool")?
  useEffect(() => {
    if (families.length === 0) return
    const requestedFamily = searchParams.get('family')
    const requestedFastMode = searchParams.get('fastMode')
    const match = families.find((f) => f.family === requestedFamily)
    if (match) {
      openTool(match.family, { fastMode: requestedFastMode === null ? undefined : requestedFastMode === 'true' })
      setSearchParams({}, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [families])

  function closeDrawer() {
    setOpenFamily(null)
  }

  function handleOptionChange(name, value) {
    setOptionsByFamily((prev) => ({
      ...prev,
      [openFamily]: { ...prev[openFamily], [name]: value },
    }))
  }

  function updateActiveResult(patch) {
    setRunResults((prev) => prev.map((r) => (r.id === activeResultId ? { ...r, ...patch } : r)))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)

    const family = openFamilyData
    const investigatedEntity = entity
    const fastMode = fastModeByFamily[openFamily]
    const hasVariantChoice = family.variants.length > 1
    const plugin = hasVariantChoice
      ? (fastMode ? fastVariant(family) : slowVariant(family)).key
      : family.variants[0].key
    const rawOptions = fastMode ? {} : optionsByFamily[openFamily] || {}
    const options = Object.fromEntries(Object.entries(rawOptions).filter(([, v]) => v !== undefined))

    const id = nextResultId++

    try {
      const res = await fetch(`${API_BASE}/api/investigate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity: investigatedEntity,
          plugin,
          options: Object.keys(options).length > 0 ? options : undefined,
        }),
      })
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const findings = await res.json()
      setRunResults((prev) => [...prev, { id, family, entity: investigatedEntity, findings, error: null, statusFilter: null }])
    } catch (err) {
      setRunResults((prev) => [...prev, { id, family, entity: investigatedEntity, findings: null, error: err.message, statusFilter: null }])
    } finally {
      setLoading(false)
      setActiveResultId(id)
      closeDrawer()
    }
  }

  return (
    <main>
      <div className="catalog-content">
        <ToolBrowser
          families={families}
          onOpenTool={openTool}
          entityFilter={entityFilter}
          onEntityFilterChange={setEntityFilter}
          entityTypes={entityTypes}
        />

        {familiesError && <p className="error-message">{familiesError}</p>}
      </div>

      {activeResult && (
        <ResultsPanel
          family={activeResult.family}
          entity={activeResult.entity}
          findings={activeResult.findings}
          error={activeResult.error}
          statusFilter={activeResult.statusFilter}
          onToggleStatusFilter={(s) => updateActiveResult({ statusFilter: activeResult.statusFilter === s ? null : s })}
          onMinimize={() => setActiveResultId(null)}
          onClose={() => {
            setRunResults((prev) => prev.filter((r) => r.id !== activeResultId))
            setActiveResultId(null)
          }}
        />
      )}

      <ResultsTray
        results={trayResults}
        onOpen={setActiveResultId}
        onClose={(id) => setRunResults((prev) => prev.filter((r) => r.id !== id))}
      />

      <RunDrawer
        family={openFamilyData}
        onClose={closeDrawer}
        fastMode={fastModeByFamily[openFamily] ?? true}
        onToggleFastMode={(v) => setFastModeByFamily((prev) => ({ ...prev, [openFamily]: v }))}
        optionValues={optionsByFamily[openFamily] || {}}
        onOptionChange={handleOptionChange}
        entity={entity}
        onEntityChange={setEntity}
        onSubmit={handleSubmit}
        loading={loading}
        onCheckVersion={() => checkVersion(openFamily)}
        checkingVersion={checkingFamily === openFamily}
      />
    </main>
  )
}

export default InvestigatePage
