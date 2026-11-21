import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { apiGet } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface QualityPayload {
  status?: string | null;
  freshness?: string;
  period?: (string | null)[];
  recon: { month: string; metric: string; computed: string; reported: string; ok: boolean }[];
  flags: string[];
}

/** Per month: what we computed vs the file's own report (green = within 1 %). */
export function ReconTable({ rows, onlyBad = false }: { rows: QualityPayload["recon"]; onlyBad?: boolean }) {
  const shown = onlyBad ? rows.filter((r) => !r.ok) : rows;
  if (shown.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-14">
        <thead>
          <tr className="text-left text-12 uppercase tracking-[0.04em] text-text-3">
            <th className="py-2 pr-3 font-semibold">Oy</th>
            <th className="py-2 pr-3 font-semibold">Ko&apos;rsatkich</th>
            <th className="py-2 pr-3 text-right font-semibold">Biz hisobladik</th>
            <th className="py-2 pr-3 text-right font-semibold">Fayl hisoboti</th>
            <th className="py-2 font-semibold">Holat</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r) => (
            <tr key={`${r.month}-${r.metric}`} className="border-t border-border-subtle">
              <td className="py-2 pr-3">{r.month}</td>
              <td className="py-2 pr-3">{r.metric}</td>
              <td className="py-2 pr-3 text-right">{r.computed}</td>
              <td className="py-2 pr-3 text-right">{r.reported}</td>
              <td className={cn("py-2 font-semibold", r.ok ? "text-success" : "text-danger")}>{r.ok ? "✓ mos" : "✗ farq bor"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Sources page panel: reconciliation with the workbook's own reports + plausibility checks. */
export function ReconPanel({ q }: { q?: QualityPayload }) {
  if (!q || (q.recon.length === 0 && q.flags.length === 0 && !q.freshness)) return null;
  const bad = q.recon.filter((r) => !r.ok).length;
  return (
    <section aria-label="Solishtirish" className="flex flex-col gap-3 rounded-card border border-border bg-surface p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="m-0 font-display text-[19px] font-bold">Faylning o&apos;z hisobotlari bilan solishtirish</h2>
        <span
          className={cn(
            "rounded-pill px-3 py-1 text-13 font-bold",
            bad || q.flags.length ? "bg-danger-bg text-danger" : "bg-success-bg text-success",
          )}
        >
          {bad || q.flags.length ? "Tekshirish kerak" : "Hammasi mos"}
        </span>
      </div>
      {q.freshness && <p className="m-0 text-14 text-warning">{q.freshness.charAt(0).toUpperCase() + q.freshness.slice(1)}.</p>}
      {q.flags.map((f) => (
        <p key={f} className="m-0 rounded-inner bg-danger-bg p-3 text-14 text-danger">
          {f}
        </p>
      ))}
      <ReconTable rows={q.recon} />
    </section>
  );
}

/** Gate for data that does not reconcile: no forecasts or advice until it does. */
export function ReviewGate({ message, recon }: { message?: string; recon?: QualityPayload["recon"] }) {
  const q = useQuery({
    queryKey: ["sources"],
    queryFn: () => apiGet<{ quality?: QualityPayload }>("/api/sources"),
    enabled: !recon,
  });
  const rows = recon ?? q.data?.quality?.recon ?? [];
  const flags = q.data?.quality?.flags ?? [];
  return (
    <section
      aria-label="Ma'lumotni tekshirish kerak"
      className="box-border flex w-full max-w-[760px] flex-col gap-4 self-center rounded-[20px] border border-[#FECDCA] bg-surface p-8"
    >
      <span className="self-start rounded-pill bg-danger-bg px-3 py-[5px] text-14 font-bold text-danger">Tekshirish kerak</span>
      <h1 className="m-0 font-display text-26 font-bold">Jadvaldan o&apos;qigan raqamlar faylning o&apos;z hisobotlari bilan mos emas</h1>
      <p className="m-0 text-16 leading-[1.6] text-text-2">
        {message ||
          "Shuning uchun hozircha prognoz va maslahat bermayman: noto'g'ri raqam asosida qaror qabul qilish xavfli."}
      </p>
      {flags.map((f) => (
        <p key={f} className="m-0 rounded-inner bg-danger-bg p-3 text-14 text-danger">
          {f}
        </p>
      ))}
      <ReconTable rows={rows} onlyBad />
      <Link
        to="/sources"
        className="inline-flex min-h-tap items-center self-start rounded-btn bg-primary px-[18px] text-15 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white"
      >
        Ma&apos;lumotlar sahifasida ko&apos;rish
      </Link>
    </section>
  );
}
