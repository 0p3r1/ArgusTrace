import { CloseIcon } from './icons.jsx'
import { truncateForDisplay } from './textUtils.js'

function chipSummary(result) {
  if (result.error) return 'error'
  if (!result.findings) return '…'
  const found = result.findings.filter((f) => f.status === 'FOUND').length
  return `${found} found`
}

export default function ResultsTray({ results, onOpen, onClose }) {
  if (results.length === 0) return null

  return (
    <div className="results-tray">
      {results.map((r) => (
        <div key={r.id} className={`results-chip type-${r.family.entity_type}`}>
          <button type="button" className="results-chip-body" onClick={() => onOpen(r.id)} title={truncateForDisplay(`${r.family.label} — ${r.entity}`, 300)}>
            <span className="results-chip-label">{r.family.label} — {truncateForDisplay(r.entity)}</span>
            <span className="results-chip-summary">{chipSummary(r)}</span>
          </button>
          <button type="button" className="results-chip-close" onClick={() => onClose(r.id)} aria-label="Discard">
            <CloseIcon />
          </button>
        </div>
      ))}
    </div>
  )
}
