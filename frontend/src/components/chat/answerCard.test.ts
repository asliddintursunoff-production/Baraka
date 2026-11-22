/** Golden answers must render the ReportCard (never a plain text bubble), title exactly once. */
import { readFileSync } from "node:fs";
import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { Answer } from "@/lib/chatTypes";

import { AnswerCard } from "./AnswerCard";

const actions = { plans: {}, candidates: {}, approve: () => undefined, accept: () => undefined };

function golden(q: string): { answer: Answer; verdict: string } {
  const snap = JSON.parse(readFileSync(new URL(`../../../../backend/tests/golden_snapshots/${q}.json`, import.meta.url), "utf8"));
  const report = snap.ui_blocks.find((b: { type: string }) => b.type === "report");
  // the chat stores golden answers like this: headline + blocks, markdown "" when a report exists
  const answer = { verdict: "info", headline: report.verdict, reason: "", steps: [], blocks: snap.ui_blocks, markdown: "", chips: [] } as unknown as Answer;
  return { answer, verdict: report.verdict };
}

const render = (answer: Answer) =>
  renderToString(createElement(MemoryRouter, null, createElement(AnswerCard, { answer, messageId: 1, busy: false, onAsk: () => undefined, actions })));

describe("golden answers render a ReportCard", () => {
  for (const q of ["Q1", "Q2", "Q3", "Q4"]) {
    it(`${q}: card, KPI tiles, title once`, () => {
      const { answer, verdict } = golden(q);
      const html = render(answer);
      expect(html).toContain("rounded-card"); // the one card container
      expect(html).toContain("tabular-nums"); // KPI values
      const text = html.replace(/<[^>]+>/g, "").replace(/&#x27;/g, "'").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
      const head = verdict.slice(0, 40);
      expect(text.split(head).length - 1).toBe(1);
    });
  }
});
