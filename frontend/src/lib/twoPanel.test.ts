import { describe, expect, it } from "vitest";

import { dayTicks, forecastRows, sharedDomain } from "./twoPanel";
import type { ForecastBlock } from "./types";

const pt = (i: number, date: string, close: string) => ({
  i,
  date,
  label: "",
  close,
  p10: close,
  p90: close,
  display: "",
});

describe("twoPanel", () => {
  it("marks the data gap as estimated and joins the lines at the gap end", () => {
    const f = {
      series: [
        pt(0, "2026-10-31", "1000000000"),
        pt(1, "2026-11-01", "1100000000"),
        pt(2, "2026-11-02", "1200000000"),
      ],
      start: "2026-10-31",
      gap: { from: "2026-11-01", to: "2026-11-01", label: "Ma'lumot kiritilmagan" },
    } as unknown as ForecastBlock;
    const rows = forecastRows(f, 30);
    expect(rows.map((r) => r.est)).toEqual([1000, 1100, null]);
    expect(rows.map((r) => r.close)).toEqual([null, 1100, 1200]);
  });

  it("shares one domain that includes 0 and the safe minimum", () => {
    const d = sharedDomain([1200, 1450], 1000);
    expect(d.min).toBeLessThan(0);
    expect(d.max).toBeGreaterThanOrEqual(1450);
    expect(d.ticks).toContain(0);
  });

  it("puts the year on the first day tick", () => {
    const rows = ["2026-12-30", "2026-12-31", "2027-01-01"].map((date, k) => ({ t: k, date }));
    expect(dayTicks(rows, 30)[0]!.label).toBe("30-dek 2026");
  });
});
