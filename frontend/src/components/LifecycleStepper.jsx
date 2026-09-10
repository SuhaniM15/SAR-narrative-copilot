const STEPS = ['open', 'drafted', 'under_review', 'approved']

export default function LifecycleStepper({ status }) {
  if (status === 'rejected') {
    return (
      <div className="flex flex-wrap gap-2">
        {['open', 'drafted', 'under_review'].map((step) => (
          <span
            key={step}
            className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700"
          >
            {step}
          </span>
        ))}
        <span className="rounded-full border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700">
          rejected
        </span>
      </div>
    )
  }

  const currentIdx = Math.max(0, STEPS.indexOf(status))
  return (
    <div className="flex flex-wrap gap-2">
      {STEPS.map((step, idx) => {
        let cls =
          'rounded-full border border-ink-200 bg-ink-50 px-3 py-1 text-xs font-semibold text-ink-500'
        if (idx < currentIdx) {
          cls =
            'rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700'
        } else if (idx === currentIdx) {
          cls =
            'rounded-full border border-brand-700 bg-brand-700 px-3 py-1 text-xs font-semibold text-white'
        }
        return (
          <span key={step} className={cls}>
            {step}
          </span>
        )
      })}
    </div>
  )
}
