// Shared reading of the `evidence` conventions (see CLAUDE.md).
//
// These were duplicated between ResultsPanel and FindingDetailModal — the
// same emptiness test under two names, the same OpenStreetMap URL built
// twice, and the same list of French company-registry field names hardcoded
// in two places inside what is otherwise a generic renderer. Divergent copies
// of the last one are the reason this file exists: a plugin's field names do
// not belong in code that renders every plugin's output.

export function isEmptyValue(value) {
  return (
    value === null ||
    value === undefined ||
    value === '' ||
    (Array.isArray(value) && value.length === 0)
  )
}

export function isPresent(value) {
  return !isEmptyValue(value)
}

/** `evidence.coordinates` is a "lat,lon" string; anything else is not a point. */
export function parseCoordinates(value) {
  if (typeof value !== 'string') return null
  const [lat, lon] = value.split(',').map((part) => part.trim())
  if (!lat || !lon) return null
  return { lat, lon }
}

export function openStreetMapUrl({ lat, lon }) {
  return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=11/${lat}/${lon}`
}

// Field names some tools use for a person or company inside a list — France's
// registry names its officers this way (`dirigeants`). Kept as data in one
// place so the renderers stay generic; a record that matches none of these
// falls back to its raw JSON rather than being silently hidden.
const PERSON_NAME_FIELDS = ['prenoms', 'nom']
const ORGANISATION_NAME_FIELD = 'denomination'
const ROLE_FIELD = 'qualite'

/**
 * A one-line description of a record inside an evidence list.
 * Returns null when the record has no recognised name-like field, leaving
 * the caller to decide how to show it.
 */
export function describeRecord(item) {
  if (!item || typeof item !== 'object') return null

  const role = item[ROLE_FIELD] ? ` — ${item[ROLE_FIELD]}` : ''
  const personName = PERSON_NAME_FIELDS.map((field) => item[field]).filter(Boolean).join(' ')
  if (personName) return personName + role
  if (item[ORGANISATION_NAME_FIELD]) return item[ORGANISATION_NAME_FIELD] + role
  return null
}
