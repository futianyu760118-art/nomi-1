import { Component, ErrorInfo, ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import App, { BrandMark } from './App'
import './styles.css'

class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('PMO rendering failed', error, info) }
  render() {
    if (this.state.failed) return <main className="fatal-error"><BrandMark /><h1>页面暂时无法加载</h1><button className="btn primary" onClick={() => window.location.reload()}>重新加载</button></main>
    return this.props.children
  }
}

const root = document.getElementById('root')
if (!root) throw new Error('Missing root element')
createRoot(root).render(<ErrorBoundary><App /></ErrorBoundary>)
