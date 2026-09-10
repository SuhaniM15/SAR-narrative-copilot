import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { api, ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'

export default function Cases() {
  const { token } = useAuth()
  const [cases, setCases] = useState([])
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const data = await api.listCases(token)
        if (!cancelled) setCases(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : 'Failed to load')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [token])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return cases.filter((c) => {
      if (statusFilter !== 'all' && c.status !== statusFilter) return false
      if (!q) return true
      return (
        c.external_alert_id?.toLowerCase().includes(q) ||
        c.customer_name?.toLowerCase().includes(q) ||
        c.typology?.toLowerCase().includes(q) ||
        c.title?.toLowerCase().includes(q)
      )
    })
  }, [cases, query, statusFilter])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold text-ink-900">Cases</h1>
        <p className="mt-1 text-sm text-ink-500">
          Search and filter post-alert cases for narrative review.
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-ink-400" />
          <input
            className="input pl-9"
            placeholder="Search alert ID, customer, typology…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <select
          className="input sm:w-48"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="open">open</option>
          <option value="drafted">drafted</option>
          <option value="under_review">under_review</option>
          <option value="approved">approved</option>
          <option value="rejected">rejected</option>
        </select>
      </div>

      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="card overflow-hidden">
        {loading ? (
          <div className="px-4 py-8 text-sm text-ink-500">Loading cases…</div>
        ) : filtered.length === 0 ? (
          <div className="px-4 py-8 text-sm text-ink-500">No cases match this filter.</div>
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3 font-semibold">Alert / Case</th>
                <th className="px-4 py-3 font-semibold">Customer</th>
                <th className="px-4 py-3 font-semibold">Typology</th>
                <th className="px-4 py-3 font-semibold">Risk</th>
                <th className="px-4 py-3 font-semibold">Status</th>
                <th className="px-4 py-3 font-semibold">Created</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((c) => (
                <tr key={c.id} className="border-t border-ink-100 hover:bg-ink-50/70">
                  <td className="px-4 py-3">
                    <Link
                      to={`/cases/${c.id}`}
                      className="font-semibold text-brand-700 hover:underline"
                    >
                      {c.external_alert_id}
                    </Link>
                    <div className="max-w-xs truncate text-xs text-ink-400">{c.title}</div>
                  </td>
                  <td className="px-4 py-3">{c.customer_name}</td>
                  <td className="px-4 py-3 font-mono text-xs">{c.typology}</td>
                  <td className="px-4 py-3">
                    {c.risk_score != null ? c.risk_score.toFixed(2) : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={c.status} />
                  </td>
                  <td className="px-4 py-3 text-ink-500">
                    {c.created_at ? new Date(c.created_at).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
