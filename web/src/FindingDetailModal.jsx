import { CloseIcon } from './icons.jsx'
import StatusBadge from './StatusBadge.jsx'

// Fields already given their own dedicated spot in the modal (subtitle, map
// link, ...) — shown once, not repeated in the generic field list below.
const HANDLED_KEYS = new Set(['headline', 'coordinates', 'reason'])
// Within evidence.profile specifically, the photo gets its own visual slot.
const PROFILE_HANDLED_KEYS = new Set(['image'])

function isPresent(value) {
  return value !== null && value !== undefined && value !== '' && !(Array.isArray(value) && value.length === 0)
}

// Flatten evidence.profile/evidence.related_ids into individual field rows
// (fullname, location, related usernames, ...) instead of leaving them as
// one opaque nested object — this is the whole point of "click for more":
// every extracted attribute should actually be visible somewhere.
function buildFieldRows(evidence) {
  const rows = []
  for (const [key, value] of Object.entries(evidence)) {
    if (HANDLED_KEYS.has(key) || !isPresent(value)) continue
    if (key === 'profile') {
      for (const [pKey, pValue] of Object.entries(value)) {
        if (PROFILE_HANDLED_KEYS.has(pKey) || !isPresent(pValue)) continue
        rows.push([pKey, pValue])
      }
      continue
    }
    if (key === 'related_ids') {
      if (isPresent(value.usernames)) rows.push(['related usernames', value.usernames])
      if (isPresent(value.links)) rows.push(['related links', value.links])
      continue
    }
    rows.push([key, value])
  }
  return rows
}

function formatFieldValue(value) {
  if (Array.isArray(value)) {
    if (value.length === 0) return '—'
    if (typeof value[0] === 'object' && value[0] !== null) {
      return (
        <ul className="detail-field-list">
          {value.map((item, i) => (
            <li key={i}>
              {item.nom || item.prenoms
                ? [item.prenoms, item.nom].filter(Boolean).join(' ') + (item.qualite ? ` — ${item.qualite}` : '')
                : item.denomination
                  ? item.denomination + (item.qualite ? ` — ${item.qualite}` : '')
                  : JSON.stringify(item)}
            </li>
          ))}
        </ul>
      )
    }
    return (
      <div className="detail-field-tags">
        {value.map((v, i) => <span key={i} className="detail-field-tag">{String(v)}</span>)}
      </div>
    )
  }
  if (typeof value === 'object' && value !== null) {
    return (
      <ul className="detail-field-list">
        {Object.entries(value).map(([k, v]) => <li key={k}>{k}: {String(v)}</li>)}
      </ul>
    )
  }
  return String(value)
}

function fieldLabel(key) {
  return key.replaceAll('_', ' ')
}

export default function FindingDetailModal({ finding, onClose }) {
  const evidence = finding.evidence || {}
  const profile = evidence.profile
  const coords = typeof evidence.coordinates === 'string' ? evidence.coordinates.split(',') : null
  const fields = buildFieldRows(evidence)

  return (
    <>
      <div className="preview-backdrop" onClick={onClose} />
      <section className="detail-modal" role="dialog" aria-modal="true">
        <div className="preview-modal-head">
          <div className="detail-modal-head-text">
            <h3>{finding.source}</h3>
            <StatusBadge status={finding.status} />
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close details">
            <CloseIcon />
          </button>
        </div>
        <div className="detail-modal-body">
          {profile?.image && (
            <img
              src={profile.image}
              alt=""
              className="detail-modal-photo"
              referrerPolicy="no-referrer"
              onError={(e) => { e.currentTarget.style.display = 'none' }}
            />
          )}
          {evidence.headline && <p className="detail-modal-headline">{evidence.headline}</p>}
          {finding.url && <a className="detail-modal-url" href={finding.url} target="_blank" rel="noreferrer">{finding.url}</a>}
          {evidence.reason && <p className="error-message">{evidence.reason}</p>}
          {coords && (
            <a
              className="action-button"
              href={`https://www.openstreetmap.org/?mlat=${coords[0]}&mlon=${coords[1]}#map=11/${coords[0]}/${coords[1]}`}
              target="_blank"
              rel="noreferrer"
            >
              View on map ↗
            </a>
          )}

          {fields.length > 0 && (
            <dl className="detail-field-grid">
              {fields.map(([key, value]) => (
                <div key={key} className="detail-field-row">
                  <dt>{fieldLabel(key)}</dt>
                  <dd>{formatFieldValue(value)}</dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>
    </>
  )
}
