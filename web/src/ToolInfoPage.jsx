import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import './App.css'
import { useToolFamilies } from './useToolFamilies.js'
import { useVersionCheck } from './useVersionCheck.js'
import VersionBadge from './VersionBadge.jsx'

export default function ToolInfoPage() {
  const { family: familyKey } = useParams()
  const navigate = useNavigate()
  const { families, loading, setFamilies } = useToolFamilies()
  const { checkVersion, checkingFamily } = useVersionCheck(setFamilies)
  const [variantKey, setVariantKey] = useState(null)

  const family = families.find((f) => f.family === familyKey)
  const variant = family?.variants.find((v) => v.key === variantKey) ?? family?.variants[0]

  if (loading) return <main><p className="muted">Loading…</p></main>

  if (!family) {
    return (
      <main>
        <p className="error-message">Unknown tool: {familyKey}</p>
        <Link to="/">← Back to investigate</Link>
      </main>
    )
  }

  function handleUseThisTool() {
    navigate(`/?family=${family.family}&variant=${variant.key}`)
  }

  return (
    <main className="tool-info-page">
      <Link to="/" className="back-link">← Back to investigate</Link>

      <div className="tool-info-head">
        <h2>{family.label}</h2>
        <span className="tool-entity">{family.entity_type}</span>
        <VersionBadge
          version={family.version}
          onCheck={family.version.status !== 'not_applicable' ? () => checkVersion(family.family) : undefined}
          checking={checkingFamily === family.family}
        />
      </div>

      <p className="tool-info-description">{family.description}</p>

      {family.repo_url && (
        <p>
          <a href={family.repo_url} target="_blank" rel="noreferrer">View on GitHub ↗</a>
          {family.docs_url && family.docs_url !== family.repo_url && (
            <>
              {' · '}
              <a href={family.docs_url} target="_blank" rel="noreferrer">Documentation ↗</a>
            </>
          )}
        </p>
      )}

      <section className="tool-info-section">
        <h3>Variants</h3>
        <ul className="variant-list">
          {family.variants.map((v) => (
            <li key={v.key}>
              <strong>{v.variant_label}</strong> — {v.speed}
              {v.fast && <span className="fast-badge">⚡ fast</span>}
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

      {family.variants.length > 1 && (
        <label className="field-label" htmlFor="info-variant-select">
          Variant to use
          <select
            id="info-variant-select"
            className="variant-select"
            value={variant.key}
            onChange={(e) => setVariantKey(e.target.value)}
          >
            {family.variants.map((v) => (
              <option key={v.key} value={v.key}>{v.variant_label}</option>
            ))}
          </select>
        </label>
      )}

      <button type="button" className="submit-button" onClick={handleUseThisTool}>
        Use this tool
      </button>
    </main>
  )
}
