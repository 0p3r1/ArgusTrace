const LABELS = {
  current: 'Up to date',
  behind: 'One release behind',
  outdated: 'Outdated',
  unknown: 'Version unknown',
  not_applicable: null,
}

export default function VersionBadge({ version, compact = false, onCheck, checking = false }) {
  if (version.status === 'not_applicable') {
    return compact ? null : <span className="version-na">Not a versioned tool</span>
  }

  const label = LABELS[version.status] ?? version.status
  const title = version.pinned
    ? `Pinned: ${version.pinned}${version.latest ? ` · Latest: ${version.latest}` : ''}`
    : label

  return (
    <span className="version-badge-group">
      <span className={`version-pill version-${version.status}`} title={title}>
        {compact ? '' : label}
      </span>
      {onCheck && (
        <button
          type="button"
          className="version-check-button"
          onClick={onCheck}
          disabled={checking}
        >
          {checking ? 'Checking…' : 'Check version'}
        </button>
      )}
    </span>
  )
}
