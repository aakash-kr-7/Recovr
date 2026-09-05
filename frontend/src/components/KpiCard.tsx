interface KpiCardProps {
  label: string;
  value: string;
  detail: string;
  positive?: boolean;
}

export function KpiCard({
  label,
  value,
  detail,
  positive = false,
}: KpiCardProps) {
  return (
    <section className="min-h-[112px] rounded-xsmall border border-slate-200 bg-white p-4">
      <p className="m-0 mb-2 text-slate-500 text-50 font-semibold">{label}</p>
      <strong
        className={`block text-300 tracking-tight ${
          positive ? "text-emerald-700" : "text-slate-900"
        }`}
      >
        {value}
      </strong>
      <small className="block mt-2 text-slate-400 text-25">{detail}</small>
    </section>
  );
}
