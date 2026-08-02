import { useRef, useState } from 'react'

// Mirrors the plugin's own validation (argustrace/plugins/exif_plugin.py) so
// obviously-bad files are rejected before a request is even sent — the
// plugin still re-validates server-side, this is just a fast local check.
const MAX_BYTES = 20 * 1024 * 1024
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/tiff', 'image/webp', 'image/heic', 'image/heif']

export default function ImageEntityInput({ entity, onEntityChange }) {
  const [mode, setMode] = useState('url')
  const [fileInfo, setFileInfo] = useState(null)
  const [fileError, setFileError] = useState(null)
  const fileInputRef = useRef(null)

  function handleFile(file) {
    setFileError(null)
    if (!file) return
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setFileError(`Unsupported file type: ${file.type || 'unknown'}. Use JPEG, PNG, TIFF, WebP, or HEIC.`)
      setFileInfo(null)
      onEntityChange('')
      return
    }
    if (file.size > MAX_BYTES) {
      setFileError(`File is too large (${(file.size / 1024 / 1024).toFixed(1)} MB, max 20 MB).`)
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
            accept={ACCEPTED_TYPES.join(',')}
            onChange={(e) => handleFile(e.target.files?.[0])}
          />
          {fileInfo && (
            <p className="image-file-info">{fileInfo.name} — {(fileInfo.size / 1024).toFixed(0)} KB, ready</p>
          )}
        </>
      )}

      {fileError && <p className="error-message">{fileError}</p>}

      <p className="image-input-hint">
        Processed inside an isolated, read-only sandbox — the file is never parsed by an image
        library on the host. JPEG/PNG/TIFF/WebP/HEIC only, 20 MB max.
      </p>
    </div>
  )
}
