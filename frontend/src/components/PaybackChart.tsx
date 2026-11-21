/**
 * Investment payback line (API_ADVISOR.md `payback_chart`): cumulative result per period,
 * zero line, a dot on the break-even period. `value` is used only to position marks; every
 * visible amount is the backend's preformatted `display`.
 */
import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface PaybackPoint {
  label: string;
  value: number;
  display: string;
}

export interface PaybackSeries {
  name: string;
  points: PaybackPoint[];
}

export interface PaybackChartProps {
  points: PaybackPoint[];
  breakEvenIndex?: number | null;
  breakEvenLabel?: string;
  series?: PaybackSeries[] | null;
}

const BASE = "#1D4ED8";
const OTHERS = ["#B54708", "#067647", "#B42318"];

interface Row {
  i: number;
  label: string;
  base: number;
  display: string;
  [key: string]: number | string;
}

function sameValues(a: PaybackPoint[], b: PaybackPoint[]): boolean {
  return a.length === b.length && a.every((p, i) => p.value === b[i]?.value);
}

function TooltipBox({
  active,
  payload,
  names,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
  names: string[];
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-lg bg-ink px-3 py-2 text-13 text-white shadow-lg">
      <div className="font-bold">{row.label}</div>
      <div className="text-[#D0D5DD]">{row.display}</div>
      {names.map((name, k) =>
        row[`d${k}`] !== undefined ? (
          <div key={name} className="text-[#D0D5DD]">
            {name}: {String(row[`d${k}`])}
          </div>
        ) : null,
      )}
    </div>
  );
}

export default function PaybackChart({ points, breakEvenIndex, breakEvenLabel, series }: PaybackChartProps) {
  const others = useMemo(() => (series ?? []).filter((s) => !sameValues(s.points, points)), [series, points]);

  const rows: Row[] = useMemo(
    () =>
      points.map((p, i) => {
        const row: Row = { i, label: p.label, base: p.value, display: p.display };
        others.forEach((s, k) => {
          const sp = s.points[i];
          if (sp) {
            row[`s${k}`] = sp.value;
            row[`d${k}`] = sp.display;
          }
        });
        return row;
      }),
    [points, others],
  );

  const n = Math.max(rows.length - 1, 0);
  const ticks = useMemo(() => {
    const step = Math.max(1, Math.ceil(n / 6));
    const out: number[] = [];
    for (let i = 0; i <= n; i += step) out.push(i);
    if (out[out.length - 1] !== n) out.push(n);
    return out;
  }, [n]);

  const be = breakEvenIndex != null ? rows[breakEvenIndex] : undefined;
  const last = rows[n];

  return (
    <div className="flex w-full flex-col gap-2">
      <div role="img" aria-label={breakEvenLabel || "Qoplanish grafigi"} className="w-full">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={rows} margin={{ top: 24, right: 16, bottom: 0, left: 16 }}>
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
            <YAxis hide domain={["dataMin", "dataMax"]} />
            <ReferenceLine y={0} stroke="#98A2B3" ifOverflow="extendDomain" />
            {others.map((s, k) => (
              <Line
                key={s.name}
                dataKey={`s${k}`}
                name={s.name}
                stroke={OTHERS[k % OTHERS.length]}
                strokeWidth={2}
                strokeDasharray="7 4"
                dot={false}
                isAnimationActive={false}
              />
            ))}
            <Line dataKey="base" stroke={BASE} strokeWidth={2.5} strokeLinejoin="round" dot={false} isAnimationActive={false} />
            {be && (
              <>
                <ReferenceLine x={be.i} stroke="#067647" strokeDasharray="3 4" />
                <ReferenceDot x={be.i} y={be.base} r={6} fill="#FFFFFF" stroke="#067647" strokeWidth={3} />
              </>
            )}
            {last && (
              <ReferenceDot
                x={last.i}
                y={last.base}
                r={4}
                fill={BASE}
                stroke="none"
                label={{ value: last.display, position: "top", fill: "#101828", fontSize: 12, fontWeight: 700 }}
              />
            )}
            <Tooltip
              content={<TooltipBox names={others.map((s) => s.name)} />}
              cursor={{ stroke: "#98A2B3", strokeDasharray: "3 3" }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-13 text-text-3">
        {breakEvenLabel && (
          <span className="inline-flex items-center gap-[6px] font-semibold text-success">
            <span className="h-[10px] w-[10px] rounded-[5px] border-[3px] border-success bg-surface" aria-hidden="true" />
            {breakEvenLabel}
          </span>
        )}
        {others.length > 0 &&
          (series ?? [])
            .filter((s) => !others.includes(s))
            .slice(0, 1)
            .map((s) => (
              <span key={s.name} className="inline-flex items-center gap-[6px]">
                <span className="h-[3px] w-4 bg-primary" aria-hidden="true" />
                {s.name}
              </span>
            ))}
        {others.map((s, k) => (
          <span key={s.name} className="inline-flex items-center gap-[6px]">
            <span
              className="h-0 w-4 border-t-2 border-dashed"
              style={{ borderColor: OTHERS[k % OTHERS.length] }}
              aria-hidden="true"
            />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}
