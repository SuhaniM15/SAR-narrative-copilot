import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function AuditPage() {
  const { token } = useAuth()
  const [params] = useSearchParams()
  const [cases, setCases] = useState([])
  const [caseId, setCaseId] = useState(params.get('caseId') || '')
  const [events, setEvents] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api
      .listCases(token)
      .then((data) => {
        setCases(data)
        if (!caseId && data.length) setCaseId(String(data[0].id))
      })
      .catch((err) => setError(err instanceof ApiError ? err.detail : 'Failed to load cases'))
  }, [token])

  useEffect(() => {
    if (!caseId) return
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        const data = await api.caseAudit(token, Number(caseId))
        if (!cancelled) setEvents([...data].reverse())
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : 'Failed to load audit')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [token, caseId])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl font-semibold text-ink-900">Audit trail</h1>
        <p className="mt-1 text-sm text-ink-500">
          Append-only events for a selected case (actor, role, timestamp).
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <select
          className="input sm:max-w-md"
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
        >
          {cases.map((c) => (
            <option key={c.id} value={c.id}>
              #{c.id} · {c.external_alert_id} · {c.status}
            </option>
          ))}
        </select>
        {caseId ? (
          <Link to={`/cases/${caseId}`} className="text-sm font-medium text-brand-700 hover:underline">
            Open case workspace →
          </Link>
        ) : null}
      </div>

      {error ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
          {error}
        </div>
      ) : null}

      <div className="card overflow-hidden">
        {loading ? (
          <div className="px-4 py-8 text-sm text-ink-500">Loading audit…</div>
        ) : events.length === 0 ? (
          <div className="px-4 py-8 text-sm text-ink-500">No audit events for this case.</div>
        ) : (
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-4 py-3 font-semibold">Timestamp</th>
                <th className="px-4 py-3 font-semibold">Action</th>
                <th className="px-4 py-3 font-semibold">Role</th>
                <th className="px-4 py-3 font-semibold">Summary</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-t border-ink-100 align-top">
                  <td className="whitespace-nowrap px-4 py-3 text-ink-500">
                    {new Date(e.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-ink-800">
                    {e.event_type}
                  </td>
                  <td className="px-4 py-3">{e.actor_role || '—'}</td>
                  <td className="px-4 py-3">
                    <div>{e.summary}</div>
                    <details className="mt-1 text-xs text-ink-400">
                      <summary className="cursor-pointer">Detail</summary>
                      <pre className="mt-1 overflow-auto rounded bg-ink-50 p-2">
                        {e.detail_json}
                      </pre>
                    </details>
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
