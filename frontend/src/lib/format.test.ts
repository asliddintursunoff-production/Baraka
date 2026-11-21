import { describe, expect, it } from "vitest";

import { axisDateLabels, formatDateUz, formatMln, formatMlnAxis, groupMlnText } from "./format";

const sp = (s: string) => s.replace(/\u00A0/g, " ");

describe("formatDateUz", () => {
  it("formats tick styles with the year", () => {
    expect(formatDateUz("2026-11-01", "tickMonth")).toBe("Noy 2026");
    expect(formatDateUz("2026-12-01", "tickDay")).toBe("1-dek 2026");
    expect(formatDateUz("2026-06-15", "tickMonth", { year: false })).toBe("Iyun");
    expect(formatDateUz("2026-12-15", "tickDay", { year: false })).toBe("15-dek");
  });

  it("formats long and full styles", () => {
    // 2027-01-10 is a Sunday; the contract's "shanba" sample is 9-yanvar.
    expect(formatDateUz("2027-01-09", "long")).toBe("9-yanvar 2027, shanba");
    expect(formatDateUz("2027-01-10", "long")).toBe("10-yanvar 2027, yakshanba");
    expect(formatDateUz("2027-01-10", "full")).toBe("10-yanvar 2027");
    expect(formatDateUz("2026-11-23", "long")).toBe("23-noyabr 2026, dushanba");
    expect(formatDateUz("2026-11-22", "long")).toBe("22-noyabr 2026, yakshanba");
    expect(formatDateUz("2026-10-31", "full")).toBe("31-oktyabr 2026");
  });

  it("shows the year on the first tick and whenever it changes", () => {
    expect(
      axisDateLabels(["2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01"], "tickMonth"),
    ).toEqual(["Noy 2026", "Dek", "Yan 2027", "Fev"]);
    expect(axisDateLabels(["2026-12-15", "2027-01-01", "2027-01-15"], "tickDay")).toEqual([
      "15-dek 2026",
      "1-yan 2027",
      "15-yan",
    ]);
  });
});

describe("formatMlnAxis", () => {
  it("groups thousands with a space and uses a decimal comma", () => {
    expect(sp(formatMlnAxis(2000))).toBe("2 000 mln");
    expect(sp(formatMlnAxis(1439.5))).toBe("1 439,5 mln");
    expect(sp(formatMlnAxis(500))).toBe("500 mln");
    expect(sp(formatMlnAxis(12500))).toBe("12 500 mln");
    expect(formatMlnAxis(0)).toBe("0");
    expect(formatMlnAxis(-0.01)).toBe("0");
    expect(sp(formatMlnAxis(-250))).toBe("\u2212250 mln");
    expect(formatMlnAxis(2000)).not.toContain("2000");
  });

  it("formats tooltip amounts and backend labels", () => {
    expect(sp(formatMln(139.6))).toBe("139,6 mln");
    expect(sp(formatMln(2000))).toBe("2 000,0 mln");
    expect(sp(groupMlnText("Xavfsiz chegara · 1000 mln"))).toBe("Xavfsiz chegara · 1 000 mln");
  });
});
