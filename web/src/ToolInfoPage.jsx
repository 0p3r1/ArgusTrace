import { Link, useNavigate, useParams } from 'react-router-dom'
import './App.css'
import { GitHubIcon } from './icons.jsx'
import ToolBadges from './ToolBadges.jsx'
import VersionBadge from './VersionBadge.jsx'

export default function ToolInfoPage({ families, checkVersion, checkingFamily, onOpenTool }) {
  const { family: familyKey } = useParams()
  const navigate = useNavigate()

  const family = families.find((f) => f.family === familyKey)

  if (families.length === 0) return <main><p className="muted">Loading…</p></main>

  if (!family) {
    return (
      <main>
        <p className="error-message">Unknown tool: {familyKey}</p>
        <Link to="/" className="back-link">← Back</Link>
      </main>
    )
  }

  const similarTools = families.filter((f) => !f.hidden && f.family !== family.family && f.entity_type === family.entity_type)
  const isGitHub = family.repo_url?.includes('github.com')

  function handleUseThisTool() {
    onOpenTool(family.family)
    navigate('/')
  }

  return (
    <main className={`tool-info-page type-${family.entity_type}`}>
      <Link to="/" className="back-link">← Back</Link>
      <p className="breadcrumbs"><span>{family.entity_type}</span><span className="breadcrumb-sep">/</span><span>{family.label}</span></p>

      <div className="tool-info-head">
        <div className="tool-info-head-title">
          <h2>{family.label}</h2>
          <ToolBadges family={family} />
        </div>
        <p className="tool-info-description">{family.description}</p>
      </div>

      <div className="tool-info-badges">
        <VersionBadge
          version={family.version}
          onCheck={family.version.status !== 'not_applicable' ? () => checkVersion(family.family) : undefined}
          checking={checkingFamily === family.family}
        />
        {family.variants.length > 1 && <span className="fast-badge">⚡ fast mode</span>}
      </div>

      <div className="tool-info-actions">
        {family.repo_url && (
          <a className="action-button" href={family.repo_url} target="_blank" rel="noreferrer">
            {isGitHub && <GitHubIcon />} Visit source ↗
          </a>
        )}
        {isGitHub && (
          <a className="action-button" href={`${family.repo_url}/issues`} target="_blank" rel="noreferrer">
            <GitHubIcon /> Report an issue ↗
          </a>
        )}
        <button type="button" className="action-button primary" onClick={handleUseThisTool}>
          Use this tool
        </button>
      </div>

      <section className="tool-info-section">
        <h3>Variants</h3>
        <ul className="variant-list">
          {family.variants.map((v) => (
            <li key={v.key}>
              <strong>{v.variant_label}</strong> — {v.speed}
            </li>
          ))}
        </ul>
      </section>

      {family.options.length > 0 && (
        <section className="tool-info-section">
          <h3>Options</h3>
          <ul className="option-info-list">
            {family.options.map((opt) => (
              <li key={opt.name}>
                <span className="option-flag">{opt.flag}</span>{' '}
                <span className={`option-tag ${opt.required ? 'required' : 'optional'}`}>
                  {opt.required ? 'required' : 'optional'}
                </span>
                <p className="option-description">{opt.description}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {family.native_reports.length > 0 && (
        <section className="tool-info-section">
          <h3>Native reports</h3>
          <ul className="native-report-list">
            {family.native_reports.map((r) => (
              <li key={r.format}>
                <div className="native-report-head">
                  <span className={`native-report-status ${r.available ? 'available' : 'unavailable'}`}>
                    {r.available ? 'Available' : 'Not generated'}
                  </span>
                  <strong>{r.label}</strong>
                </div>
                <p className="option-description">{r.note}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {family.examples.length > 0 && (
        <section className="tool-info-section">
          <h3>Example entities</h3>
          <ul className="example-list">
            {family.examples.map((ex) => (
              <li key={ex.entity}>
                <code>{ex.entity}</code> — {ex.label}
              </li>
            ))}
          </ul>
        </section>
      )}

      {similarTools.length > 0 && (
        <section className="tool-info-section">
          <h3>Similar tools</h3>
          <div className="similar-tools">
            {similarTools.map((f) => (
              <Link key={f.family} to={`/tools/${f.family}`} className="similar-tool-card">
                {f.label}
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}
