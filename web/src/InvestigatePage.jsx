import { useMemo, useState } from 'react'
import './App.css'
import ToolBrowser from './ToolBrowser.jsx'

function InvestigatePage({ families, familiesError, onOpenTool }) {
  const [entityFilter, setEntityFilter] = useState(null)

  const entityTypes = useMemo(() => {
    const seen = []
    for (const f of families) {
      if (f.hidden || f.entity_type === 'any') continue
      if (!seen.includes(f.entity_type)) seen.push(f.entity_type)
    }
    return seen
  }, [families])

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

        {familiesError && <p className="error-message">{familiesError}</p>}
      </div>
    </main>
  )
}

export default InvestigatePage
