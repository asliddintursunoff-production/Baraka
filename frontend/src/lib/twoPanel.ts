/**
 * Data preparation for the two-panel cash chart (history | forecast). Pure functions, no
 * Recharts, so the light wrapper and the tests can use them without loading the chart chunk.
 * Amounts are converted to mln only to position marks; dates stay ISO strings.
 */
import { axisDateLabels, toMln } from "./format";
import type { ForecastBlock, ForecastHistory } from "./types";

export const HISTORY_RANGES = [3, 6, 12] as const;
export type HistoryRange = (typeof HISTORY_RANGES)[number];
export const FORECAST_RANGES = [30, 60, 90] as const;
export type ForecastRange = (typeof FORECAST_RANGES)[number];

const DAY_MS = 86_400_000;

/** ISO date → whole days since 1970-01-01 (UTC, so no DST/timezone drift). */
export function dayNum(iso: string): number {
  const [y = 1970, m = 1, d = 1] = iso.slice(0, 10).split("-").map(Number);
  return Math.round(Date.UTC(y, m - 1, d) / DAY_MS);
}

export function isoFromDay(n: number): string {
  return new Date(n * DAY_MS).toISOString().slice(0, 10);
}

export function addMonthsIso(iso: string, months: number): string {
  const [y = 1970, m = 1, d = 1] = iso.slice(0, 10).split("-").map(Number);
  const target = new Date(Date.UTC(y, m - 1 + months, 1));
  const last = new Date(
    Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0),
  ).getUTCDate();
  target.setUTCDate(Math.min(d, last));
  return target.toISOString().slice(0, 10);
}

export interface HistoryRow {
  t: number;
  date: string;
  close: number;
}

export interface WeeklyRow {
  t: number;
  date: string;
  in: number;
  out: number;
}

export interface MarkerRow {
  t: number;
  date: string;
  label: string;
  close: number;
}

export interface HistoryData {
  rows: HistoryRow[];
  weekly: WeeklyRow[];
  markers: MarkerRow[];
}

/** The last `months` months of actual history, ending at `last_actual`. */
export function historyData(h: ForecastHistory, months: HistoryRange): HistoryData {
  const from = addMonthsIso(h.last_actual, -months);
  const rows = h.points
    .filter((p) => p.date > from && p.date <= h.last_actual)
    .map((p) => ({ t: dayNum(p.date), date: p.date, close: toMln(p.close) }));
  const byDate = new Map(rows.map((r) => [r.date, r.close]));
  const fromDay = dayNum(from);
  const weekly = h.weekly
    .filter((w) => dayNum(w.week) + 3 > fromDay && w.week <= h.last_actual)
    .map((w) => ({ t: dayNum(w.week) + 3, date: w.week, in: toMln(w.in), out: toMln(w.out) }));
  const markers = h.markers
    .filter((m) => byDate.has(m.date))
    .map((m) => ({ t: dayNum(m.date), date: m.date, label: m.label, close: byDate.get(m.date)! }));
  return { rows, weekly, markers };
}

export interface ForecastRow {
  t: number;
  date: string;
  display: string;
  /** Solid forecast line (null inside the data gap). */
  close: number | null;
  /** Dotted, estimated line inside the gap (null elsewhere). */
  est: number | null;
  band: [number, number];
  overlay?: number;
  /** Index in `series` (matches overlay / marker indices from the API). */
  i: number;
}

/** `days` days of forecast from `start` (the last actual day); the gap part is "estimated". */
export function forecastRows(
  f: ForecastBlock,
  days: ForecastRange,
  overlay?: string[] | null,
): ForecastRow[] {
  const start = f.start ?? f.series[0]?.date ?? "";
  const gapTo = f.gap?.to ?? null;
  return f.series
    .map((s, i) => ({ s, i }))
    .filter(({ s }) => s.date >= start)
    .slice(0, days + 1)
    .map(({ s, i }) => {
      const v = toMln(s.close);
      const inGap = gapTo !== null && s.date <= gapTo;
      const ov = overlay?.[i];
      return {
        t: dayNum(s.date),
        date: s.date,
        display: s.display,
        close: gapTo === null || s.date >= gapTo ? v : null,
        est: inGap ? v : null,
        band: [toMln(s.p10), toMln(s.p90)] as [number, number],
        overlay: ov !== undefined ? toMln(ov) : undefined,
        i,
      };
    });
}

const NICE = [1, 2, 2.5, 5, 10];

export function niceStep(range: number, target = 4): number {
  if (!(range > 0)) return 1;
  const raw = range / target;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const unit = NICE.find((n) => n * mag >= raw) ?? 10;
  return unit * mag;
}

export interface YDomain {
  min: number;
  max: number;
  ticks: number[];
}

/** One y-domain for both panels: visible data of both, 0 and the safe minimum. */
export function sharedDomain(values: number[], safeMin: number): YDomain {
  const finite = values.filter((v) => Number.isFinite(v));
  const hi = Math.max(0, safeMin, ...finite);
  const lo = Math.min(0, safeMin, ...finite);
  const step = niceStep(hi - lo);
  const max = Math.ceil((hi * 1.04) / step) * step || step;
  // Always keep a thin "Pul yetmaydigan zona" strip below 0.
  const min = lo < 0 ? Math.floor(lo / step) * step : -step * 0.4;
  const ticks: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step / 1000; v += step)
    ticks.push(Math.round(v * 1000) / 1000);
  return { min, max, ticks };
}

export function domainValues(history: HistoryRow[], forecast: ForecastRow[]): number[] {
  return [
    ...history.map((r) => r.close),
    ...forecast.flatMap((r) => [
      r.band[0],
      r.band[1],
      r.close ?? r.est ?? 0,
      ...(r.overlay !== undefined ? [r.overlay] : []),
    ]),
  ];
}

export interface Tick {
  t: number;
  label: string;
}

/** Month ticks for the history panel (1st of each month; every 2nd month for 12 months). */
export function monthTicks(rows: { t: number; date: string }[], months: number): Tick[] {
  const firsts = rows.filter((r) => r.date.endsWith("-01"));
  const every = months > 6 ? 2 : 1;
  const picked = firsts.filter((_r, i) => i % every === 0);
  const labels = axisDateLabels(
    picked.map((r) => r.date),
    "tickMonth",
  );
  return picked.map((r, i) => ({ t: r.t, label: labels[i]! }));
}

/** Day ticks for the forecast panel: start, then 1st (and 15th up to 60 days) of each month. */
export function dayTicks(rows: { t: number; date: string }[], days: number): Tick[] {
  const minGap = Math.max(6, Math.round(days / 6));
  const picked: { t: number; date: string }[] = [];
  rows.forEach((r, idx) => {
    const day = Number(r.date.slice(8, 10));
    const wanted = idx === 0 || day === 1 || (days <= 60 && day === 15);
    const prev = picked[picked.length - 1];
    if (wanted && (!prev || r.t - prev.t >= minGap)) picked.push(r);
  });
  const labels = axisDateLabels(
    picked.map((r) => r.date),
    "tickDay",
  );
  return picked.map((r, i) => ({ t: r.t, label: labels[i]! }));
}

/** "Ta'sischi kiritmasi 600,0 mln" → short label for the chart (full text in tooltip/table). */
export function shortLabel(text: string, max = 22): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}
