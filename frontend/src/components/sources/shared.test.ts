import { describe, expect, it } from "vitest";

import type { Proposals, SourceProposal } from "@/lib/sourcesTypes";

import { mergeProposals, normalizeProposals, parseAmount, safePath } from "./shared";

const source = (id: number, title: string): SourceProposal => ({
  id,
  title,
  kind: "google_sheet",
  summary: "",
  sheets: [
    {
      title: "S",
      rows: 1,
      rows_display: "1",
      header_row: 1,
      kind: "k",
      kind_label: "K",
      recognized: "",
      columns: [],
    },
  ],
});

const proposals = (over: Partial<Proposals>): Proposals => normalizeProposals(over);

describe("parseAmount", () => {
  it("accepts grouped so'm amounts", () => {
    expect(parseAmount("48 200 000")).toBe("48200000");
    expect(parseAmount("48\u00a0200\u202f000")).toBe("48200000");
    expect(parseAmount("350000,50")).toBe("350000.50");
  });
  it("rejects anything that is not a plain number", () => {
    expect(parseAmount("")).toBeNull();
    expect(parseAmount("48,2 mln")).toBeNull();
    expect(parseAmount("-5")).toBeNull();
    expect(parseAmount("1.2.3")).toBeNull();
  });
});

describe("safePath", () => {
  it("follows same-origin paths only", () => {
    expect(safePath("/", "/x")).toBe("/");
    expect(safePath("/sources", "/x")).toBe("/sources");
    expect(safePath("//evil.example", "/x")).toBe("/x");
    expect(safePath("https://evil.example", "/x")).toBe("/x");
    expect(safePath(undefined, "/x")).toBe("/x");
  });
});

describe("mergeProposals", () => {
  it("appends new sources and replaces a re-picked one in place", () => {
    const prev = proposals({
      sources: [source(1, "A"), source(2, "B")],
      field_options: [{ value: "date", label: "Sana" }],
      issues_preview: [{ source_id: 2, sheet: "S", row: 4, message: "old", action_label: "x" }],
      opening_balance_hint: { amount_display: "1", date_display: "d" },
    });
    const next = proposals({
      sources: [source(2, "B2"), source(3, "C")],
      field_options: [
        { value: "date", label: "To'lov sanasi" },
        { value: "ignore", label: "E'tiborsiz qoldirish" },
      ],
      issues_preview: [{ source_id: 3, sheet: "S", row: 9, message: "new", action_label: "y" }],
      needs_opening_balance: true,
    });
    const merged = mergeProposals(prev, next);
    expect(merged.sources.map((s) => s.title)).toEqual(["A", "B2", "C"]);
    expect(merged.field_options).toEqual([
      { value: "date", label: "To'lov sanasi" },
      { value: "ignore", label: "E'tiborsiz qoldirish" },
    ]);
    expect(merged.issues_preview.map((i) => i.message)).toEqual(["new"]);
    expect(merged.needs_opening_balance).toBe(true);
    expect(merged.opening_balance_hint).toEqual({ amount_display: "1", date_display: "d" });
  });

  it("fills missing arrays", () => {
    const merged = mergeProposals(null, {} as Proposals);
    expect(merged.sources).toEqual([]);
    expect(merged.kind_options).toEqual([]);
    expect(merged.needs_opening_balance).toBe(false);
  });
});
