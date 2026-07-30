import { ErrorIcon, FoundIcon, NotFoundIcon } from './icons.jsx'

const CONFIG = {
  FOUND: { label: 'Found', icon: FoundIcon },
  NOT_FOUND: { label: 'Not found', icon: NotFoundIcon },
  ERROR: { label: 'Error', icon: ErrorIcon },
}

export default function StatusBadge({ status }) {
  const { label, icon: Icon } = CONFIG[status]
  return (
    <span className={`status-badge status-${status.toLowerCase()}`}>
      <Icon />
      {label}
    </span>
  )
}
