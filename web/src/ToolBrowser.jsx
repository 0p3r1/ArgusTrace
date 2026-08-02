import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { SearchIcon } from './icons.jsx'
import ToolBadges from './ToolBadges.jsx'
import VersionBadge from './VersionBadge.jsx'

function ToolCard({ family, onOpen }) {
  const hasFastVariant = family.variants.length > 1

  return (
    <div
      role="button"
      tabIndex={0}
      className={`tool-card type-${family.entity_type}`}
      onClick={() => onOpen(family.family)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onOpen(family.family)
        }
      }}
    >
      <div className="tool-card-head">
        <span className="tool-card-name" title={family.label}>{family.label}</span>
        <div className="tool-card-head-badges">
          <ToolBadges family={family} />
          <VersionBadge version={family.version} compact />
        </div>
      </div>

      <p className="tool-card-desc">{family.description}</p>

      <div className="tool-card-foot">
        <span className="tool-card-category">{family.entity_type}</span>
        {hasFastVariant && <span className="fast-badge">⚡ fast mode</span>}
      </div>

      <Link
        to={`/tools/${family.family}`}
        className="tool-card-details"
        onClick={(e) => e.stopPropagation()}
      >
        View details →
      </Link>
    </div>
  )
}

export default function ToolBrowser({ families, onOpenTool, entityFilter, onEntityFilterChange, entityTypes }) {
  const [search, setSearch] = useState('')
  const [fastOnly, setFastOnly] = useState(false)

  const visibleFamilies = useMemo(() => {
    const query = search.trim().toLowerCase()
    return families.filter((f) => {
      if (f.hidden) return false
      if (entityFilter && f.entity_type !== 'any' && f.entity_type !== entityFilter) return false
      if (fastOnly && f.variants.length <= 1) return false
      if (query && !f.label.toLowerCase().includes(query) && !f.description.toLowerCase().includes(query)) return false
      return true
    })
  }, [families, entityFilter, fastOnly, search])

  return (
    <div className="tool-browser">
      <div className="tool-search-wrap">
        <span className="tool-search-icon"><SearchIcon /></span>
        <input
          type="search"
          className="tool-search"
          placeholder="Search all tools…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="tag-filters">
        <button
          type="button"
          className={`tag-filter${!entityFilter ? ' active' : ''}`}
          onClick={() => onEntityFilterChange(null)}
        >
          All
        </button>
        {entityTypes.map((type) => (
          <button
            key={type}
            type="button"
            className={`tag-filter type-${type}${entityFilter === type ? ' active' : ''}`}
            onClick={() => onEntityFilterChange(type)}
          >
            {type}
          </button>
        ))}
        <label className="fast-toggle">
          <input type="checkbox" checked={fastOnly} onChange={(e) => setFastOnly(e.target.checked)} />
          Has fast mode
        </label>
      </div>

      <div className="tool-grid">
        {visibleFamilies.map((family) => (
          <ToolCard key={family.family} family={family} onOpen={onOpenTool} />
        ))}
        {visibleFamilies.length === 0 && <p className="muted no-results">No tools match your search/filters.</p>}
      </div>
    </div>
  )
}
