import { useState } from 'react'
import { API_BASE, apiFetch } from './api.js'
import { downloadFindings, findingsContent } from './exportFindings.js'
import FindingDetailModal from './FindingDetailModal.jsx'
import { CloseIcon, EyeIcon, MinimizeIcon } from './icons.jsx'
import PreviewModal from './PreviewModal.jsx'
import RemoteAvatar from './RemoteAvatar.jsx'
import StatusBadge from './StatusBadge.jsx'
import { truncateForDisplay } from './textUtils.js'

const STATUS_FILTERS = [
  { status: 'FOUND', label: 'found' },
  { status: 'NOT_FOUND', label: 'not found' },
  { status: 'ERROR', label: 'error' },
]

const PROFILE_META_FIELDS = ['location', 'follower_count', 'company']

// Diagnostic fields already implied by the status badge/URL column — never
// worth a "Details" cell on their own. A curated evidence.headline (set by
// the plugin, not guessed here) is the primary row summary; profile/
// related_ids/coordinates get their own compact rendering. Everything else
// is still visible, just one click away in FindingDetailModal instead of
// crammed into a hover tooltip.
const DIAGNOSTIC_KEYS = new Set(['reason', 'http_status', 'error_reason', 'rate_limited'])

function hasMeaningfulEvidence(evidence) {
  if (!evidence) return false
  return Object.entries(evidence).some(([key, value]) => !DIAGNOSTIC_KEYS.has(key) && !isEmptyValue(value))
}

function isEmptyValue(value) {
  return value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)
}

function ProfileSummary({ profile, relatedIds }) {
  const label = profile?.fullname || profile?.name
  const meta = profile ? PROFILE_META_FIELDS.filter((key) => profile[key]).map((key) => profile[key]) : []
  const relatedCount = (Object.keys(relatedIds?.usernames ?? {}).length) + (relatedIds?.links?.length ?? 0)

  return (
    <div className="profile-cell">
      <RemoteAvatar src={profile?.image} className="profile-avatar" />
      <div className="profile-text">
        {label && <span className="profile-name">{label}</span>}
        {meta.length > 0 && <span className="profile-meta">{meta.join(' · ')}</span>}
        {relatedCount > 0 && <span className="profile-meta">+{relatedCount} related ID{relatedCount > 1 ? 's' : ''}</span>}
      </div>
    </div>
  )
}

function DetailsCell({ finding, onOpenDetail }) {
  const evidence = finding.evidence
  const clickable = hasMeaningfulEvidence(evidence)
  const coords = typeof evidence?.coordinates === 'string' ? evidence.coordinates.split(',') : null

  let body
  if (evidence?.profile || evidence?.related_ids) {
    body = <ProfileSummary profile={evidence.profile} relatedIds={evidence.related_ids} />
  } else if (evidence?.headline) {
    body = <span className="details-summary">{evidence.headline}</span>
  } else if (!clickable) {
    body = <span className="muted">—</span>
  }

  return (
    <div
      className={`details-cell${clickable ? ' details-cell-clickable' : ''}`}
      onClick={clickable ? () => onOpenDetail(finding) : undefined}
    >
      {body}
      {coords && (
        <a
          href={`https://www.openstreetmap.org/?mlat=${coords[0]}&mlon=${coords[1]}#map=11/${coords[0]}/${coords[1]}`}
          target="_blank"
          rel="noreferrer"
          className="details-map-link"
          onClick={(e) => e.stopPropagation()}
        >
          Map ↗
        </a>
      )}
      {clickable && <span className="details-cell-chevron">›</span>}
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

export default function ResultsPanel({ family, plugin, entity, findings, error, statusFilter, onToggleStatusFilter, onMinimize, onClose }) {
  const hasDetails = findings?.some((f) => hasMeaningfulEvidence(f.evidence)) ?? false
  const filenameBase = `${family.family}_${entity}`.replace(/[^\w.-]+/g, '_')
  const nativeActions = family.native_reports.filter((r) => r.available && r.kind !== 'info')
  // plugin identifies which variant produced these results, so the native
  // report can re-run the same one. Omitted rather than sent as "undefined"
  // if it's ever missing — the API 404s on an unknown plugin, and falling
  // back to the family default beats breaking the link outright.
  const reportUrl = (format) =>
    `${API_BASE}/api/tools/${family.family}/report?entity=${encodeURIComponent(entity)}&format=${format}` +
    (plugin ? `&plugin=${encodeURIComponent(plugin)}` : '')
  const [preview, setPreview] = useState(null)
  const [detailFinding, setDetailFinding] = useState(null)

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
      const res = await apiFetch(reportUrl(r.format))
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
          <h2 title={truncateForDisplay(`${family.label} — ${entity}`, 300)}>
            {family.label} <span className="results-panel-entity">— {truncateForDisplay(entity)}</span>
          </h2>
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
                    href={reportUrl(r.format)}
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
                            <td><DetailsCell finding={f} onOpenDetail={setDetailFinding} /></td>
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

      {detailFinding && (
        <FindingDetailModal finding={detailFinding} onClose={() => setDetailFinding(null)} />
      )}
    </>
  )
}
