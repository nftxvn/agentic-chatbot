const STATUS_PRESENTATION = {
  open: { label: 'Terbuka', classes: 'bg-amber-500/10 text-amber-500 border-amber-500/20' },
  in_progress: { label: 'Diproses', classes: 'bg-sky-500/10 text-sky-500 border-sky-500/20' },
  resolved: { label: 'Selesai', classes: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' },
}

export function TicketStatusBadge({ status }) {
  const presentation = STATUS_PRESENTATION[status] ?? {
    label: status,
    classes: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  }

  return (
    <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full border ${presentation.classes}`}>
      {presentation.label}
    </span>
  )
}
