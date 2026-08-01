import { API_BASE } from './api.js'
import { downloadFindings } from './exportFindings.js'
import { CloseIcon, MinimizeIcon } from './icons.jsx'
import StatusBadge from './StatusBadge.jsx'

const STATUS_FILTERS = [
  { status: 'FOUND', label: 'found' },
  { status: 'NOT_FOUND', label: 'not found' },
  { status: 'ERROR', label: 'error' },
]

const PROFILE_META_FIELDS = ['location', 'follower_count', 'company']

function ProfileCell({ profile }) {
  const label = profile.fullname || profile.name
  const meta = PROFILE_META_FIELDS.filter((key) => profile[key]).map((key) => profile[key])
  const details = Object.entries(profile)
    .filter(([key]) => key !== 'image' && key !== '_extractor')
    .map(([key, value]) => `${key}: ${value}`)
    .join('\n')

  if (!label && meta.length === 0 && !profile.image) return <span className="muted">—</span>

  return (
    <div className="profile-cell" title={details}>
      {profile.image && (
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
  const hasProfiles = findings?.some((f) => f.evidence?.profile) ?? false
  const filenameBase = `${family.family}_${entity}`.replace(/[^\w.-]+/g, '_')
  const nativeActions = family.native_reports.filter((r) => r.available && r.kind !== 'info')

  return (
    <>
      <div className="results-modal-backdrop" onClick={onMinimize} />
      <section className={`results-modal type-${family.entity_type}`} role="dialog" aria-modal="true">
        <div className="results-modal-head">
          <h2>{family.label} <span className="results-panel-entity">— {entity}</span></h2>
          <div className="results-modal-head-actions">
            {findings && findings.length > 0 && (
              <>
                <button type="button" className="action-button" onClick={() => downloadFindings(findings, filenameBase, 'csv')}>
                  Export CSV
                </button>
                <button type="button" className="action-button" onClick={() => downloadFindings(findings, filenameBase, 'json')}>
                  Export JSON
                </button>
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
                <a
                  key={r.format}
                  className="action-button"
                  href={`${API_BASE}/api/tools/${family.family}/report?entity=${encodeURIComponent(entity)}&format=${r.format}`}
                  download
                  title={r.note}
                >
                  {r.label}
                </a>
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
                      {hasProfiles && <th>Profile</th>}
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
                          {hasProfiles && (
                            <td>{f.evidence?.profile ? <ProfileCell profile={f.evidence.profile} /> : <span className="muted">—</span>}</td>
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
    </>
  )
}
