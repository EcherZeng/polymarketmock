import { Component, type ErrorInfo, type ReactNode } from "react"

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack)
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div style={{ padding: 24, color: "red", fontFamily: "monospace" }}>
            <h2>Something went wrong</h2>
            <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
              {this.state.error?.message}
            </pre>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 12, color: "#666", marginTop: 8 }}>
              {this.state.error?.stack}
            </pre>
          </div>
        )
      )
    }
    return this.props.children
  }
}
