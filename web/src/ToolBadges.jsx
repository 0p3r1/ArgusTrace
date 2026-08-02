import { ApiIcon, KeyIcon } from './icons.jsx'

// Transparency badges the user asked for explicitly: how a tool actually
// gets its data (a live API call vs. a wrapped CLI tool in Docker), and
// whether it needs a key/registration — only shown when true, since every
// integrated tool today is key-free by project policy (see CLAUDE.local.md).
export default function ToolBadges({ family }) {
  return (
    <>
      <span
        className={`source-badge source-${family.source_kind}`}
        title={family.source_kind === 'api' ? 'Queries a live API directly, no wrapped tool involved.' : 'Runs a dedicated OSINT tool inside an isolated container.'}
      >
        {family.source_kind === 'api' ? <ApiIcon /> : null} {family.source_kind === 'api' ? 'Direct API' : 'CLI tool'}
      </span>
      {family.requires_key && (
        <span className="key-badge" title={family.key_note || 'Requires an API key or registration to use.'}>
          <KeyIcon /> Needs key
        </span>
      )}
    </>
  )
}
