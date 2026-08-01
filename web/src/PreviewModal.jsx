import { CloseIcon } from './icons.jsx'

export default function PreviewModal({ title, kind, content, loading, error, onClose }) {
  return (
    <>
      <div className="preview-backdrop" onClick={onClose} />
      <section className="preview-modal" role="dialog" aria-modal="true">
        <div className="preview-modal-head">
          <h3>{title}</h3>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close preview">
            <CloseIcon />
          </button>
        </div>
        <div className="preview-modal-body">
          {loading && <p className="muted">Loading preview…</p>}
          {error && <p className="error-message">{error}</p>}
          {!loading && !error && kind === 'html' && (
            <iframe title={title} className="preview-iframe" srcDoc={content} sandbox="allow-same-origin" />
          )}
          {!loading && !error && kind === 'text' && (
            <pre className="preview-text">{content}</pre>
          )}
        </div>
      </section>
    </>
  )
}
