import { Component, type ReactNode, type ErrorInfo } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  panelName?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[ErrorBoundary${this.props.panelName ? `:${this.props.panelName}` : ""}]`, error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center h-full p-8 text-center">
          <svg className="w-10 h-10 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"
            style={{ color: "var(--severity-moderate)" }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <p className="font-mono-display text-xs tracking-wider mb-1"
            style={{ color: "var(--text-secondary)" }}>
            {this.props.panelName ? `${this.props.panelName.toUpperCase()} ERROR` : "COMPONENT ERROR"}
          </p>
          <p className="text-xs" style={{ color: "var(--text-tertiary)" }}>
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-3 px-3 py-1.5 rounded text-xs font-mono-display tracking-wider transition-colors"
            style={{
              border: "1px solid var(--bg-panel-border)",
              color: "var(--accent-orbital)",
              background: "rgba(77,124,255,0.05)",
            }}
          >
            RETRY
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
