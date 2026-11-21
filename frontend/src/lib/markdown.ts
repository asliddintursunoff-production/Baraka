/**
 * Tiny, dependency-free markdown parser for CFO answers (Part D2): `#`/`##`/`###` headings,
 * paragraphs, **bold**, *italic*, `code`, `- ` bullets, `1. ` numbered lists (the index is kept
 * apart from the text) and simple pipe tables. Output is plain data; the React renderer only
 * creates text nodes, so nothing from the model is ever injected as HTML.
 */

export type Inline = { kind: "text" | "bold" | "italic" | "code"; text: string };

export type MdBlock =
  | { type: "heading"; level: 1 | 2 | 3; inline: Inline[] }
  | { type: "paragraph"; lines: Inline[][] }
  | { type: "ul"; items: Inline[][] }
  | { type: "ol"; items: { index: number; inline: Inline[] }[] }
  | {
      type: "table";
      header: Inline[][];
      rows: Inline[][][];
      align: ("left" | "right" | "center")[];
    }
  | { type: "hr" };

const INLINE = /(\*\*[^*\n]+?\*\*|__[^_\n]+?__|`[^`\n]+`|\*[^*\s](?:[^*\n]*[^*\s])?\*)/g;

export function parseInline(text: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    const tok = m[0];
    const at = m.index ?? 0;
    if (at > last) out.push({ kind: "text", text: text.slice(last, at) });
    if (tok.startsWith("**") || tok.startsWith("__"))
      out.push({ kind: "bold", text: tok.slice(2, -2) });
    else if (tok.startsWith("`")) out.push({ kind: "code", text: tok.slice(1, -1) });
    else out.push({ kind: "italic", text: tok.slice(1, -1) });
    last = at + tok.length;
  }
  if (last < text.length) out.push({ kind: "text", text: text.slice(last) });
  return out;
}

const HEADING = /^(#{1,6})\s+(.*?)\s*#*\s*$/;
const BULLET = /^\s*[-*+•]\s+(.*)$/;
const NUMBERED = /^\s*(\d{1,3})[.)]\s+(.*)$/;
const HR = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
const TABLE_SEP = /^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function isTableLine(line: string): boolean {
  const t = line.trim();
  return t.startsWith("|") && t.indexOf("|", 1) > 0;
}

function cells(line: string): string[] {
  let t = line.trim();
  if (t.startsWith("|")) t = t.slice(1);
  if (t.endsWith("|")) t = t.slice(0, -1);
  return t.split("|").map((c) => c.trim());
}

function alignOf(cell: string): "left" | "right" | "center" {
  const c = cell.trim();
  if (c.startsWith(":") && c.endsWith(":")) return "center";
  if (c.endsWith(":")) return "right";
  return "left";
}

export function parseMarkdown(src: string): MdBlock[] {
  const lines = src.replace(/\r\n?/g, "\n").split("\n");
  const blocks: MdBlock[] = [];
  let para: Inline[][] | null = null;
  let list: Extract<MdBlock, { type: "ul" | "ol" }> | null = null;

  const close = () => {
    para = null;
    list = null;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    if (!line.trim()) {
      close();
      continue;
    }
    if (isTableLine(line)) {
      close();
      const rowsRaw: string[] = [];
      while (i < lines.length && isTableLine(lines[i]!)) rowsRaw.push(lines[i++]!);
      i--;
      const hasSep = rowsRaw.length > 1 && TABLE_SEP.test(rowsRaw[1]!);
      const header = cells(rowsRaw[0]!);
      const body = rowsRaw.slice(hasSep ? 2 : 1).filter((r) => !TABLE_SEP.test(r));
      const align = hasSep ? cells(rowsRaw[1]!).map(alignOf) : header.map(() => "left" as const);
      blocks.push({
        type: "table",
        header: header.map(parseInline),
        rows: body.map((r) => {
          const c = cells(r);
          return header.map((_h, ci) => parseInline(c[ci] ?? ""));
        }),
        align,
      });
      continue;
    }
    const h = HEADING.exec(line);
    if (h) {
      close();
      const level = Math.min(3, h[1]!.length) as 1 | 2 | 3;
      blocks.push({ type: "heading", level, inline: parseInline(h[2]!) });
      continue;
    }
    if (HR.test(line)) {
      close();
      blocks.push({ type: "hr" });
      continue;
    }
    const n = NUMBERED.exec(line);
    if (n) {
      para = null;
      const cur = list as Extract<MdBlock, { type: "ol" }> | null;
      if (cur?.type === "ol") {
        const prev = cur.items[cur.items.length - 1]!;
        cur.items.push({ index: prev.index + 1, inline: parseInline(n[2]!) });
      } else {
        const ol: Extract<MdBlock, { type: "ol" }> = {
          type: "ol",
          items: [{ index: Number(n[1]), inline: parseInline(n[2]!) }],
        };
        blocks.push(ol);
        list = ol;
      }
      continue;
    }
    const b = BULLET.exec(line);
    if (b) {
      para = null;
      const cur = list as Extract<MdBlock, { type: "ul" }> | null;
      if (cur?.type === "ul") cur.items.push(parseInline(b[1]!));
      else {
        const ul: Extract<MdBlock, { type: "ul" }> = { type: "ul", items: [parseInline(b[1]!)] };
        blocks.push(ul);
        list = ul;
      }
      continue;
    }
    // An indented line right after a list item continues that item.
    const curList = list as Extract<MdBlock, { type: "ul" | "ol" }> | null;
    if (curList && /^\s{2,}/.test(line)) {
      const extra = parseInline(` ${line.trim()}`);
      if (curList.type === "ol") curList.items[curList.items.length - 1]!.inline.push(...extra);
      else curList.items[curList.items.length - 1]!.push(...extra);
      continue;
    }
    list = null;
    const cur = para as Inline[][] | null;
    if (cur) cur.push(parseInline(line.trim()));
    else {
      const p: Inline[][] = [parseInline(line.trim())];
      blocks.push({ type: "paragraph", lines: p });
      para = p;
    }
  }
  return blocks;
}

/** Plain text of a markdown answer (aria labels, copy). */
export function inlineText(inline: Inline[]): string {
  return inline.map((t) => t.text).join("");
}
