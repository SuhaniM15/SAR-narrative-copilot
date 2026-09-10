const STATUS_STYLES = {
  open: 'bg-sky-50 text-sky-800 border-sky-200',
  drafted: 'bg-amber-50 text-amber-800 border-amber-200',
  under_review: 'bg-violet-50 text-violet-800 border-violet-200',
  approved: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  rejected: 'bg-rose-50 text-rose-800 border-rose-200',
}

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || 'bg-ink-50 text-ink-700 border-ink-200'
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${style}`}
    >
      {status || 'unknown'}
    </span>
  )
}
