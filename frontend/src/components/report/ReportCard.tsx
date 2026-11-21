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
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Markdown } from "@/components/Markdown";
import { cn } from "@/lib/utils";

type Row = Record<string, string | number>;
export interface ReportChart {
  type: "stacked_bar_horizontal" | "bar" | "progress" | "line";
  unit?: string;
  series?: string[];
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
}

const fmt = (v: number) => Math.round(v).toLocaleString("ru-RU").replace(/,/g, " ");
const short = (v: number) => (Math.abs(v) >= 1000 ? `${Math.round(v / 1000)}k` : String(v));

function StackedH({ c }: { c: ReportChart }) {
  const series = c.series ?? [];
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
    <div className="h-[220px] w-full">
      <ResponsiveContainer>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 60 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey={c.x ?? "variant"} width={170} tick={{ fontSize: 12 }} />
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
    <div className="h-[200px] w-full">
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

function Chart({ c }: { c: ReportChart }) {
  if (c.type === "stacked_bar_horizontal") return <StackedH c={c} />;
  if (c.type === "bar") return <BarV c={c} />;
  if (c.type === "line") return <LineC c={c} />;
  return <Progress c={c} />;
}

function Table({ t }: { t: NonNullable<ReportSection["table"]> }) {
  const md = ["| " + t.columns.join(" | ") + " |", "|" + t.columns.map((_, i) => (i ? "---:" : "---")).join("|") + "|", ...t.rows.map((r) => "| " + r.join(" | ") + " |")].join("\n");
  return <Markdown text={md} />;
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
    <div ref={ref} className="flex min-w-0 flex-col gap-4 rounded-card border border-border bg-surface p-5 text-ink sm:p-6">
      <p className="m-0 font-display text-20 font-bold leading-snug">
        {report.verdict} {report.verdict_highlight && <span className="text-[#0F766E]">{report.verdict_highlight}</span>}
      </p>
      <div className={cn("grid gap-3", "grid-cols-2 lg:grid-cols-4", cueIds.some((c) => c.startsWith("kpi") || c.startsWith("verdict")) && "rounded-inner ring-2 ring-[#2DD4BF]")}>
        {report.kpis.map((k) => (
          <div key={k.label} className="rounded-inner border border-border p-3">
            <div className="text-13 text-text-3">{k.label}</div>
            <div className={cn("font-display text-22 font-bold tabular-nums", k.tone === "good" && "text-[#0F766E]", k.tone === "bad" && "text-danger")}>{k.value}</div>
            {k.sub && <div className="text-12 text-text-3">{k.sub}</div>}
          </div>
        ))}
      </div>
      {report.sections.filter(showSection).map((s) => (
        <section
          key={s.id}
          className={cn("flex flex-col gap-3 rounded-inner border border-border p-4", isActive(s.id) && "border-[#2DD4BF] bg-[#F0FDFA] ring-2 ring-[#2DD4BF]")}
        >
          {isActive(s.id) && compact && (
            <span className="self-start rounded-full bg-[#2DD4BF] px-2 py-0.5 text-12 font-bold text-[#042F2E]">● hozir aytilmoqda</span>
          )}
          <h3 className="m-0 text-16 font-bold">{s.title}</h3>
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
      {(!compact || full) && report.assumptions && <p className="m-0 text-12 text-text-3">{report.assumptions}</p>}
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
