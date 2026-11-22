/** Golden report card: one component for chat and Live (verdict, KPI tiles, charts, tables,
 * actions, assumptions, PDF). Live passes `activeCue` (the section being spoken) and `compact`. */
import { FileDown } from "lucide-react";
import { useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Markdown } from "@/components/Markdown";
import { cn } from "@/lib/utils";

type Row = Record<string, string | number>;
export interface ReportChart {
  type: "stacked_bar_horizontal" | "bar" | "progress" | "line" | "line_multi" | "progress_list" | "waterfall" | "bar_grouped";
  start?: { label: string; value: number };
  end?: { label: string; value: number };
  steps?: { label: string; value: number }[];
  target_line?: number;
  ref_lines?: { y: number; label: string; color: string }[];
  marker?: { x: string; label: string };
  group_colors?: Record<string, string>;
  x_labels?: string[];
  zero_line?: boolean;
  threshold?: number;
  items?: { label: string; value: number; note?: string }[];
  unit?: string;
  series?: string[] | { name: string; color: string; data: number[] }[];
  colors?: string[];
  x?: string;
  y?: string;
  data?: Row[];
  highlight?: string;
  now?: number;
  plan?: number;
  hire_second_at?: number;
  label_now?: string;
  label_plan?: string;
  note?: string;
}
export interface ReportSection {
  id: string;
  title: string;
  chart?: ReportChart;
  table?: { columns: string[]; rows: string[][]; highlight_last?: boolean };
  actions?: string[];
  note?: string;
}
export interface Report {
  id: string;
  type: "report";
  verdict: string;
  verdict_highlight?: string;
  period?: string;
  kpis: { label: string; value: string; sub?: string; tone?: "good" | "bad" }[];
  sections: ReportSection[];
  assumptions?: string;
  source?: string;
}

const fmt = (v: number) => Math.round(v).toLocaleString("ru-RU").replace(/,/g, " ");
const short = (v: number) => (Math.abs(v) >= 1000 ? `${Math.round(v / 1000)}k` : String(v));

function StackedH({ c }: { c: ReportChart }) {
  const series = (c.series ?? []).filter((x): x is string => typeof x === "string");
  const data = c.data ?? [];
  const keep = c.highlight ?? series[series.length - 1] ?? "";
  return (
    <div className="flex flex-col gap-2">
      {data.map((row) => {
        const total = series.reduce((s, k) => s + Number(row[k] ?? 0), 0) || 1;
        const good = Number(row[keep] ?? 0);
        const best = Math.max(...data.map((r) => Number(r[keep] ?? 0)));
        const worst = Math.min(...data.map((r) => Number(r[keep] ?? 0)));
        return (
          <div key={String(row[c.x ?? "kanal"])} className="grid grid-cols-[minmax(90px,170px)_1fr_auto] items-center gap-3">
            <span className="truncate text-14 font-semibold">{String(row[c.x ?? "kanal"])}</span>
            <div className="flex h-7 overflow-hidden rounded-[8px]">
              {series.map((k, i) => {
                const v = Number(row[k] ?? 0);
                return (
                  <span
                    key={k}
                    title={`${k}: ${fmt(v)}`}
                    className="flex items-center justify-center text-12 font-semibold text-white"
                    style={{ width: `${(v / total) * 100}%`, background: c.colors?.[i] ?? "#94A3B8" }}
                  >
                    {v / total > 0.08 ? short(v) : ""}
                  </span>
                );
              })}
            </div>
            <span className={cn("min-w-[64px] text-right text-15 font-bold tabular-nums", good === worst && good !== best ? "text-danger" : "text-[#0F766E]")}>
              {fmt(good)}
            </span>
          </div>
        );
      })}
      <div className="flex flex-wrap gap-4 pt-1 text-13 text-text-3">
        {series.map((k, i) => (
          <span key={k} className="inline-flex items-center gap-1">
            <span className="h-3 w-3 rounded-[3px]" style={{ background: c.colors?.[i] }} />
            {k}
          </span>
        ))}
      </div>
    </div>
  );
}

function BarV({ c }: { c: ReportChart }) {
  const data = (c.data ?? []).map((r) => ({ ...r }));
  return (
    <div className="h-[200px] w-full lg:h-[240px]">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 60 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey={c.x ?? "variant"} width={120} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => fmt(Number(v))} />
          <Bar dataKey={c.y ?? "qiymat"} radius={4}>
            {data.map((r, i) => (
              <Cell key={i} fill={String(r.color ?? "#2DD4BF")} />
            ))}
            <LabelList dataKey={c.y ?? "qiymat"} position="right" formatter={(v) => fmt(Number(v))} style={{ fontSize: 12 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function LineC({ c }: { c: ReportChart }) {
  return (
    <div className="h-[200px] w-full lg:h-[240px]">
      <ResponsiveContainer>
        <LineChart data={c.data ?? []} margin={{ left: 0, right: 16, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis dataKey={c.x ?? "oy"} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={40} />
          <Tooltip formatter={(v) => `${String(v).replace(".", ",")} ${c.unit ?? ""}`} />
          <Line type="monotone" dataKey={c.y ?? "qiymat"} stroke="#0F766E" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function Progress({ c }: { c: ReportChart }) {
  const bar = (v: number, color: string) => (
    <div className="h-4 w-full overflow-hidden rounded-full bg-[#F2F4F7]">
      <div className="h-full rounded-full" style={{ width: `${Math.min(100, (v ?? 0) * 100)}%`, background: color }} />
    </div>
  );
  return (
    <div className="flex flex-col gap-3 text-14 text-text-2">
      <span>{c.label_now}</span>
      {bar(c.now ?? 0, "#F59E0B")}
      <span>{c.label_plan}</span>
      {bar(c.plan ?? 0, "#14B8A6")}
      {c.note && <span className="text-13 text-text-3">{c.note}</span>}
    </div>
  );
}

function LineMulti({ c }: { c: ReportChart }) {
  const series = (c.series ?? []).filter((x): x is { name: string; color: string; data: number[] } => typeof x !== "string");
  const data = (c.x_labels ?? []).map((x, i) => {
    const row: Row = { x };
    for (const s of series) row[s.name] = s.data[i] ?? 0;
    return row;
  });
  return (
    <div className="h-[200px] w-full lg:h-[240px]">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ left: 0, right: 24, top: 12 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis dataKey="x" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={40} />
          <Tooltip formatter={(v) => `${String(v).replace(".", ",")} ${c.unit ?? ""}`} />
          {(c.ref_lines ?? []).map((r) => (
            <ReferenceLine key={r.label} y={r.y} stroke={r.color} strokeDasharray="5 4" label={{ value: r.label, position: "insideTopLeft", fontSize: 11, fill: r.color }} />
          ))}
          {c.zero_line && <ReferenceLine y={0} stroke="#98A2B3" />}
          {c.marker && <ReferenceLine x={c.marker.x} stroke="#0F766E" label={{ value: c.marker.label, position: "insideTopRight", fontSize: 11, fill: "#0F766E" }} />}
          {series.map((s) => (
            <Line key={s.name} type="monotone" dataKey={s.name} stroke={s.color} strokeWidth={2.5} dot={!!c.ref_lines} />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <div className="flex flex-wrap gap-4 text-13 text-text-3">
        {series.map((s) => (
          <span key={s.name} className="inline-flex items-center gap-1">
            <span className="h-3 w-3 rounded-[3px]" style={{ background: s.color }} />
            {s.name} ({String(s.data[s.data.length - 1] ?? 0).replace(".", ",")} mln)
          </span>
        ))}
      </div>
    </div>
  );
}

function ProgressList({ c }: { c: ReportChart }) {
  const thr = c.threshold ?? 0.85;
  return (
    <div className="flex flex-col gap-3">
      {(c.items ?? []).map((it) => (
        <div key={it.label} className="flex flex-col gap-1">
          <div className="flex justify-between text-14">
            <span className="font-semibold">{it.label}</span>
            <span className="text-text-3">{it.note}</span>
          </div>
          <div className="relative h-3 w-full rounded-full bg-[#F2F4F7]">
            <div className="h-full rounded-full" style={{ width: `${Math.min(100, it.value * 100)}%`, background: it.value >= 0.8 ? "#F59E0B" : "#14B8A6" }} />
            <span className="absolute top-[-3px] h-[18px] w-[2px] bg-danger" style={{ left: `${thr * 100}%` }} />
          </div>
        </div>
      ))}
      {c.note && <span className="text-13 text-text-3">{c.note}</span>}
    </div>
  );
}

function Waterfall({ c }: { c: ReportChart }) {
  const start = c.start ?? { label: "", value: 0 };
  const end = c.end ?? { label: "", value: 0 };
  const stepsIn = c.steps ?? [];
  const bases = stepsIn.map((_, i) => start.value + stepsIn.slice(0, i).reduce((s, x) => s + x.value, 0));
  const rows = [
    { label: start.label, base: 0, val: start.value, color: "#94A3B8", text: String(start.value).replace(".", ",") },
    ...stepsIn.map((st, i) => ({
      label: st.label,
      base: bases[i] ?? 0,
      val: st.value,
      color: "#14B8A6",
      text: `+${st.value.toFixed(2).replace(".", ",")}`,
    })),
    { label: end.label, base: 0, val: end.value, color: "#0F766E", text: end.value.toFixed(1).replace(".", ",") },
  ];
  const lo = Math.floor((start.value * 0.96) / 5) * 5;
  const hi = Math.ceil((Math.max(end.value, c.target_line ?? 0) * 1.01) / 5) * 5;
  const y = (v: number) => ((hi - v) / (hi - lo)) * 100;
  return (
    <div className="flex flex-col gap-1">
      <div className="relative h-[220px] w-full border-b border-border">
        {c.target_line && (
          <div className="absolute left-0 right-0 border-t-2 border-dashed border-[#F59E0B]" style={{ top: `${y(c.target_line)}%` }}>
            <span className="absolute -top-5 left-0 text-12 font-semibold text-[#B45309]">Maqsad</span>
          </div>
        )}
        <div className="absolute inset-0 flex items-stretch gap-2 px-1">
          {rows.map((r) => {
            const top = y(r.base + r.val);
            const bottom = r.base ? y(r.base) : 100;
            return (
              <div key={r.label} className="relative flex-1">
                <div className="absolute left-0 right-0 rounded-[4px]" style={{ top: `${top}%`, height: `${Math.max(1, bottom - top)}%`, background: r.color }} />
                <span className="absolute left-0 right-0 text-center text-12 font-bold" style={{ top: `calc(${top}% - 18px)` }}>
                  {r.text}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <div className="flex gap-2 px-1">
        {rows.map((r) => (
          <span key={r.label} className="flex-1 text-center text-11 text-text-3">
            {r.label}
          </span>
        ))}
      </div>
    </div>
  );
}

function BarGrouped({ c }: { c: ReportChart }) {
  const keys = Object.keys(c.group_colors ?? {});
  return (
    <div className="h-[200px] w-full lg:h-[240px]">
      <ResponsiveContainer>
        <BarChart data={c.data ?? []} margin={{ left: 0, right: 8, top: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis dataKey={c.x ?? "label"} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={36} />
          <Tooltip formatter={(v) => `${String(v).replace(".", ",")} ${c.unit ?? ""}`} />
          {keys.map((k) => (
            <Bar key={k} dataKey={k} fill={c.group_colors?.[k]} radius={3} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function Chart({ c }: { c: ReportChart }) {
  if (c.type === "waterfall") return <Waterfall c={c} />;
  if (c.type === "bar_grouped") return <BarGrouped c={c} />;
  if (c.type === "line_multi") return <LineMulti c={c} />;
  if (c.type === "progress_list") return <ProgressList c={c} />;
  if (c.type === "stacked_bar_horizontal") return <StackedH c={c} />;
  if (c.type === "bar") return <BarV c={c} />;
  if (c.type === "line") return <LineC c={c} />;
  return <Progress c={c} />;
}

function Table({ t, limit = 6 }: { t: NonNullable<ReportSection["table"]>; limit?: number }) {
  const [all, setAll] = useState(false);
  const rows = all ? t.rows : t.rows.slice(0, limit);
  const num = (v: string) => /^[−\-+]?[\d\s\u00a0\u202f.,]+(%| so'm| mln)?$/.test(v.trim());
  return (
    <div className="flex flex-col gap-2">
      <div className="-mx-5 overflow-x-auto px-5 sm:mx-0 sm:px-0">
        <table className="w-full min-w-max border-collapse text-14">
          <thead>
            <tr>
              {t.columns.map((c, i) => (
                <th
                  key={i}
                  scope="col"
                  className={cn(
                    "whitespace-nowrap border-b border-[#E5E7EB] px-3 py-2 text-12 font-semibold text-text-3",
                    i === 0 ? "sticky left-0 z-[1] bg-surface text-left" : "text-right",
                  )}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={ri} className={cn(t.highlight_last && ri === t.rows.length - 1 && "font-semibold")}>
                {r.map((v, i) => (
                  <td
                    key={i}
                    className={cn(
                      "border-b border-[#F2F4F7] px-3 py-2 align-top",
                      i === 0 ? "sticky left-0 z-[1] bg-surface text-left" : "whitespace-nowrap text-right tabular-nums",
                      i > 0 && !num(v) && "text-left",
                      /^[−-]\d/.test(v.trim()) && "text-danger",
                    )}
                  >
                    {v.replace(/\*\*/g, "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {t.rows.length > limit && (
        <button type="button" onClick={() => setAll((v) => !v)} className="self-start border-0 bg-transparent p-0 text-14 font-semibold text-primary">
          {all ? "Kamroq ko'rsatish" : `Hammasini ko'rish (${t.rows.length})`}
        </button>
      )}
    </div>
  );
}

export function ReportCard({
  report,
  activeCue,
  compact = false,
}: {
  report: Report;
  activeCue?: string | null;
  compact?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [full, setFull] = useState(false);
  const cueIds = (activeCue ?? "").split("+");
  const isActive = (id: string) => cueIds.some((c) => c && (id === c || id.startsWith(c)));
  const showSection = (s: ReportSection) => !compact || full || open[s.id] || isActive(s.id);
  return (
    <div ref={ref} className="flex min-w-0 flex-col gap-5 rounded-card border border-[#E5E7EB] bg-surface p-5 text-ink">
      <h3 className="m-0 text-[19px] font-semibold leading-snug [overflow-wrap:anywhere]">
        {report.verdict} {report.verdict_highlight && <span className="text-[#0F766E]">{report.verdict_highlight}</span>}
      </h3>
      <div className={cn("grid gap-3", "grid-cols-2 lg:grid-cols-4", cueIds.some((c) => c.startsWith("kpi") || c.startsWith("verdict")) && "rounded-inner ring-2 ring-[#2DD4BF]")}>
        {report.kpis.map((k) => (
          <div key={k.label} className="flex min-w-0 flex-col gap-0.5 rounded-inner bg-[#F9FAFB] p-3">
            <div className="text-12 text-text-3">{k.label}</div>
            <div
              className={cn(
                "text-22 font-semibold leading-tight tabular-nums [overflow-wrap:anywhere]",
                k.tone === "good" && "text-success",
                k.tone === "bad" && "text-danger",
                (k.tone as string) === "warn" && "text-warning",
              )}
            >
              {k.value}
            </div>
            {k.sub && <div className="text-12 text-text-4">{k.sub}</div>}
          </div>
        ))}
      </div>
      {report.sections.filter(showSection).map((s) => (
        <section
          key={s.id}
          className={cn("flex min-w-0 flex-col gap-3 border-t border-[#F2F4F7] pt-4", isActive(s.id) && "-mx-2 rounded-inner border-t-0 bg-[#F0FDFA] px-2 py-3 ring-2 ring-[#2DD4BF]")}
        >
          {isActive(s.id) && compact && (
            <span className="self-start rounded-full bg-[#2DD4BF] px-2 py-0.5 text-12 font-bold text-[#042F2E]">● hozir aytilmoqda</span>
          )}
          <h4 className="m-0 text-15 font-semibold [overflow-wrap:anywhere]">{s.title}</h4>
          {s.chart && <Chart c={s.chart} />}
          {s.table && !(compact && !full && s.chart) && <Table t={s.table} />}
          {s.actions && (
            <ol className="m-0 flex flex-col gap-1 pl-5 text-15 leading-relaxed">
              {s.actions.map((a, i) => (
                <li key={i}>
                  <Markdown text={a} />
                </li>
              ))}
            </ol>
          )}
          {s.note && <p className="m-0 text-14 text-text-2">{s.note}</p>}
        </section>
      ))}
      {compact && !full && (
        <div className="flex flex-wrap gap-2">
          {report.sections
            .filter((s) => !showSection(s))
            .map((s) => (
              <button key={s.id} type="button" onClick={() => setOpen((o) => ({ ...o, [s.id]: true }))} className="rounded-inner bg-[#F2F4F7] px-3 py-1.5 text-13 font-semibold">
                ▸ {(s.title.split("(")[0] ?? s.title).trim()}
              </button>
            ))}
          <button type="button" onClick={() => setFull(true)} className="rounded-inner bg-[#0F766E] px-3 py-1.5 text-13 font-semibold text-white">
            To'liq hisobot
          </button>
        </div>
      )}
      {((!compact || full) && report.assumptions) || report.source ? (
        <div className="flex flex-col gap-1 border-t border-[#F2F4F7] pt-3 text-13 text-text-3">
          {(!compact || full) && report.assumptions && (
            <details>
              <summary className="flex min-h-tap cursor-pointer items-center font-semibold md:min-h-8">Taxminlar</summary>
              <p className="m-0 pb-2 leading-relaxed">{report.assumptions}</p>
            </details>
          )}
          {report.source && (
            <details>
              <summary className="flex min-h-tap cursor-pointer items-center font-semibold md:min-h-8">
                Manba · Ishonch: {/taxmin/i.test(`${report.assumptions ?? ""} ${report.period ?? ""}`) ? "O'rta" : "Yuqori"}
              </summary>
              <p className="m-0 pb-2 leading-relaxed">
                {report.source}
                {report.period ? ` · ${report.period}` : ""}
              </p>
            </details>
          )}
        </div>
      ) : null}
      {(!compact || full) && (
        <button
          type="button"
          onClick={() => printReport(ref.current)}
          className="inline-flex items-center gap-1 self-start rounded-pill border border-border px-3 py-1 text-13 text-text-3 hover:text-ink print:hidden"
        >
          <FileDown size={14} /> Hisobot (PDF)
        </button>
      )}
    </div>
  );
}

function printReport(el: HTMLElement | null): void {
  if (!el) return;
  const w = window.open("", "_blank", "width=1000,height=1100");
  if (!w) return;
  const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style')).map((n) => n.outerHTML).join("");
  w.document.write(`<!doctype html><html><head><meta charset="utf-8"><title>Baraka — hisobot</title>${styles}<style>body{padding:24px;background:#fff}</style></head><body>${el.outerHTML}</body></html>`);
  w.document.close();
  w.onload = () => {
    w.focus();
    w.print();
  };
}
