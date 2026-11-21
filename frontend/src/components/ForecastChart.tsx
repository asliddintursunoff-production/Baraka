/**
 * Cash forecast (DESIGN.md): blue line, light-blue uncertainty band, red "Pul yetmaydigan
 * zona" below 0, dashed amber "Xavfsiz chegara", a callout on the hardest day and an
 * optional dashed scenario overlay. Every label text comes from the backend.
 */
import { useMemo } from "react";
import {
  Area,
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

import { toMln } from "@/lib/format";
import type { SeriesPoint } from "@/lib/types";

export interface ForecastChartProps {
  series: SeriesPoint[];
  days: number;
  safeMin: string;
  safeLabel: string;
  lowestIndex: number;
  calloutTitle: string;
  calloutText: string;
  overlay?: string[] | null;
  overlayColor?: string;
  overlayMarker?: number | null;
  ariaLabel: string;
  bandFill?: number;
}

const NICE = [5, 10, 20, 25, 50, 100, 200, 500, 1000];

function niceStep(range: number): number {
  const raw = range / 3;
  return NICE.find((s) => s >= raw) ?? 1000;
}

function CalloutLabel(props: {
  viewBox?: { x?: number; y?: number };
  title: string;
  text: string;
  width: number;
}) {
  const x = props.viewBox?.x ?? 0;
  const y = props.viewBox?.y ?? 0;
  const w = Math.max(196, Math.max(props.title.length, props.text.length) * 7.2 + 24);
  const flip = x + 12 + w > props.width - 10;
  const bx = flip ? x - 12 - w : x + 12;
  const by = Math.max(4, y - 40);
  return (
    <g>
      <rect x={bx} y={by} width={w} height={46} rx={8} fill="#101828" />
      <text x={bx + 12} y={by + 19} fontSize={13} fill="#FFFFFF" fontWeight={700}>
        {props.title}
      </text>
      <text x={bx + 12} y={by + 37} fontSize={12} fill="#D0D5DD">
        {props.text}
      </text>
    </g>
  );
}

interface Row {
  i: number;
  label: string;
  display: string;
  close: number;
  band: [number, number];
  overlay?: number;
}

function TooltipBox({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-lg bg-ink px-3 py-2 text-13 text-white shadow-lg">
      <div className="font-bold">{row.label}</div>
      <div className="text-[#D0D5DD]">Kassada: {row.display}</div>
    </div>
  );
}

export default function ForecastChart(p: ForecastChartProps) {
  const rows: Row[] = useMemo(
    () =>
      p.series.slice(0, p.days + 1).map((s, i) => ({
        i,
        label: s.label,
        display: s.display,
        close: toMln(s.close),
        band: [toMln(s.p10), toMln(s.p90)],
        overlay: p.overlay?.[i] !== undefined ? toMln(p.overlay[i]!) : undefined,
      })),
    [p.series, p.days, p.overlay],
  );

  const safe = toMln(p.safeMin);
  const values = rows.flatMap((r) => [r.band[0], r.band[1], r.overlay ?? r.close]);
  const maxV = Math.max(...values, safe);
  const minV = Math.min(...values, 0);
  const step = niceStep(maxV - Math.min(minV, 0));
  const yMax = Math.ceil(maxV / step) * step;
  const yMin = Math.min(-step, Math.floor(minV / step) * step);
  const yTicks: number[] = [];
  for (let v = 0; v <= yMax; v += step) yTicks.push(v);

  const n = rows.length - 1;
  const ticks = useMemo(() => {
    const out = [0];
    const minGap = Math.max(3, Math.round(n / 9));
    rows.forEach((_r, i) => {
      const day = Number(p.series[i]?.date.slice(8, 10));
      if ((day === 1 || day === 10 || day === 25 || i === p.lowestIndex) && i - out[out.length - 1]! >= minGap) {
        out.push(i);
      }
    });
    if (n - out[out.length - 1]! >= minGap) out.push(n);
    return out;
  }, [rows, n, p.series, p.lowestIndex]);

  const lowest = rows[p.lowestIndex];
  const overlayMarker = p.overlayMarker != null ? rows[p.overlayMarker] : undefined;

  return (
    <div role="img" aria-label={p.ariaLabel} className="w-full">
      <ResponsiveContainer width="100%" aspect={830 / 300} minHeight={220}>
        <ComposedChart data={rows} margin={{ top: 16, right: 14, bottom: 0, left: 0 }}>
          <ReferenceArea
            y1={yMin}
            y2={0}
            fill="#FEF3F2"
            fillOpacity={1}
            ifOverflow="extendDomain"
            label={{
              value: "Pul yetmaydigan zona",
              position: "insideBottomLeft",
              fill: "#B42318",
              fontSize: 12,
              fontWeight: 600,
            }}
          />
          <CartesianGrid vertical={false} stroke="#EAECF0" />
          <XAxis
            dataKey="i"
            type="number"
            domain={[0, n]}
            ticks={ticks}
            tickFormatter={(i: number) => rows[i]?.label ?? ""}
            tick={{ fontSize: 12, fill: "#5D6679" }}
            axisLine={false}
            tickLine={false}
            interval={0}
          />
          <YAxis
            domain={[yMin, yMax]}
            ticks={yTicks}
            tickFormatter={(v: number) => (v === 0 ? "0" : `${v} mln`)}
            tick={{ fontSize: 12, fill: "#5D6679" }}
            axisLine={false}
            tickLine={false}
            width={64}
          />
          <ReferenceLine y={0} stroke="#98A2B3" />
          <Area
            dataKey="band"
            stroke="none"
            fill="#1D4ED8"
            fillOpacity={p.bandFill ?? 0.1}
            isAnimationActive={false}
            activeDot={false}
          />
          <Line
            dataKey="close"
            stroke="#1D4ED8"
            strokeWidth={2.5}
            strokeLinejoin="round"
            dot={false}
            isAnimationActive={false}
          />
          {p.overlay && (
            <Line
              dataKey="overlay"
              stroke={p.overlayColor ?? "#B42318"}
              strokeWidth={2.5}
              strokeDasharray="7 4"
              strokeLinejoin="round"
              dot={false}
              isAnimationActive={false}
            />
          )}
          <ReferenceLine
            y={safe}
            stroke="#B54708"
            strokeWidth={1.5}
            strokeDasharray="6 5"
            label={{
              value: p.safeLabel,
              position: "insideTopRight",
              fill: "#B54708",
              fontSize: 12,
              fontWeight: 600,
            }}
          />
          {lowest && !p.overlay && (
            <>
              <ReferenceLine x={lowest.i} stroke="#B54708" strokeDasharray="3 4" />
              <ReferenceDot
                x={lowest.i}
                y={lowest.close}
                r={6}
                fill="#FFFFFF"
                stroke="#B54708"
                strokeWidth={3}
                label={<CalloutLabel title={p.calloutTitle} text={p.calloutText} width={830} />}
              />
            </>
          )}
          {overlayMarker?.overlay !== undefined && (
            <ReferenceDot
              x={overlayMarker.i}
              y={overlayMarker.overlay}
              r={6}
              fill="#FFFFFF"
              stroke={p.overlayColor ?? "#B42318"}
              strokeWidth={3}
            />
          )}
          <ReferenceDot x={0} y={rows[0]?.close ?? 0} r={5} fill="#1D4ED8" stroke="none" />
          <Tooltip content={<TooltipBox />} cursor={{ stroke: "#98A2B3", strokeDasharray: "3 3" }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
