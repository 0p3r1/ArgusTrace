import { useEffect, useRef, useState } from 'react'
import { Link, Route, Routes, useSearchParams } from 'react-router-dom'
import './App.css'
import { API_BASE, apiFetch } from './api.js'
import { BrandMark } from './icons.jsx'
import InvestigatePage from './InvestigatePage.jsx'
import ResultsPanel from './ResultsPanel.jsx'
import ResultsTray from './ResultsTray.jsx'
import RunDrawer from './RunDrawer.jsx'
import ToolInfoPage from './ToolInfoPage.jsx'
import { useToolFamilies } from './useToolFamilies.js'
import { useVersionCheck } from './useVersionCheck.js'
import { fastVariant, slowVariant } from './variants.js'

// Run/results state lives here, above <Routes>, so the drawer and the
// results tray survive navigating to a tool's info page — they used to
// live inside InvestigatePage and got wiped every time React Router
// unmounted it for a route change.
function App() {
  const { families, error: familiesError, setFamilies, reload } = useToolFamilies()
  const { checkVersion, checkingFamily } = useVersionCheck(setFamilies)

  const [openFamily, setOpenFamily] = useState(null)
  const [fastModeByFamily, setFastModeByFamily] = useState({})
  const [optionsByFamily, setOptionsByFamily] = useState({})
  const [entity, setEntity] = useState('')
  const [loading, setLoading] = useState(false)
  const [runResults, setRunResults] = useState([])
  const [activeResultId, setActiveResultId] = useState(null)
  const [searchParams, setSearchParams] = useSearchParams()
  // Lets the drawer abort an in-flight scan; a full run can take minutes and
  // was previously only escapable by reloading the page.
  const inFlight = useRef(null)

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

  // Direct-link handoff, e.g. someone bookmarks/shares "/?family=maigret".
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

  function handleClearOptions() {
    setOptionsByFamily((prev) => ({ ...prev, [openFamily]: {} }))
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

    // A module-level counter survived Vite's HMR reset while runResults did
    // not, so ids restarted at 1 and collided with results already on screen.
    const id = crypto.randomUUID()

    try {
      const controller = new AbortController()
      inFlight.current = controller
      const res = await apiFetch(`${API_BASE}/api/investigate`, {
        method: 'POST',
        signal: controller.signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entity: investigatedEntity,
          plugin,
          options: Object.keys(options).length > 0 ? options : undefined,
        }),
      })
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const findings = await res.json()
      setRunResults((prev) => [...prev, { id, family, plugin, entity: investigatedEntity, findings, error: null, statusFilter: null }])
    } catch (err) {
      const message = err.name === 'AbortError' ? 'Cancelled.' : err.message
      setRunResults((prev) => [...prev, { id, family, plugin, entity: investigatedEntity, findings: null, error: message, statusFilter: null }])
    } finally {
      inFlight.current = null
      setLoading(false)
      setActiveResultId(id)
      closeDrawer()
    }
  }

  return (
    <div className="page">
      <header className="site-header">
        <Link to="/" className="brand">
          <BrandMark />
          <h1>ArgusTrace</h1>
        </Link>
        <p className="tagline">Modular OSINT investigation, one entity at a time.</p>
      </header>

      <Routes>
        <Route
          path="/"
          element={<InvestigatePage families={families} familiesError={familiesError} onOpenTool={openTool} onReload={reload} />}
        />
        <Route
          path="/tools/:family"
          element={
            <ToolInfoPage
              families={families}
              checkVersion={checkVersion}
              checkingFamily={checkingFamily}
              onOpenTool={openTool}
            />
          }
        />
      </Routes>

      {activeResult && (
        <ResultsPanel
          family={activeResult.family}
          plugin={activeResult.plugin}
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
        onClearOptions={handleClearOptions}
        entity={entity}
        onEntityChange={setEntity}
        onSubmit={handleSubmit}
        onCancel={() => inFlight.current?.abort()}
        loading={loading}
        onCheckVersion={() => checkVersion(openFamily)}
        checkingVersion={checkingFamily === openFamily}
      />
    </div>
  )
}

export default App
