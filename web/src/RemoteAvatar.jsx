import { useState } from 'react'

function hostOf(url) {
  try {
    return new URL(url).host
  } catch {
    return null
  }
}

/**
 * A profile picture hosted by whoever the tool found it on — loaded only when
 * asked for.
 *
 * Fetching it reveals the investigator's IP address and User-Agent to that
 * host, which in an OSINT context can tip off the very account being looked
 * into. `referrerPolicy="no-referrer"` hides where the request came from but
 * not who made it, so the request itself has to be the user's decision.
 */
export default function RemoteAvatar({ src, className }) {
  const [confirmed, setConfirmed] = useState(false)
  const host = src ? hostOf(src) : null

  if (!src || !host) return null

  if (!confirmed) {
    return (
      <button
        type="button"
        className={`${className} avatar-placeholder`}
        title={`Load picture from ${host} — this reveals your IP address to that host`}
        aria-label={`Load profile picture from ${host}`}
        onClick={(e) => {
          e.stopPropagation()  // the surrounding results cell is itself clickable
          setConfirmed(true)
        }}
      >
        <span aria-hidden="true">↓</span>
      </button>
    )
  }

  return (
    <img
      src={src}
      alt=""
      className={className}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={(e) => { e.currentTarget.style.display = 'none' }}
    />
  )
}
