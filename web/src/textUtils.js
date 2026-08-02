// Cap how much of a string we ever hand to the browser to lay out for
// display (e.g. an uploaded image's data: URI, which can run into the
// millions of characters). CSS text-overflow:ellipsis is meant to handle
// this, but real-world testing found it unreliable at these extremes —
// truncating the string itself is the only guarantee that a header row
// never gets pushed out of its bounds, in any browser.
export function truncateForDisplay(text, maxLength = 120) {
  if (typeof text !== 'string' || text.length <= maxLength) return text
  return `${text.slice(0, maxLength)}…`
}
