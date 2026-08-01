import { useState } from 'react'
import { API_BASE } from './api.js'
import { downloadFindings, findingsContent } from './exportFindings.js'
import { CloseIcon, EyeIcon, MinimizeIcon } from './icons.jsx'
import PreviewModal from './PreviewModal.jsx'
import StatusBadge from './StatusBadge.jsx'

const STATUS_FILTERS = [
  { status: 'FOUND', label: 'found' },
  { status: 'NOT_FOUND', label: 'not found' },
  { status: 'ERROR', label: 'error' },
]

const PROFILE_META_FIELDS = ['location', 'follower_count', 'company']

// Diagnostic fields already implied by the status badge/URL column — never
// worth a "Details" cell on their own. profile/related_ids/coordinates get
// their own rendering below; every other evidence key falls back to a
// generic key:value summary so no plugin's data is ever silently invisible.
const DIAGNOSTIC_KEYS = new Set(['reason', 'http_status', 'error_reason', 'rate_limited'])
const SPECIALLY_RENDERED_KEYS = new Set(['profile', 'related_ids', 'coordinates'])

function hasMeaningfulEvidence(evidence) {
  if (!evidence) return false
  return Object.entries(evidence).some(([key, value]) => !DIAGNOSTIC_KEYS.has(key) && !isEmptyValue(value))
}

function isEmptyValue(value) {
  return value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)
}

function formatEvidenceValue(value) {
  if (Array.isArray(value)) {
    if (typeof value[0] === 'object' && value[0] !== null) {
      return value.map((item) => {
        if (item.nom || item.prenoms) return [item.prenoms, item.nom].filter(Boolean).join(' ') + (item.qualite ? ` (${item.qualite})` : '')
        if (item.denomination) return item.denomination + (item.qualite ? ` (${item.qualite})` : '')
        return JSON.stringify(item)
      }).join(', ')
    }
    return value.join(', ')
  }
  if (typeof value === 'object' && value !== null) {
    return Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(', ')
  }
  return String(value)
}

function DetailsCell({ evidence }) {
  if (evidence?.profile || evidence?.related_ids) {
    return <ProfileCell profile={evidence.profile} relatedIds={evidence.related_ids} />
  }

  const entries = evidence
    ? Object.entries(evidence).filter(([key, value]) => !DIAGNOSTIC_KEYS.has(key) && !SPECIALLY_RENDERED_KEYS.has(key) && !isEmptyValue(value))
    : []
  const coords = typeof evidence?.coordinates === 'string' ? evidence.coordinates.split(',') : null

  if (entries.length === 0 && !coords) return <span className="muted">—</span>

  const summary = entries.slice(0, 3).map(([, value]) => formatEvidenceValue(value)).join(' · ')
  const full = entries.map(([key, value]) => `${key}: ${formatEvidenceValue(value)}`).join('\n')

  return (
    <div className="details-cell" title={full}>
      {summary && <span className="details-summary">{summary}</span>}
      {coords && (
        <a
          href={`https://www.openstreetmap.org/?mlat=${coords[0]}&mlon=${coords[1]}#map=11/${coords[0]}/${coords[1]}`}
          target="_blank"
          rel="noreferrer"
          className="details-map-link"
        >
          Map ↗
        </a>
      )}
    </div>
  )
}

function relatedIdsText(relatedIds) {
  if (!relatedIds) return ''
  const lines = []
  if (relatedIds.usernames) {
    lines.push(...Object.entries(relatedIds.usernames).map(([name, type]) => `related ${type}: ${name}`))
  }
  if (relatedIds.links) {
    lines.push(...relatedIds.links.map((link) => `related link: ${link}`))
  }
  return lines.join('\n')
}

function ProfileCell({ profile, relatedIds }) {
  const label = profile?.fullname || profile?.name
  const meta = profile ? PROFILE_META_FIELDS.filter((key) => profile[key]).map((key) => profile[key]) : []
  const profileDetails = profile
    ? Object.entries(profile)
      .filter(([key]) => key !== 'image' && key !== '_extractor')
      .map(([key, value]) => `${key}: ${value}`)
      .join('\n')
    : ''
  const details = [profileDetails, relatedIdsText(relatedIds)].filter(Boolean).join('\n')

  const relatedCount = (Object.keys(relatedIds?.usernames ?? {}).length) + (relatedIds?.links?.length ?? 0)

  if (!label && meta.length === 0 && !profile?.image && !relatedCount) return <span className="muted">—</span>

  return (
    <div className="profile-cell" title={details}>
      {profile?.image && (
        <img
          src={profile.image}
          alt=""
          className="profile-avatar"
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
      )}
      <div className="profile-text">
        {label && <span className="profile-name">{label}</span>}
        {meta.length > 0 && <span className="profile-meta">{meta.join(' · ')}</span>}
        {relatedCount > 0 && <span className="profile-meta">+{relatedCount} related ID{relatedCount > 1 ? 's' : ''}</span>}
      </div>
    </div>
  )
}

function ResultsSummary({ findings, activeFilter, onToggleFilter }) {
  const counts = { FOUND: 0, NOT_FOUND: 0, ERROR: 0 }
  for (const f of findings) counts[f.status]++

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

export default function ResultsPanel({ family, entity, findings, error, statusFilter, onToggleStatusFilter, onMinimize, onClose }) {
  const hasDetails = findings?.some((f) => hasMeaningfulEvidence(f.evidence)) ?? false
  const filenameBase = `${family.family}_${entity}`.replace(/[^\w.-]+/g, '_')
  const nativeActions = family.native_reports.filter((r) => r.available && r.kind !== 'info')
  const [preview, setPreview] = useState(null)

  function previewOwnExport(format) {
    setPreview({
      title: `${family.label} — ${format.toUpperCase()} export`,
      kind: 'text',
      content: findingsContent(findings, format),
      loading: false,
      error: null,
    })
  }

  async function previewNativeReport(r) {
    setPreview({
      title: `${family.label} — ${r.label}`,
      kind: r.format === 'html' ? 'html' : 'text',
      content: '',
      loading: true,
      error: null,
    })
    try {
      const res = await fetch(`${API_BASE}/api/tools/${family.family}/report?entity=${encodeURIComponent(entity)}&format=${r.format}`)
      if (!res.ok) throw new Error(`API returned ${res.status}`)
      const text = await res.text()
      setPreview((prev) => (prev ? { ...prev, content: text, loading: false } : prev))
    } catch (err) {
      setPreview((prev) => (prev ? { ...prev, loading: false, error: err.message } : prev))
    }
  }

  return (
    <>
      <div className="results-modal-backdrop" onClick={onMinimize} />
      <section className={`results-modal type-${family.entity_type}`} role="dialog" aria-modal="true">
        <div className="results-modal-head">
          <h2>{family.label} <span className="results-panel-entity">— {entity}</span></h2>
          <div className="results-modal-head-actions">
            {findings && findings.length > 0 && (
              <>
                <span className="split-action">
                  <button type="button" className="action-button" onClick={() => downloadFindings(findings, filenameBase, 'csv')}>
                    Export CSV
                  </button>
                  <button type="button" className="icon-button" onClick={() => previewOwnExport('csv')} aria-label="Preview CSV export" title="Preview CSV export">
                    <EyeIcon />
                  </button>
                </span>
                <span className="split-action">
                  <button type="button" className="action-button" onClick={() => downloadFindings(findings, filenameBase, 'json')}>
                    Export JSON
                  </button>
                  <button type="button" className="icon-button" onClick={() => previewOwnExport('json')} aria-label="Preview JSON export" title="Preview JSON export">
                    <EyeIcon />
                  </button>
                </span>
              </>
            )}
            <button type="button" className="drawer-close" onClick={onMinimize} aria-label="Minimize (keep in tray)">
              <MinimizeIcon />
            </button>
            <button type="button" className="drawer-close" onClick={onClose} aria-label="Close and discard">
              <CloseIcon />
            </button>
          </div>
        </div>

        {nativeActions.length > 0 && (
          <div className="results-native-reports">
            <span className="results-native-reports-label">Native reports:</span>
            {nativeActions.map((r) =>
              r.kind === 'download' ? (
                <span key={r.format} className="split-action">
                  <a
                    className="action-button"
                    href={`${API_BASE}/api/tools/${family.family}/report?entity=${encodeURIComponent(entity)}&format=${r.format}`}
                    download
                    title={r.note}
                  >
                    {r.label}
                  </a>
                  <button
                    type="button"
                    className="icon-button"
                    onClick={() => previewNativeReport(r)}
                    aria-label={`Preview ${r.label}`}
                    title={`Preview ${r.label}`}
                  >
                    <EyeIcon />
                  </button>
                </span>
              ) : (
                <a
                  key={r.format}
                  className="action-button"
                  href={r.url_template.replace('{entity}', encodeURIComponent(entity))}
                  target="_blank"
                  rel="noreferrer"
                  title={r.note}
                >
                  {r.label} ↗
                </a>
              )
            )}
            {nativeActions.some((r) => r.kind === 'download') && (
              <span className="results-native-reports-hint">downloads re-run the tool, can take a few seconds</span>
            )}
          </div>
        )}

        <div className="results-modal-body">
          {error && <p className="error-message">{error}</p>}

          {findings && (
            <>
              <ResultsSummary findings={findings} activeFilter={statusFilter} onToggleFilter={onToggleStatusFilter} />
              <div className="findings-table-wrap">
                <table className="findings-table">
                  <thead>
                    <tr>
                      <th>Source</th>
                      <th>Status</th>
                      <th>URL</th>
                      {hasDetails && <th>Details</th>}
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
                          {hasDetails && (
                            <td><DetailsCell evidence={f.evidence} /></td>
                          )}
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </section>

      {preview && (
        <PreviewModal
          title={preview.title}
          kind={preview.kind}
          content={preview.content}
          loading={preview.loading}
          error={preview.error}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  )
}
