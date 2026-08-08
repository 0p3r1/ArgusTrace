import { useEffect, useState } from 'react'
import AdvancedOptionsPanel from './AdvancedOptionsPanel.jsx'
import { CloseIcon } from './icons.jsx'
import ImageEntityInput from './ImageEntityInput.jsx'
import { fastVariant, slowVariant } from './variants.js'
import VersionBadge from './VersionBadge.jsx'

export default function RunDrawer({
  onCancel,
  family,
  onClose,
  fastMode,
  onToggleFastMode,
  optionValues,
  onOptionChange,
  onClearOptions,
  entity,
  onEntityChange,
  onSubmit,
  loading,
  onCheckVersion,
  checkingVersion,
}) {
  // Ticks only while a run is in flight, so a long scan visibly progresses.
  const [elapsed, setElapsed] = useState(0)
  useEffect(() => {
    if (!loading) {
      setElapsed(0)
      return
    }
    const started = Date.now()
    const id = setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000)
    return () => clearInterval(id)
  }, [loading])

  const hasOptionValues = Object.values(optionValues || {}).some((v) => v !== undefined)
  const [clearedFlash, setClearedFlash] = useState(false)

  if (!family) return null

  const hasVariantChoice = family.variants.length > 1
  const showModeControls = hasVariantChoice || family.options.length > 0
  const activeVariant = hasVariantChoice
    ? (fastMode ? fastVariant(family) : slowVariant(family))
    : family.variants[0]

  function handleClearOptions() {
    onClearOptions()
    setClearedFlash(true)
    setTimeout(() => setClearedFlash(false), 1200)
  }

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className={`run-drawer type-${family.entity_type}`}>
        <div className="run-drawer-head">
          <div className="run-drawer-head-text">
            <h2>{family.label}</h2>
            <VersionBadge
              version={family.version}
              onCheck={family.version.status !== 'not_applicable' ? onCheckVersion : undefined}
              checking={checkingVersion}
            />
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close">
            <CloseIcon />
          </button>
        </div>

        <form onSubmit={onSubmit} className="run-drawer-form">
          {showModeControls && (
            <div className="fast-mode-block">
              <label className="fast-mode-toggle">
                <input
                  type="checkbox"
                  checked={fastMode}
                  onChange={(e) => onToggleFastMode(e.target.checked)}
                />
                Fast mode
              </label>
              <p className="fast-mode-info">
                {hasVariantChoice ? (
                  <>Uses <strong>{activeVariant.variant_label}</strong> ({activeVariant.speed}){fastMode ? ' — custom options are skipped.' : ' — set custom options below.'}</>
                ) : (
                  fastMode ? 'Custom options are skipped.' : 'Set custom options below.'
                )}
              </p>
            </div>
          )}

          {!fastMode && family.options.length > 0 && (
            <div className="advanced-options-wrap">
              <AdvancedOptionsPanel
                family={family}
                values={optionValues}
                onChange={onOptionChange}
                defaultOpen
              />
              <button
                type="button"
                className="clear-options-button"
                onClick={handleClearOptions}
                disabled={!hasOptionValues}
              >
                {clearedFlash ? 'Cleared ✓' : 'Clear options'}
              </button>
            </div>
          )}

          {family.entity_type === 'image' ? (
            <ImageEntityInput entity={entity} onEntityChange={onEntityChange} />
          ) : (
            <>
              <label className="field-label" htmlFor="entity-input">
                Entity to investigate
                {family.entity_type === 'company' && <span className="field-label-hint"> (optional if a person/location filter is set below)</span>}
              </label>
              <input
                id="entity-input"
                type="text"
                placeholder={family.examples[0]?.entity ?? family.entity_type}
                value={entity}
                onChange={(e) => onEntityChange(e.target.value)}
              />
            </>
          )}

          <button type="submit" className="submit-button" disabled={loading}>
            {loading ? `Investigating… ${elapsed}s` : 'Investigate'}
          </button>
          {loading && (
            // A full scan can run for minutes; without this, "still working"
            // and "hung" look identical and there is no way out but a reload.
            <button type="button" className="cancel-button" onClick={onCancel}>
              Cancel
            </button>
          )}
        </form>
      </aside>
    </>
  )
}
