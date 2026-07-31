import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import VersionBadge from './VersionBadge.jsx'

function ToolRow({ family, selected, onSelect }) {
  const isFast = family.variants.some((v) => v.fast)

  return (
    <div
      role="button"
      tabIndex={0}
      className={`tool-row${selected ? ' selected' : ''}`}
      onClick={() => onSelect(family.family)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onSelect(family.family)
        }
      }}
    >
      <VersionBadge version={family.version} compact />
      <span className="tool-row-label">{family.label}</span>
      <span className="tool-entity">{family.entity_type}</span>
      {isFast && <span className="fast-badge" title="Has a fast variant">⚡ fast</span>}
      <span className="tool-row-description">{family.description}</span>
      <Link
        to={`/tools/${family.family}`}
        className="tool-row-details"
        onClick={(e) => e.stopPropagation()}
      >
        Details
      </Link>
    </div>
  )
}

export default function ToolBrowser({ families, selectedFamily, onSelectFamily, entityFilter, onEntityFilterChange, entityTypes }) {
  const [search, setSearch] = useState('')
  const [fastOnly, setFastOnly] = useState(false)

  const visibleFamilies = useMemo(() => {
    const query = search.trim().toLowerCase()
    return families.filter((f) => {
      if (entityFilter && f.entity_type !== 'any' && f.entity_type !== entityFilter) return false
      if (fastOnly && !f.variants.some((v) => v.fast)) return false
      if (query && !f.label.toLowerCase().includes(query) && !f.description.toLowerCase().includes(query)) return false
      return true
    })
  }, [families, entityFilter, fastOnly, search])

  return (
    <div className="tool-browser">
      <input
        type="search"
        className="tool-search"
        placeholder="Search tools by name or description…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <div className="entity-filter">
        <button
          type="button"
          className={`filter-chip${!entityFilter ? ' active' : ''}`}
          onClick={() => onEntityFilterChange(null)}
        >
          All
        </button>
        {entityTypes.map((type) => (
          <button
            key={type}
            type="button"
            className={`filter-chip${entityFilter === type ? ' active' : ''}`}
            onClick={() => onEntityFilterChange(type)}
          >
            {type}
          </button>
        ))}
        <label className="fast-toggle">
          <input type="checkbox" checked={fastOnly} onChange={(e) => setFastOnly(e.target.checked)} />
          Fast only
        </label>
      </div>

      <div className="tool-list">
        {visibleFamilies.map((family) => (
          <ToolRow
            key={family.family}
            family={family}
            selected={selectedFamily === family.family}
            onSelect={onSelectFamily}
          />
        ))}
        {visibleFamilies.length === 0 && <p className="muted no-results">No tools match your search/filters.</p>}
      </div>
    </div>
  )
}
