import { useRef, useState } from 'react'

// Mirrors the plugin's own validation (argustrace/plugins/exif_plugin.py) so
// an obviously-too-large file is rejected before a request is even sent —
// the plugin still re-checks server-side, this is just a fast local check.
// No file-type restriction: exiftool reads 100+ formats (RAW, video, audio,
// PDF, ...) and the backend doesn't gate on type either — see exif_plugin.py
// for why (sandboxing the parser, not guessing the file, is the real control).
const MAX_BYTES = 100 * 1024 * 1024

export default function ImageEntityInput({ entity, onEntityChange }) {
  const [mode, setMode] = useState('url')
  const [fileInfo, setFileInfo] = useState(null)
  const [fileError, setFileError] = useState(null)
  const fileInputRef = useRef(null)

  function handleFile(file) {
    setFileError(null)
    if (!file) return
    if (file.size > MAX_BYTES) {
      setFileError(`File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB, max 100 MB).`)
      setFileInfo(null)
      onEntityChange('')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      onEntityChange(reader.result)
      setFileInfo({ name: file.name, size: file.size })
    }
    reader.onerror = () => setFileError('Could not read this file.')
    reader.readAsDataURL(file)
  }

  function switchMode(next) {
    setMode(next)
    setFileError(null)
    setFileInfo(null)
    onEntityChange('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="image-entity-input">
      <label className="field-label">Image to analyze</label>

      <div className="image-input-mode-toggle">
        <button type="button" className={mode === 'url' ? 'active' : ''} onClick={() => switchMode('url')}>
          Image URL
        </button>
        <button type="button" className={mode === 'upload' ? 'active' : ''} onClick={() => switchMode('upload')}>
          Upload file
        </button>
      </div>

      {mode === 'url' ? (
        <input
          type="text"
          placeholder="https://example.com/photo.jpg"
          value={entity}
          onChange={(e) => onEntityChange(e.target.value)}
        />
      ) : (
        <>
          <input
            ref={fileInputRef}
            type="file"
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          {fileInfo && (
            <p className="image-file-info">{fileInfo.name} — {(fileInfo.size / 1024).toFixed(0)} KB, ready</p>
          )}
        </>
      )}

      {fileError && <p className="error-message">{fileError}</p>}

      <p className="image-input-hint">
        Any format exiftool supports (photos, RAW, video, and more) — processed inside an
        isolated, network-disabled sandbox, never parsed on the host. 100 MB max.
      </p>
    </div>
  )
}
