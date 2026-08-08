import { useMemo, useState } from 'react'
import './App.css'
import ToolBrowser from './ToolBrowser.jsx'

function InvestigatePage({ families, familiesError, onOpenTool, onReload }) {
  const [entityFilter, setEntityFilter] = useState(null)

  const entityTypes = useMemo(() => {
    const seen = []
    for (const f of families) {
      if (f.hidden || f.entity_type === 'any') continue
      if (!seen.includes(f.entity_type)) seen.push(f.entity_type)
    }
    return seen
  }, [families])

  // When the catalog could not be loaded at all, show why instead of the
  // browser: an empty list otherwise renders "No tools match your
  // search/filters", which blames the filters for a backend that is down.
  if (familiesError) {
    return (
      <main>
        <div className="catalog-content catalog-error">
          <p className="error-message">{familiesError}</p>
          {onReload && (
            <button type="button" className="action-button" onClick={onReload}>
              Try again
            </button>
          )}
        </div>
      </main>
    )
  }

  return (
    <main>
      <div className="catalog-content">
        <ToolBrowser
          families={families}
          onOpenTool={onOpenTool}
          entityFilter={entityFilter}
          onEntityFilterChange={setEntityFilter}
          entityTypes={entityTypes}
        />
      </div>
    </main>
  )
}

export default InvestigatePage
