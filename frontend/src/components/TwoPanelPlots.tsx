/**
 * Recharts part of the two-panel cash chart (lazy chunk, like ForecastChart). Data, ticks and
 * the shared y-domain are prepared in `lib/twoPanel.ts`; this file only draws.
 */
import type { ReactNode } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatDateUz, formatMln, formatMlnAxis } from "@/lib/format";
import type { ForecastRow, HistoryRow, MarkerRow, Tick, WeeklyRow, YDomain } from "@/lib/twoPanel";
import { shortLabel } from "@/lib/twoPanel";
import type { ForecastGap, HardestDay } from "@/lib/types";

export const COLORS = {
  actual: "#101828",
  forecast: "#1D4ED8",
  band: "#1D4ED8",
  safe: "#B54708",
  gap: "#F2F4F7",
  danger: "#B42318",
  dangerBg: "#FEF3F2",
  grid: "#EAECF0",
  axis: "#5D6679",
  inflow: "#1D4ED8",
  outflow: "#F79009",
} as const;

const PLOT_HEIGHT = 260;
const Y_WIDTH = 72;
const MARGIN = { top: 24, right: 14, bottom: 0, left: 0 };
const TICK = { fontSize: 12, fill: COLORS.axis };

function YAxisShared({ domain }: { domain: YDomain }) {
  return (
    <YAxis
      type="number"
      domain={[domain.min, domain.max]}
      ticks={domain.ticks}
      tickFormatter={formatMlnAxis}
      tick={TICK}
      axisLine={false}
      tickLine={false}
      width={Y_WIDTH}
      allowDataOverflow
    />
  );
}

function tickFormatter(ticks: Tick[]) {
  const map = new Map(ticks.map((t) => [t.t, t.label]));
  return (t: number) => map.get(t) ?? "";
}

function DangerZone({ domain }: { domain: YDomain }) {
  if (domain.min >= 0) return null;
  return (
    <ReferenceArea
      y1={domain.min}
      y2={0}
      fill={COLORS.dangerBg}
      fillOpacity={1}
      ifOverflow="hidden"
    />
  );
}

function TipBox({ children }: { children: ReactNode }) {
  return (
    <div className="max-w-[260px] rounded-lg bg-ink px-3 py-2 text-13 text-white shadow-lg">
      {children}
    </div>
  );
}

/* ---------------------------------------------------------------- history */

function HistoryTip({
  active,
  payload,
  markers,
}: {
  active?: boolean;
  payload?: { payload: HistoryRow }[];
  markers?: MarkerRow[];
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const here = (markers ?? []).filter((m) => m.date === row.date);
  return (
    <TipBox>
      <div className="font-bold">{formatDateUz(row.date, "long")}</div>
      <div className="text-[#D0D5DD]">Haqiqiy qoldiq: {formatMln(row.close)}</div>
      {here.map((m) => (
        <div key={m.label} className="pt-1 font-semibold text-[#FEC84B]">
          {m.label}
        </div>
      ))}
    </TipBox>
  );
}

export interface HistoryPlotProps {
  rows: HistoryRow[];
  weekly: WeeklyRow[];
  markers: MarkerRow[];
  ticks: Tick[];
  domain: YDomain;
  showWeekly: boolean;
  ariaLabel: string;
}

export function HistoryPlot(p: HistoryPlotProps) {
  const first = p.rows[0]?.t ?? 0;
  const last = p.rows[p.rows.length - 1]?.t ?? 1;
  const fmt = tickFormatter(p.ticks);
  return (
    <div role="img" aria-label={p.ariaLabel} className="w-full">
      <ResponsiveContainer width="100%" height={PLOT_HEIGHT}>
        <ComposedChart data={p.rows} margin={MARGIN}>
          <DangerZone domain={p.domain} />
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis
            dataKey="t"
            type="number"
            domain={[first, last]}
            ticks={p.ticks.map((t) => t.t)}
            tickFormatter={fmt}
            tick={TICK}
            axisLine={false}
            tickLine={false}
            interval={0}
          />
          <YAxisShared domain={p.domain} />
          <ReferenceLine y={0} stroke="#98A2B3" />
          <Line
            dataKey="close"
            stroke={COLORS.actual}
            strokeWidth={2}
            strokeLinejoin="round"
            dot={false}
            isAnimationActive={false}
          />
          {p.markers.map((m) => (
            <ReferenceDot
              key={`${m.date}-${m.label}`}
              x={m.t}
              y={m.close}
              r={5}
              fill="#FFFFFF"
              stroke={COLORS.actual}
              strokeWidth={2}
              label={{
                value: shortLabel(m.label),
                position: "top",
                fill: "#344054",
                fontSize: 11,
                fontWeight: 600,
              }}
            />
          ))}
          <Tooltip
            content={<HistoryTip markers={p.markers} />}
            cursor={{ stroke: "#98A2B3", strokeDasharray: "3 3" }}
          />
        </ComposedChart>
      </ResponsiveContainer>
      {p.showWeekly && (
        <ResponsiveContainer width="100%" height={96}>
          <BarChart
            data={p.weekly}
            margin={{ top: 8, right: MARGIN.right, bottom: 0, left: 0 }}
            barGap={1}
          >
            <XAxis dataKey="t" type="number" domain={[first - 4, last + 4]} hide />
            <YAxis width={Y_WIDTH} tick={false} axisLine={false} tickLine={false} />
            <Bar
              dataKey="in"
              fill={COLORS.inflow}
              radius={[2, 2, 0, 0]}
              isAnimationActive={false}
              barSize={4}
            />
            <Bar
              dataKey="out"
              fill={COLORS.outflow}
              radius={[2, 2, 0, 0]}
              isAnimationActive={false}
              barSize={4}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

/* --------------------------------------------------------------- forecast */

function ForecastTip({
  active,
  payload,
  hardest,
}: {
  active?: boolean;
  payload?: { payload: ForecastRow }[];
  hardest?: HardestDay | null;
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  const isHard = hardest != null && hardest.date === row.date;
  const estimated = row.close === null;
  return (
    <TipBox>
      <div className="font-bold">{isHard ? hardest.label : formatDateUz(row.date, "long")}</div>
      <div className="text-[#D0D5DD]">
        {estimated ? "Taxminiy" : "Prognoz"}: {isHard ? hardest.balance : row.display}
      </div>
      <div className="text-[#D0D5DD]">
        Ehtimoliy oraliq: {formatMln(row.band[0])} – {formatMln(row.band[1])}
      </div>
      {isHard && hardest.payments.length > 0 && (
        <ul className="m-0 list-none p-0 pt-1">
          {hardest.payments.map((pay, i) => (
            <li key={i} className="flex justify-between gap-3">
              <span>{pay.title}</span>
              <strong className="whitespace-nowrap">{pay.amount}</strong>
            </li>
          ))}
        </ul>
      )}
    </TipBox>
  );
}

export interface ForecastPlotProps {
  rows: ForecastRow[];
  ticks: Tick[];
  domain: YDomain;
  safeMin: number;
  todayT?: number | null;
  gap?: ForecastGap | null;
  gapFromT?: number | null;
  gapToT?: number | null;
  hardest?: HardestDay | null;
  hardestRow?: ForecastRow | null;
  overlayColor?: string;
  overlayRow?: ForecastRow | null;
  hasOverlay: boolean;
  ariaLabel: string;
}

export function ForecastPlot(p: ForecastPlotProps) {
  const first = p.rows[0]?.t ?? 0;
  const last = p.rows[p.rows.length - 1]?.t ?? 1;
  const fmt = tickFormatter(p.ticks);
  const hard = p.hardestRow;
  const hardY = hard ? (hard.close ?? hard.est) : null;
  return (
    <div role="img" aria-label={p.ariaLabel} className="w-full">
      <ResponsiveContainer width="100%" height={PLOT_HEIGHT}>
        <ComposedChart data={p.rows} margin={MARGIN}>
          <DangerZone domain={p.domain} />
          {p.gap && p.gapFromT != null && p.gapToT != null && (
            <ReferenceArea
              x1={Math.max(first, p.gapFromT - 0.5)}
              x2={Math.min(last, p.gapToT)}
              fill={COLORS.gap}
              fillOpacity={1}
              ifOverflow="hidden"
              label={{
                value: p.gap.label,
                position: "insideTop",
                fill: "#475467",
                fontSize: 11,
                fontWeight: 600,
                offset: 8,
              }}
            />
          )}
          <CartesianGrid vertical={false} stroke={COLORS.grid} />
          <XAxis
            dataKey="t"
            type="number"
            domain={[first, last]}
            ticks={p.ticks.map((t) => t.t)}
            tickFormatter={fmt}
            tick={TICK}
            axisLine={false}
            tickLine={false}
            interval={0}
          />
          <YAxisShared domain={p.domain} />
          <ReferenceLine y={0} stroke="#98A2B3" />
          <Area
            dataKey="band"
            stroke="none"
            fill={COLORS.band}
            fillOpacity={0.1}
            isAnimationActive={false}
            activeDot={false}
          />
          <Line
            dataKey="est"
            stroke={COLORS.forecast}
            strokeWidth={2}
            strokeDasharray="2 4"
            strokeLinecap="round"
            dot={false}
            isAnimationActive={false}
            activeDot={false}
          />
          <Line
            dataKey="close"
            stroke={COLORS.forecast}
            strokeWidth={2.5}
            strokeLinejoin="round"
            dot={false}
            isAnimationActive={false}
          />
          {p.hasOverlay && (
            <Line
              dataKey="overlay"
              stroke={p.overlayColor ?? COLORS.danger}
              strokeWidth={2.5}
              strokeDasharray="7 4"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive={false}
            />
          )}
          <ReferenceLine
            y={p.safeMin}
            stroke={COLORS.safe}
            strokeWidth={1.5}
            strokeDasharray="6 5"
          />
          {p.todayT != null && p.todayT >= first && p.todayT <= last && (
            <ReferenceLine
              x={p.todayT}
              stroke="#475467"
              strokeWidth={1.5}
              label={{
                value: "Bugun",
                position: "top",
                fill: "#344054",
                fontSize: 12,
                fontWeight: 700,
              }}
            />
          )}
          {hard && hardY != null && !p.hasOverlay && (
            <ReferenceDot
              x={hard.t}
              y={hardY}
              r={6}
              fill="#FFFFFF"
              stroke={COLORS.safe}
              strokeWidth={3}
              label={
                p.hardest
                  ? {
                      value: p.hardest.balance,
                      position: "bottom",
                      fill: COLORS.safe,
                      fontSize: 12,
                      fontWeight: 700,
                    }
                  : undefined
              }
            />
          )}
          {p.overlayRow?.overlay !== undefined && (
            <ReferenceDot
              x={p.overlayRow.t}
              y={p.overlayRow.overlay}
              r={6}
              fill="#FFFFFF"
              stroke={p.overlayColor ?? COLORS.danger}
              strokeWidth={3}
            />
          )}
          <Tooltip
            content={<ForecastTip hardest={p.hardest ?? null} />}
            cursor={{ stroke: "#98A2B3", strokeDasharray: "3 3" }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
