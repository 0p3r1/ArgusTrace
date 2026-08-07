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
            // sandbox="" is fully restrictive: no scripts, no forms, no
            // navigation, and an opaque origin. It must never gain
            // allow-same-origin — combined with srcDoc that gives the frame
            // this app's own origin, so adding allow-scripts alongside it
            // would turn a tool-generated report into same-origin XSS. The
            // reports rendered here are HTML produced by third-party OSINT
            // tools from attacker-influenced input.
            <iframe title={title} className="preview-iframe" srcDoc={content} sandbox="" />
          )}
          {!loading && !error && kind === 'text' && (
            <pre className="preview-text">{content}</pre>
          )}
        </div>
      </section>
    </>
  )
}
