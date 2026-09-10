import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Shield } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { ApiError, getApiBase } from '../api/client'

export default function Login() {
  const { login, token, bootstrapping } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('analyst@example.com')
  const [password, setPassword] = useState('AnalystPass123!')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (bootstrapping) {
    return (
      <div className="flex min-h-screen items-center justify-center text-ink-500">
        Loading…
      </div>
    )
  }

  if (token) return <Navigate to="/" replace />

  async function onSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email.trim(), password)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-ink-100 via-ink-50 to-brand-50">
      <div className="m-auto w-full max-w-md px-4">
        <div className="card p-8">
          <div className="mb-6 flex items-center gap-3">
            <div className="rounded-lg bg-brand-700 p-2 text-white">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <h1 className="font-display text-2xl font-semibold text-ink-900">
                SAR Narrative Copilot
              </h1>
              <p className="text-sm text-ink-500">
                Analyst-in-the-loop · FinCEN 5 Ws + How
              </p>
            </div>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div>
              <label className="label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>

            {error ? (
              <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {error}
              </div>
            ) : null}

            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <details className="mt-5 text-xs text-ink-500">
            <summary className="cursor-pointer font-medium text-ink-600">
              Demo credentials & API
            </summary>
            <div className="mt-2 space-y-1 rounded-md bg-ink-50 p-3">
              <div>analyst@example.com / AnalystPass123!</div>
              <div>reviewer@example.com / ReviewerPass123!</div>
              <div className="pt-1 text-ink-400">API: {getApiBase()}</div>
            </div>
          </details>
        </div>
      </div>
    </div>
  )
}
