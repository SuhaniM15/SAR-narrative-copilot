import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, FileText, FolderOpen } from 'lucide-react'
import { api, ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'

function StatCard({ label, value, icon: Icon, tone }) {
  return (
    <div className="card flex items-start gap-3 p-4">
      <div className={`rounded-md p-2 ${tone}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <div className="text-2xl font-semibold text-ink-900">{value}</div>
        <div className="text-sm text-ink-500">{label}</div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { token } = useAuth()
  const [cases, setCases] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await api.listCases(token)
        if (!cancelled) setCases(data)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : 'Failed to load cases')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [token])

  const stats = useMemo(() => {
    const count = (status) => cases.filter((c) => c.status === status).length
    return {
      total: cases.length,
      open: count('open'),
      drafted: count('drafted'),
      under_review: count('under_review'),
      approved: count('approved'),
      rejected: count('rejected'),
    }
  }, [cases])

  const recent = useMemo(
    () =>
      [...cases]
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 6),
    [cases],
  )

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold text-ink-900">Dashboard</h1>
        <p className="mt-1 text-sm text-ink-500">
          Case workload overview from live API counts — no invented metrics.
        </p>
      </div>

      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      {loading ? (
        <div className="text-sm text-ink-500">Loading cases…</div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <StatCard
              label="Total cases"
              value={stats.total}
              icon={FolderOpen}
              tone="bg-ink-100 text-ink-700"
            />
            <StatCard
              label="Open"
              value={stats.open}
              icon={AlertTriangle}
              tone="bg-sky-50 text-sky-700"
            />
            <StatCard
              label="Drafts"
              value={stats.drafted}
              icon={FileText}
              tone="bg-amber-50 text-amber-700"
            />
            <StatCard
              label="Under review"
              value={stats.under_review}
              icon={FileText}
              tone="bg-violet-50 text-violet-700"
            />
            <StatCard
              label="Approved"
              value={stats.approved}
              icon={CheckCircle2}
              tone="bg-emerald-50 text-emerald-700"
            />
            <StatCard
              label="Rejected*"
              value={stats.rejected}
              icon={AlertTriangle}
              tone="bg-rose-50 text-rose-700"
            />
          </div>
          <p className="text-xs text-ink-400">
            * Rejected cases may return to <code>drafted</code> after reviewer rejection for
            revision.
          </p>

          <div className="card overflow-hidden">
            <div className="border-b border-ink-200 px-4 py-3">
              <h2 className="section-title">Recent cases</h2>
            </div>
            {recent.length === 0 ? (
              <div className="px-4 py-8 text-sm text-ink-500">No cases yet. Seed the API.</div>
            ) : (
              <table className="min-w-full text-left text-sm">
                <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Alert</th>
                    <th className="px-4 py-3 font-semibold">Customer</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 font-semibold">Risk</th>
                    <th className="px-4 py-3 font-semibold">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((c) => (
                    <tr key={c.id} className="border-t border-ink-100 hover:bg-ink-50/70">
                      <td className="px-4 py-3">
                        <Link
                          to={`/cases/${c.id}`}
                          className="font-medium text-brand-700 hover:underline"
                        >
                          {c.external_alert_id}
                        </Link>
                        <div className="text-xs text-ink-400">{c.title}</div>
                      </td>
                      <td className="px-4 py-3">{c.customer_name}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={c.status} />
                      </td>
                      <td className="px-4 py-3">
                        {c.risk_score != null ? c.risk_score.toFixed(2) : '—'}
                      </td>
                      <td className="px-4 py-3 text-ink-500">
                        {c.created_at ? new Date(c.created_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  )
}
