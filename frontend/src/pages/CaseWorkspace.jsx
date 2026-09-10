import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ArrowLeft,
  BookOpen,
  Download,
  FileWarning,
  Loader2,
  ShieldCheck,
  Sparkles,
} from 'lucide-react'
import { api, ApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'
import StatusBadge from '../components/StatusBadge'
import LifecycleStepper from '../components/LifecycleStepper'

function parseJson(raw, fallback) {
  try {
    return JSON.parse(raw || '') ?? fallback
  } catch {
    return fallback
  }
}

/** Show only a short doc name — never absolute local paths. */
function citationSourceLabel(citation) {
  const raw = citation?.source_path || citation?.doc_id || ''
  const normalized = String(raw).replace(/\\/g, '/')
  const base = normalized.split('/').filter(Boolean).pop()
  return base || citation?.doc_id || 'policy doc'
}

function buildNarrativeMarkdown(caseData, draft, citations = [], citedTxns = []) {
  const alertId = caseData?.external_alert_id || 'case'
  const citeLines = (citations || []).map(
    (c) => `- ${c.title || c.doc_id}${c.snippet ? `: ${c.snippet}` : ''}`,
  )
  return [
    `# SAR Narrative — ${alertId}`,
    '',
    `**Title:** ${caseData?.title || ''}`,
    `**Status:** ${caseData?.status || ''}`,
    `**Typology:** ${caseData?.typology || ''}`,
    `**Jurisdiction:** ${caseData?.jurisdiction || ''}`,
    `**Draft version:** ${draft?.version ?? ''}`,
    '',
    '## Who',
    draft?.who || '',
    '',
    '## What',
    draft?.what || '',
    '',
    '## When',
    draft?.when || '',
    '',
    '## Where',
    draft?.where || '',
    '',
    '## Why',
    draft?.why || '',
    '',
    '## How',
    draft?.how || '',
    '',
    '## Full narrative',
    draft?.full_narrative || '',
    '',
    '## Evidence transaction refs',
    citedTxns?.length ? citedTxns.map((r) => `- ${r}`).join('\n') : '- (none)',
    '',
    '## Regulatory citations',
    citeLines.length ? citeLines.join('\n') : '- (none)',
    '',
  ].join('\n')
}

function buildNarrativeJson(caseData, draft, citations = [], citedTxns = []) {
  return JSON.stringify(
    {
      alert_id: caseData?.external_alert_id,
      title: caseData?.title,
      status: caseData?.status,
      typology: caseData?.typology,
      jurisdiction: caseData?.jurisdiction,
      draft_version: draft?.version,
      narrative: {
        who: draft?.who,
        what: draft?.what,
        when: draft?.when,
        where: draft?.where,
        why: draft?.why,
        how: draft?.how,
        full_narrative: draft?.full_narrative,
      },
      evidence_txn_refs: citedTxns || [],
      citations: (citations || []).map((c) => ({
        doc_id: c.doc_id,
        title: c.title,
        typologies: c.typologies,
        snippet: c.snippet,
      })),
      exported_at: new Date().toISOString(),
    },
    null,
    2,
  )
}

function downloadFile(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function nextStepHint(status, hasDraft) {
  if (status === 'open') return 'Next: generate a grounded SAR draft.'
  if (status === 'drafted' && hasDraft) return 'Next: edit if needed, then submit for review.'
  if (status === 'under_review') return 'Next: reviewer approve or reject with a comment.'
  if (status === 'approved') return 'Case approved — drafts are locked.'
  if (status === 'rejected') return 'Rejected path — revise draft and resubmit.'
  return ''
}

export default function CaseWorkspace() {
  const { caseId } = useParams()
  const { token, isAnalyst, isReviewer } = useAuth()
  const [caseData, setCaseData] = useState(null)
  const [evidence, setEvidence] = useState(null)
  const [drafts, setDrafts] = useState([])
  const [audit, setAudit] = useState([])
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [actionOk, setActionOk] = useState('')
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draftForm, setDraftForm] = useState(null)
  const [decisionComment, setDecisionComment] = useState('')

  const latest = drafts.length ? drafts[drafts.length - 1] : null
  const citations = useMemo(
    () => parseJson(latest?.retrieval_citations_json, []),
    [latest],
  )
  const citedTxns = useMemo(
    () => parseJson(latest?.evidence_txn_refs_json, []),
    [latest],
  )

  const refresh = useCallback(async () => {
    const id = Number(caseId)
    const [c, e, d, a] = await Promise.all([
      api.getCase(token, id),
      api.getEvidence(token, id),
      api.listDrafts(token, id),
      api.caseAudit(token, id),
    ])
    setCaseData(c)
    setEvidence(e)
    setDrafts(d)
    setAudit([...a].reverse())
    const last = d.length ? d[d.length - 1] : null
    if (last) {
      setDraftForm({
        who: last.who || '',
        what: last.what || '',
        when: last.when || '',
        where: last.where || '',
        why: last.why || '',
        how: last.how || '',
        full_narrative: last.full_narrative || '',
      })
    } else {
      setDraftForm(null)
    }
  }, [token, caseId])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError('')
      try {
        await refresh()
      } catch (err) {
        if (!cancelled) setError(err instanceof ApiError ? err.detail : 'Failed to load case')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [refresh])

  async function runAction(fn, okMessage) {
    setActionError('')
    setActionOk('')
    try {
      await fn()
      await refresh()
      setActionOk(okMessage)
      setEditing(false)
    } catch (err) {
      setActionError(err instanceof ApiError ? err.detail : 'Action failed')
    }
  }

  async function onGenerate() {
    setGenerating(true)
    await runAction(
      () => api.generateDraft(token, Number(caseId)),
      'Draft generated (versioned + audited).',
    )
    setGenerating(false)
  }

  if (loading) {
    return <div className="text-sm text-ink-500">Loading case workspace…</div>
  }

  if (error || !caseData) {
    return (
      <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
        {error || 'Case not found'}
      </div>
    )
  }

  const status = caseData.status
  const canGenerate = isAnalyst && ['open', 'drafted', 'rejected'].includes(status)
  const canSubmit = isAnalyst && ['open', 'drafted', 'rejected'].includes(status) && !!latest
  const canEdit = isAnalyst && ['open', 'drafted', 'rejected'].includes(status) && !!latest
  const canDecide = isReviewer && ['under_review', 'drafted'].includes(status)
  const commentOk = decisionComment.trim().length > 0

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link to="/cases" className="inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-800">
          <ArrowLeft className="h-4 w-4" />
          Back to cases
        </Link>
        <Link
          to={`/audit?caseId=${caseData.id}`}
          className="text-sm font-medium text-brand-700 hover:underline"
        >
          Full audit trail →
        </Link>
      </div>

      <div className="card p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-semibold text-ink-900 md:text-3xl">
              {caseData.title}
            </h1>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <span className="rounded-md border border-ink-200 bg-ink-50 px-2.5 py-1">
                <strong>Alert</strong> {caseData.external_alert_id}
              </span>
              <span className="rounded-md border border-ink-200 bg-ink-50 px-2.5 py-1">
                <strong>Typology</strong> {caseData.typology}
              </span>
              <span className="rounded-md border border-ink-200 bg-ink-50 px-2.5 py-1">
                <strong>Risk</strong>{' '}
                {caseData.risk_score != null ? caseData.risk_score.toFixed(2) : '—'}
              </span>
              <span className="rounded-md border border-ink-200 bg-ink-50 px-2.5 py-1">
                <strong>Jurisdiction</strong> {caseData.jurisdiction}
              </span>
              <StatusBadge status={status} />
            </div>
          </div>
        </div>
        <div className="mt-4">
          <LifecycleStepper status={status} />
          <p className="mt-2 text-sm text-ink-500">{nextStepHint(status, !!latest)}</p>
        </div>
      </div>

      {(actionError || actionOk) && (
        <div
          className={`rounded-md border px-3 py-2 text-sm ${
            actionError
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-emerald-200 bg-emerald-50 text-emerald-800'
          }`}
        >
          {actionError || actionOk}
        </div>
      )}

      <div className="card flex flex-wrap items-center gap-2 p-3">
        {canGenerate ? (
          <button type="button" className="btn-primary" disabled={generating} onClick={onGenerate}>
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {generating ? 'Generating…' : 'Generate draft'}
          </button>
        ) : null}
        {canSubmit ? (
          <button
            type="button"
            className="btn-secondary"
            onClick={() =>
              runAction(() => api.submitCase(token, Number(caseId)), 'Submitted for review.')
            }
          >
            Submit for review
          </button>
        ) : null}
        {canEdit ? (
          <button type="button" className="btn-secondary" onClick={() => setEditing((v) => !v)}>
            {editing ? 'Cancel edit' : 'Edit draft'}
          </button>
        ) : null}
        {latest ? (
          <>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                const base = `${caseData.external_alert_id || 'sar'}-draft-v${latest.version}`
                downloadFile(
                  `${base}.md`,
                  buildNarrativeMarkdown(caseData, latest, citations, citedTxns),
                  'text/markdown;charset=utf-8',
                )
              }}
            >
              <Download className="h-4 w-4" />
              Export Markdown
            </button>
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                const base = `${caseData.external_alert_id || 'sar'}-draft-v${latest.version}`
                downloadFile(
                  `${base}.json`,
                  buildNarrativeJson(caseData, latest, citations, citedTxns),
                  'application/json;charset=utf-8',
                )
              }}
            >
              <Download className="h-4 w-4" />
              Export JSON
            </button>
          </>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card p-4">
          <h2 className="section-title mb-3">Customer / KYC</h2>
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-ink-400">Customer ID</dt>
              <dd className="font-medium">{caseData.customer_id}</dd>
            </div>
            <div>
              <dt className="text-ink-400">Name</dt>
              <dd className="font-medium">{caseData.customer_name}</dd>
            </div>
            <div>
              <dt className="text-ink-400">Occupation</dt>
              <dd>{caseData.customer_occupation}</dd>
            </div>
            <div>
              <dt className="text-ink-400">Country</dt>
              <dd>{caseData.customer_country}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-ink-400">Expected activity</dt>
              <dd>{caseData.customer_expected_activity}</dd>
            </div>
          </dl>
        </section>

        <section className="card p-4">
          <h2 className="section-title mb-3">Alert</h2>
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="text-ink-400">Alert ID</dt>
              <dd className="font-medium">{caseData.external_alert_id}</dd>
            </div>
            <div>
              <dt className="text-ink-400">Reason</dt>
              <dd>{caseData.alert_reason}</dd>
            </div>
          </dl>
        </section>
      </div>

      <section className="card overflow-hidden">
        <div className="border-b border-ink-200 px-4 py-3">
          <h2 className="section-title">Transactions</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-ink-50 text-xs uppercase tracking-wide text-ink-500">
              <tr>
                <th className="px-3 py-2">Ref</th>
                <th className="px-3 py-2">Amount</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2">Counterparty</th>
                <th className="px-3 py-2">Location</th>
                <th className="px-3 py-2">Channel</th>
                <th className="px-3 py-2">When</th>
              </tr>
            </thead>
            <tbody>
              {(caseData.transactions || []).map((t) => (
                <tr key={t.id || t.txn_ref} className="border-t border-ink-100">
                  <td className="px-3 py-2 font-mono text-xs">{t.txn_ref}</td>
                  <td className="px-3 py-2">
                    {t.amount} {t.currency}
                  </td>
                  <td className="px-3 py-2">{t.txn_type}</td>
                  <td className="px-3 py-2">{t.counterparty}</td>
                  <td className="px-3 py-2">{t.location || '—'}</td>
                  <td className="px-3 py-2">{t.channel}</td>
                  <td className="px-3 py-2 text-ink-500">
                    {t.occurred_at ? new Date(t.occurred_at).toLocaleString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-5">
        <div className="space-y-4 xl:col-span-2">
          <section className="card p-4">
            <div className="mb-3 flex items-center gap-2">
              <FileWarning className="h-4 w-4 text-brand-700" />
              <h2 className="section-title">Typology findings</h2>
            </div>
            {!evidence?.findings?.length ? (
              <p className="text-sm text-ink-500">No deterministic rules triggered.</p>
            ) : (
              <ul className="space-y-3">
                {evidence.findings.map((f) => (
                  <li key={f.rule_id} className="rounded-md border border-ink-200 bg-ink-50 p-3">
                    <div className="font-mono text-xs font-semibold text-brand-800">
                      {f.rule_id}
                    </div>
                    <div className="mt-1 text-sm text-ink-800">{f.finding}</div>
                    <div className="mt-1 text-xs text-ink-500">
                      Evidence: {(f.evidence_txn_refs || []).join(', ') || '—'}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="card p-4">
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-brand-700" />
              <h2 className="section-title">Evidence / grounding</h2>
            </div>
            <div className="space-y-2 text-sm">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-400">
                  Allowed txn refs
                </div>
                <div className="mt-1 font-mono text-xs">
                  {(evidence?.allowed_txn_refs || []).join(', ') || '—'}
                </div>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-400">
                  Cited in draft
                </div>
                <div className="mt-1 font-mono text-xs">
                  {citedTxns.length ? citedTxns.join(', ') : '—'}
                </div>
              </div>
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-ink-400">
                  Grounding status
                </div>
                <div className="mt-1">
                  {latest
                    ? 'Saved drafts passed allow-list validation (fail-closed on invent).'
                    : 'Generate a draft to run grounding checks.'}
                </div>
              </div>
            </div>
          </section>

          <section className="card p-4">
            <div className="mb-3 flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-brand-700" />
              <h2 className="section-title">Regulatory sources</h2>
            </div>
            {!citations.length ? (
              <p className="text-sm text-ink-500">Citations appear after draft generation.</p>
            ) : (
              <ul className="space-y-3">
                {citations.map((c) => (
                  <li
                    key={`${c.doc_id}-${c.distance}`}
                    className="border-l-2 border-brand-600 bg-ink-50 py-2 pl-3"
                  >
                    <div className="text-sm font-semibold text-ink-800">
                      {c.title || c.doc_id}
                    </div>
                    <div className="text-xs text-ink-400">
                      {citationSourceLabel(c)}
                      {c.typologies?.length ? ` · ${c.typologies.join(', ')}` : ''}
                    </div>
                    <p className="mt-1 text-sm text-ink-600">{c.snippet}</p>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>

        <div className="space-y-4 xl:col-span-3">
          <section className="card p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="section-title">SAR narrative</h2>
                {latest ? (
                  <span className="text-xs text-ink-400">Draft v{latest.version}</span>
                ) : null}
              </div>
              {latest ? (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      const base = `${caseData.external_alert_id || 'sar'}-draft-v${latest.version}`
                      downloadFile(
                        `${base}.md`,
                        buildNarrativeMarkdown(caseData, latest, citations, citedTxns),
                        'text/markdown;charset=utf-8',
                      )
                    }}
                  >
                    <Download className="h-4 w-4" />
                    Export .md
                  </button>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => {
                      const base = `${caseData.external_alert_id || 'sar'}-draft-v${latest.version}`
                      downloadFile(
                        `${base}.json`,
                        buildNarrativeJson(caseData, latest, citations, citedTxns),
                        'application/json;charset=utf-8',
                      )
                    }}
                  >
                    <Download className="h-4 w-4" />
                    Export .json
                  </button>
                </div>
              ) : null}
            </div>

            {!latest ? (
              <div className="rounded-md border border-dashed border-ink-300 bg-ink-50 px-4 py-8 text-center">
                <p className="text-sm text-ink-600">No draft yet.</p>
                {canGenerate ? (
                  <button
                    type="button"
                    className="btn-primary mt-3"
                    disabled={generating}
                    onClick={onGenerate}
                  >
                    Generate draft
                  </button>
                ) : (
                  <p className="mt-2 text-xs text-ink-400">Analyst role required to generate.</p>
                )}
              </div>
            ) : editing && draftForm ? (
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault()
                  runAction(
                    () => api.updateDraft(token, Number(caseId), draftForm),
                    'Draft edits saved as a new version.',
                  )
                }}
              >
                {['who', 'what', 'when', 'where', 'why', 'how'].map((key) => (
                  <div key={key}>
                    <label className="label" htmlFor={key}>
                      {key}
                    </label>
                    <textarea
                      id={key}
                      className="input min-h-[70px]"
                      value={draftForm[key]}
                      onChange={(e) =>
                        setDraftForm((prev) => ({ ...prev, [key]: e.target.value }))
                      }
                    />
                  </div>
                ))}
                <div>
                  <label className="label" htmlFor="full_narrative">
                    Full narrative
                  </label>
                  <textarea
                    id="full_narrative"
                    className="input min-h-[120px]"
                    value={draftForm.full_narrative}
                    onChange={(e) =>
                      setDraftForm((prev) => ({
                        ...prev,
                        full_narrative: e.target.value,
                      }))
                    }
                  />
                </div>
                <button type="submit" className="btn-primary">
                  Save as new version
                </button>
              </form>
            ) : (
              <div className="space-y-3">
                {[
                  ['Who', latest.who],
                  ['What', latest.what],
                  ['When', latest.when],
                  ['Where', latest.where],
                  ['Why', latest.why],
                  ['How', latest.how],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-md border border-ink-200 bg-ink-50 p-3">
                    <div className="text-xs font-semibold uppercase tracking-wide text-ink-400">
                      {label}
                    </div>
                    <p className="mt-1 text-sm text-ink-800">{value || '—'}</p>
                  </div>
                ))}
                <div className="rounded-md border border-ink-200 p-3">
                  <div className="text-xs font-semibold uppercase tracking-wide text-ink-400">
                    Full narrative
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-sm text-ink-800">
                    {latest.full_narrative || '—'}
                  </p>
                </div>
              </div>
            )}
          </section>

          {canDecide ? (
            <section className="card p-4">
              <h2 className="section-title mb-3">Reviewer decision</h2>
              <textarea
                className="input min-h-[90px]"
                placeholder="Required comment explaining approve / reject…"
                value={decisionComment}
                onChange={(e) => setDecisionComment(e.target.value)}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  className="btn-primary"
                  disabled={!commentOk}
                  onClick={() =>
                    runAction(
                      () =>
                        api.approveCase(token, Number(caseId), decisionComment.trim()),
                      'Case approved.',
                    )
                  }
                >
                  Approve
                </button>
                <button
                  type="button"
                  className="btn-danger"
                  disabled={!commentOk}
                  onClick={() =>
                    runAction(
                      () =>
                        api.rejectCase(token, Number(caseId), decisionComment.trim()),
                      'Rejected — returned to drafted for revision.',
                    )
                  }
                >
                  Reject
                </button>
              </div>
            </section>
          ) : null}

          <section className="card p-4">
            <h2 className="section-title mb-3">Recent audit</h2>
            {!audit.length ? (
              <p className="text-sm text-ink-500">No events yet.</p>
            ) : (
              <ul className="divide-y divide-ink-100">
                {audit.slice(0, 6).map((e) => (
                  <li key={e.id} className="py-2 text-sm">
                    <div className="font-semibold text-ink-800">{e.event_type}</div>
                    <div className="text-xs text-ink-400">
                      {new Date(e.created_at).toLocaleString()} · {e.actor_role || '—'}
                    </div>
                    <div className="text-ink-600">{e.summary}</div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}
