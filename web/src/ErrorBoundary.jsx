import { Component } from 'react'

/**
 * Last resort so a render-time crash shows something readable instead of a
 * blank page.
 *
 * There was no boundary at all: any unguarded field access on unexpected API
 * data — an error body where a list was expected, a status the badge doesn't
 * know — took the entire app down to a white screen with the cause only
 * visible in the console.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('ArgusTrace crashed while rendering:', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <div className="crash-screen">
        <h1>Something went wrong</h1>
        <p>
          The interface hit an unexpected error and stopped. Reloading usually
          clears it; if it comes straight back, the details are in the browser
          console.
        </p>
        <pre className="crash-detail">{String(this.state.error)}</pre>
        <button type="button" className="action-button" onClick={() => window.location.reload()}>
          Reload
        </button>
      </div>
    )
  }
}
