import { describe, expect, it } from "vitest";

import { inlineText, parseInline, parseMarkdown } from "./markdown";

describe("parseMarkdown", () => {
  it("keeps the list index separate from text that starts with a date", () => {
    const blocks = parseMarkdown(
      "1. 10-dekabr: ish haqini to'lang\n2. 15-dekabr: ijarani kechiktiring",
    );
    expect(blocks).toHaveLength(1);
    const ol = blocks[0]!;
    expect(ol.type).toBe("ol");
    if (ol.type !== "ol") return;
    expect(ol.items.map((i) => i.index)).toEqual([1, 2]);
    expect(inlineText(ol.items[0]!.inline)).toBe("10-dekabr: ish haqini to'lang");
    expect(inlineText(ol.items[1]!.inline)).toBe("15-dekabr: ijarani kechiktiring");
  });

  it("parses headings, paragraphs, bullets and tables", () => {
    const md = [
      "## Xulosa",
      "Kassada **139,6 mln** qoladi.",
      "Bu *taxminiy* raqam.",
      "",
      "- birinchi",
      "- ikkinchi",
      "",
      "| Sana | Summa |",
      "|---|---:|",
      "| 10-yanvar | 63,3 mln |",
    ].join("\n");
    const blocks = parseMarkdown(md);
    expect(blocks.map((b) => b.type)).toEqual(["heading", "paragraph", "ul", "table"]);
    const p = blocks[1]!;
    if (p.type === "paragraph") {
      expect(p.lines).toHaveLength(2);
      expect(p.lines[0]).toEqual([
        { kind: "text", text: "Kassada " },
        { kind: "bold", text: "139,6 mln" },
        { kind: "text", text: " qoladi." },
      ]);
      expect(p.lines[1]![1]).toEqual({ kind: "italic", text: "taxminiy" });
    }
    const t = blocks[3]!;
    if (t.type === "table") {
      expect(t.header.map(inlineText)).toEqual(["Sana", "Summa"]);
      expect(t.align).toEqual(["left", "right"]);
      expect(t.rows[0]!.map(inlineText)).toEqual(["10-yanvar", "63,3 mln"]);
    }
  });

  it("leaves HTML and stray markers as plain text", () => {
    expect(parseInline("<b>x</b> 2 * 3")).toEqual([{ kind: "text", text: "<b>x</b> 2 * 3" }]);
  });
});
