import { Bar, BarChart, LabelList, ResponsiveContainer, XAxis } from "recharts";

import { toMln } from "@/lib/format";
import type { Dashboard } from "@/lib/types";

/** "Tushum va xarajat" bars; the label above each pair is the monthly net (from backend). */
export default function MonthlyBars({ months }: { months: Dashboard["monthly"] }) {
  const data = months.map((m) => ({
    label: m.label,
    inflow: toMln(m.inflow),
    outflow: toMln(m.outflow),
    profit: m.profit_label,
  }));
  const aria = months
    .map((m) => `${m.label}: tushum ${m.inflow_display}, xarajat ${m.outflow_display}`)
    .join("; ");
  return (
    <div role="img" aria-label={aria}>
      <ResponsiveContainer width="100%" aspect={2}>
        <BarChart data={data} barGap={2} barCategoryGap="30%" margin={{ top: 22, right: 8, bottom: 0, left: 8 }}>
          <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#5D6679" }} axisLine={{ stroke: "#D0D5DD" }} tickLine={false} />
          <Bar dataKey="inflow" fill="#1D4ED8" radius={[3, 3, 0, 0]} isAnimationActive={false}>
            <LabelList
              dataKey="profit"
              position="top"
              offset={8}
              style={{ fontSize: 11, fill: "#344054", fontWeight: 600 }}
            />
          </Bar>
          <Bar dataKey="outflow" fill="#F79009" radius={[3, 3, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
