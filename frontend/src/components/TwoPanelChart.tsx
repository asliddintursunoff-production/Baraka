/**
 * Two-panel cash chart (Part B): "O'tgan davr — haqiqiy" | "Prognoz — keyingi N kun".
 * Side by side from 1024px with a thin divider, stacked below (history on top). Both panels
 * share one y-domain. Titles, captions and labels come from the backend; the Recharts part is
 * a lazy chunk (TwoPanelPlots), so this wrapper, the legend and the table view stay light.
 */
import { lazy, Suspense, useMemo, useState, type ReactNode } from "react";

import { Skeleton } from "@/components/States";
import { RichText } from "@/components/RichText";
import { formatDateUz, formatMln, toMln } from "@/lib/format";
import {
  dayNum,
  dayTicks,
  domainValues,
  FORECAST_RANGES,
  forecastRows,
  HISTORY_RANGES,
  historyData,
  monthTicks,
  sharedDomain,
  type ForecastRange,
  type HistoryRange,
} from "@/lib/twoPanel";
import type { ForecastBlock, HardestDay } from "@/lib/types";
import { cn } from "@/lib/utils";

const HistoryPlot = lazy(() => import("./TwoPanelPlots").then((m) => ({ default: m.HistoryPlot })));
const ForecastPlot = lazy(() =>
  import("./TwoPanelPlots").then((m) => ({ default: m.ForecastPlot })),
);

export interface TwoPanelChartProps {
  forecast: ForecastBlock;
  days: ForecastRange;
  onDaysChange: (d: ForecastRange) => void;
  /** Scenario overlay ("agar"), indexed like `forecast.series`. */
  overlay?: string[] | null;
  overlayColor?: string;
  /** Series index of the scenario marker. */
  overlayMarker?: number | null;
  overlayLegend?: string;
}

function SegToggle<T extends number>({
  options,
  value,
  onChange,
  unit,
  label,
}: {
  options: readonly T[];
  value: T;
  onChange: (v: T) => void;
  unit: string;
  label: string;
}) {
  return (
    <div role="group" aria-label={label} className="flex gap-[2px] rounded-btn bg-[#F2F4F7] p-1">
      {options.map((o) => (
        <button
          key={o}
          type="button"
          aria-pressed={o === value}
          onClick={() => onChange(o)}
          className={cn(
            "min-h-9 min-w-[52px] rounded-lg border-0 px-2 text-14",
            o === value
              ? "bg-surface font-bold text-ink shadow-[0_1px_2px_rgba(16,24,40,.1)]"
              : "bg-transparent font-semibold text-text-3",
          )}
        >
          {o} {unit}
        </button>
      ))}
    </div>
  );
}

function PressButton({
  on,
  onClick,
  children,
}: {
  on: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={cn(
        "inline-flex min-h-9 items-center gap-2 rounded-btn border px-3 text-13 font-semibold",
        on
          ? "border-primary bg-primary-soft text-primary"
          : "border-border-input bg-surface text-text-3",
      )}
    >
      {children}
    </button>
  );
}

type Swatch =
  "solid" | "solidInk" | "band" | "dashedSafe" | "dotted" | "dashedOverlay" | "barIn" | "barOut";

function LegendItem({
  kind,
  color,
  children,
}: {
  kind: Swatch;
  color?: string;
  children: ReactNode;
}) {
  const sw: Record<Swatch, ReactNode> = {
    solid: <span className="h-[3px] w-[18px] rounded-sm bg-primary" />,
    solidInk: <span className="h-[2px] w-[18px] rounded-sm bg-ink" />,
    band: <span className="h-[10px] w-[18px] rounded-sm bg-[#DCE6FB]" />,
    dashedSafe: <span className="h-0 w-[18px] border-t-2 border-dashed border-warning" />,
    dotted: <span className="h-0 w-[18px] border-t-[3px] border-dotted border-primary" />,
    dashedOverlay: (
      <span className="h-0 w-[18px] border-t-[3px] border-dashed" style={{ borderColor: color }} />
    ),
    barIn: <span className="h-3 w-3 rounded-[3px] bg-primary" />,
    barOut: <span className="h-3 w-3 rounded-[3px] bg-warning-accent" />,
  };
  return (
    <span className="inline-flex items-center gap-2">
      <span className="inline-flex w-[18px] items-center justify-center" aria-hidden="true">
        {sw[kind]}
      </span>
      {children}
    </span>
  );
}

function PanelHead({
  title,
  caption,
  extra,
  control,
}: {
  title: string;
  caption: ReactNode;
  extra?: string;
  control: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="m-0 font-display text-17 font-bold">{title}</h3>
        {control}
      </div>
      <p className="m-0 text-14 leading-normal text-text-3">{caption}</p>
      {extra && <p className="m-0 text-14 font-semibold leading-normal text-warning">{extra}</p>}
    </div>
  );
}

const TH =
  "sticky top-0 bg-surface py-2 text-left text-12 font-semibold uppercase tracking-label text-text-4";

function captionDays(title: string | undefined): number {
  return Number(title?.match(/(\d+) kun/)?.[1] ?? 60);
}

export function TwoPanelChart(p: TwoPanelChartProps) {
  const f = p.forecast;
  const [months, setMonths] = useState<HistoryRange>(3);
  const [weekly, setWeekly] = useState(false);
  const [table, setTable] = useState(false);

  const hist = useMemo(
    () => (f.history ? historyData(f.history, months) : null),
    [f.history, months],
  );
  const rows = useMemo(() => forecastRows(f, p.days, p.overlay), [f, p.days, p.overlay]);
  const safe = toMln(f.safe_min);
  const domain = useMemo(
    () => sharedDomain(domainValues(hist?.rows ?? [], rows), safe),
    [hist, rows, safe],
  );
  const hTicks = useMemo(() => (hist ? monthTicks(hist.rows, months) : []), [hist, months]);
  const fTicks = useMemo(() => dayTicks(rows, p.days), [rows, p.days]);

  const baseDays = captionDays(f.title);
  const summary = f.summaries[String(p.days)];
  const title = f.title
    ? f.title.replace(/\d+(?= kun)/, String(p.days))
    : `Prognoz — keyingi ${p.days} kun`;
  const caption: ReactNode =
    p.days === baseDays && f.caption ? (
      f.caption
    ) : summary ? (
      <RichText text={summary.text} />
    ) : (
      (f.caption ?? "")
    );
  const captionText =
    p.days === baseDays && f.caption
      ? f.caption
      : (summary?.text ?? f.caption ?? "").replace(/\*\*/g, "");

  const hardDate =
    p.days === baseDays && f.hardest ? f.hardest.date : (summary?.lowest_date ?? f.hardest?.date);
  const hardest: HardestDay | null = hardDate
    ? f.hardest?.date === hardDate
      ? f.hardest
      : {
          date: hardDate,
          label: formatDateUz(hardDate, "long"),
          balance: summary?.lowest_display ?? "",
          payments: [],
        }
    : null;
  const hardestRow = rows.find((r) => r.date === hardDate) ?? null;
  const overlayRow =
    p.overlayMarker != null ? (rows.find((r) => r.i === p.overlayMarker) ?? null) : null;
  const hasOverlay = Boolean(p.overlay && p.overlay.length > 0);
  const today = f.today;
  const fallback = <Skeleton className="h-[260px]" />;

  const historyPanel = f.history && hist && (
    <div className="flex min-w-0 flex-col gap-3 lg:pr-5">
      <PanelHead
        title={f.history.title}
        caption={f.history.caption}
        control={
          <SegToggle
            options={HISTORY_RANGES}
            value={months}
            onChange={setMonths}
            unit="oy"
            label="O'tgan davr muddati"
          />
        }
      />
      {table ? (
        <div className="max-h-[300px] overflow-auto">
          <table className="w-full border-collapse text-14">
            <caption className="sr-only">{f.history.title}</caption>
            <thead>
              <tr>
                <th scope="col" className={TH}>
                  Sana
                </th>
                <th scope="col" className={cn(TH, "text-right")}>
                  Haqiqiy qoldiq
                </th>
              </tr>
            </thead>
            <tbody>
              {hist.rows.map((r) => {
                const marks = hist.markers.filter((m) => m.date === r.date);
                return (
                  <tr key={r.date} className="border-t border-border-subtle">
                    <td className="py-2">
                      {formatDateUz(r.date, "full")}
                      {marks.map((m) => (
                        <span key={m.label} className="block text-12 font-semibold text-text-3">
                          {m.label}
                        </span>
                      ))}
                    </td>
                    <td className="py-2 text-right font-semibold">{formatMln(r.close)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <Suspense fallback={fallback}>
          <HistoryPlot
            rows={hist.rows}
            weekly={hist.weekly}
            markers={hist.markers}
            ticks={hTicks}
            domain={domain}
            showWeekly={weekly}
            ariaLabel={`${f.history.title}. ${f.history.caption}`}
          />
        </Suspense>
      )}
      {!table && hist.weekly.length > 0 && (
        <div className="flex flex-wrap items-center gap-[14px] text-13 text-text-3">
          <PressButton on={weekly} onClick={() => setWeekly((w) => !w)}>
            Haftalik tushum va xarajat
          </PressButton>
          {weekly && (
            <>
              <LegendItem kind="barIn">Tushum</LegendItem>
              <LegendItem kind="barOut">Xarajat</LegendItem>
            </>
          )}
        </div>
      )}
    </div>
  );

  const forecastPanel = (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-3",
        historyPanel && "border-t border-border pt-5 lg:border-t-0 lg:pl-5 lg:pt-0",
      )}
    >
      <PanelHead
        title={title}
        caption={caption}
        extra={f.beyond || undefined}
        control={
          <SegToggle
            options={FORECAST_RANGES}
            value={p.days}
            onChange={p.onDaysChange}
            unit="kun"
            label="Prognoz muddati"
          />
        }
      />
      {table ? (
        <div className="max-h-[300px] overflow-auto">
          <table className="w-full border-collapse text-14">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr>
                <th scope="col" className={TH}>
                  Sana
                </th>
                <th scope="col" className={cn(TH, "text-right")}>
                  Prognoz
                </th>
                <th scope="col" className={cn(TH, "text-right")}>
                  Ehtimoliy oraliq
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const hard = r.date === hardDate;
                return (
                  <tr
                    key={r.date}
                    className={cn("border-t border-border-subtle", hard && "bg-warning-bg")}
                  >
                    <td className="py-2">
                      {formatDateUz(r.date, "full")}
                      {r.close === null && (
                        <span className="block text-12 text-text-4">Taxminiy (ma'lumot yo'q)</span>
                      )}
                      {hard &&
                        hardest?.payments.map((pay, i) => (
                          <span key={i} className="block text-12 font-semibold text-warning">
                            {pay.title} · {pay.amount}
                          </span>
                        ))}
                    </td>
                    <td className="py-2 text-right font-semibold">{r.display}</td>
                    <td className="whitespace-nowrap py-2 text-right text-text-3">
                      {formatMln(r.band[0])} – {formatMln(r.band[1])}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <Suspense fallback={fallback}>
          <ForecastPlot
            rows={rows}
            ticks={fTicks}
            domain={domain}
            safeMin={safe}
            todayT={today ? dayNum(today) : null}
            gap={f.gap ?? null}
            gapFromT={f.gap ? dayNum(f.gap.from) : null}
            gapToT={f.gap ? dayNum(f.gap.to) : null}
            hardest={hardest}
            hardestRow={hardestRow}
            overlayColor={p.overlayColor}
            overlayRow={overlayRow}
            hasOverlay={hasOverlay}
            ariaLabel={`${title}. ${captionText}`}
          />
        </Suspense>
      )}
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      <div
        className={cn(
          "grid grid-cols-1 gap-5",
          historyPanel && "lg:grid-cols-2 lg:gap-0 lg:divide-x lg:divide-border",
        )}
      >
        {historyPanel}
        {forecastPanel}
      </div>
      <div className="flex flex-wrap items-center gap-x-[18px] gap-y-2 text-13 text-text-3">
        {f.history && <LegendItem kind="solidInk">Haqiqiy qoldiq</LegendItem>}
        <LegendItem kind="solid">Prognoz</LegendItem>
        <LegendItem kind="band">Ehtimoliy oraliq</LegendItem>
        <LegendItem kind="dashedSafe">Xavfsiz chegara</LegendItem>
        {f.gap && <LegendItem kind="dotted">Taxminiy (ma'lumot yo'q)</LegendItem>}
        {hasOverlay && p.overlayLegend && (
          <LegendItem kind="dashedOverlay" color={p.overlayColor}>
            {p.overlayLegend}
          </LegendItem>
        )}
        <span className="ml-auto">
          <PressButton on={table} onClick={() => setTable((t) => !t)}>
            Jadval ko'rinishi
          </PressButton>
        </span>
      </div>
    </div>
  );
}
