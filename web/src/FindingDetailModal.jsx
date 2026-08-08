import { useState } from 'react'
import { CheckIcon, CloseIcon, CopyIcon } from './icons.jsx'
import { describeRecord, isPresent, openStreetMapUrl, parseCoordinates } from './lib/evidence.js'
import RemoteAvatar from './RemoteAvatar.jsx'
import StatusBadge from './StatusBadge.jsx'

// Fields already given their own dedicated spot in the modal (subtitle, map
// link, ...) — shown once, not repeated in the generic field list below.
const HANDLED_KEYS = new Set(['headline', 'coordinates', 'reason'])
// Within evidence.profile specifically, the photo gets its own visual slot.
const PROFILE_HANDLED_KEYS = new Set(['image'])

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
            <li key={i}>{describeRecord(item) ?? JSON.stringify(item)}</li>
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

// Plain-text counterpart to formatFieldValue — clipboard content should be
// pasteable text, not JSX, so arrays/objects get flattened differently here.
function plainTextValue(value) {
  if (Array.isArray(value)) {
    if (typeof value[0] === 'object' && value[0] !== null) {
      return value.map((item) => describeRecord(item) ?? JSON.stringify(item)).join(', ')
    }
    return value.join(', ')
  }
  if (typeof value === 'object' && value !== null) {
    return Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(', ')
  }
  return String(value)
}

function CopyButton({ value, label }) {
  const [copied, setCopied] = useState(false)

  async function handleCopy(e) {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1200)
    } catch {
      // Clipboard access denied/unavailable — nothing meaningful to recover into.
    }
  }

  return (
    <button
      type="button"
      className="copy-field-button"
      onClick={handleCopy}
      aria-label={`Copy ${label}`}
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
    </button>
  )
}

export default function FindingDetailModal({ finding, onClose }) {
  const evidence = finding.evidence || {}
  const profile = evidence.profile
  const coords = parseCoordinates(evidence.coordinates)
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
          <RemoteAvatar src={profile?.image} className="detail-modal-photo" />
          {evidence.headline && (
            <p className="detail-modal-headline">
              {evidence.headline}
              <CopyButton value={evidence.headline} label="headline" />
            </p>
          )}
          {finding.url && (
            <p className="detail-modal-url-row">
              <a className="detail-modal-url" href={finding.url} target="_blank" rel="noreferrer">{finding.url}</a>
              <CopyButton value={finding.url} label="URL" />
            </p>
          )}
          {evidence.reason && <p className="error-message">{evidence.reason}</p>}
          {coords && (
            <a
              className="action-button"
              href={openStreetMapUrl(coords)}
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
                  <dd>
                    {formatFieldValue(value)}
                    <CopyButton value={plainTextValue(value)} label={fieldLabel(key)} />
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
      </section>
    </>
  )
}
