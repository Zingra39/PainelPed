import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}
interface State {
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  render() {
    if (this.state.error) {
      return this.props.fallback ?? (
        <div className="p-8 text-center text-red-600 text-sm">
          <p className="mb-3">Ocorreu um erro inesperado ao carregar esta página.</p>
          <button
            onClick={() => this.setState({ error: null })}
            className="text-blue-500 underline hover:text-blue-700"
          >
            Tentar novamente
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
