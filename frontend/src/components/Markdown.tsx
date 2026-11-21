/**
 * Renders CFO markdown answers (lib/markdown.ts) with plain React text nodes: no
 * dangerouslySetInnerHTML, so anything that is not supported markdown shows as escaped text.
 */
import { Fragment, useMemo } from "react";

import { parseMarkdown, type Inline, type MdBlock } from "@/lib/markdown";
import { cn } from "@/lib/utils";

function plain(items: Inline[]): string {
  return items.map((i) => ("text" in i ? String((i as { text: string }).text) : "")).join("");
}

/** A numeric cell ("71 121 526", "−4,2 mln", "36,2%") is right-aligned; a negative is red. */
function numCell(items: Inline[]): { num: boolean; neg: boolean } {
  const t = plain(items).trim();
  const num = /^[−\-+]?[\d\s.,]+(\s*(mln|mlrd|ming|so'm|%|oy|kun|dona|porsiya))?(\s*\/\s*\w+)?$/i.test(t) && /\d/.test(t);
  return { num, neg: num && /^[−-]/.test(t) };
}

function Inlines({ items }: { items: Inline[] }) {
  return (
    <>
      {items.map((t, i) => {
        switch (t.kind) {
          case "bold":
            return (
              <strong key={i} className="font-bold text-ink">
                {t.text}
              </strong>
            );
          case "italic":
            return <em key={i}>{t.text}</em>;
          case "code":
            return (
              <code key={i} className="rounded bg-[#F2F4F7] px-1 text-[0.92em]">
                {t.text}
              </code>
            );
          default:
            return <Fragment key={i}>{t.text}</Fragment>;
        }
      })}
    </>
  );
}

const ALIGN = { left: "text-left", right: "text-right", center: "text-center" } as const;

function Block({ block }: { block: MdBlock }) {
  switch (block.type) {
    case "heading":
      return block.level === 3 ? (
        <h4 className="m-0 pt-1 font-display text-17 font-bold text-ink">
          <Inlines items={block.inline} />
        </h4>
      ) : (
        <h3
          className={cn(
            "m-0 pt-1 font-display font-bold text-ink",
            block.level === 1 ? "text-22" : "text-20",
          )}
        >
          <Inlines items={block.inline} />
        </h3>
      );
    case "paragraph":
      return (
        <p className="m-0">
          {block.lines.map((l, i) => (
            <Fragment key={i}>
              {i > 0 && <br />}
              <Inlines items={l} />
            </Fragment>
          ))}
        </p>
      );
    case "ul":
      return (
        <ul className="m-0 list-disc pl-5 marker:text-text-4">
          {block.items.map((it, i) => (
            <li key={i} className="pl-1">
              <Inlines items={it} />
            </li>
          ))}
        </ul>
      );
    case "ol":
      return (
        <ol className="m-0 flex list-none flex-col gap-[6px] p-0" start={block.items[0]?.index}>
          {block.items.map((it) => (
            <li key={it.index} value={it.index} className="flex items-baseline gap-2">
              <span className="min-w-[1.6em] shrink-0 select-none text-right font-bold tabular-nums text-text-3">
                {it.index}.
              </span>{" "}
              <span className="min-w-0">
                <Inlines items={it.inline} />
              </span>
            </li>
          ))}
        </ol>
      );
    case "table":
      return (
        <div className="max-h-[520px] max-w-full overflow-auto rounded-inner border border-border-subtle">
          <table className="w-full border-collapse text-14 tabular-nums">
            <thead className="sticky top-0 z-[1]">
              <tr className="bg-surface-muted">
                {block.header.map((c, i) => (
                  <th
                    key={i}
                    scope="col"
                    className={cn(
                      "px-3 py-2 font-semibold text-text-3",
                      ALIGN[block.align[i] ?? "left"],
                    )}
                  >
                    <Inlines items={c} />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {block.rows.map((r, ri) => (
                <tr key={ri} className="border-t border-border-subtle">
                  {r.map((c, ci) => {
                    const n = numCell(c);
                    return (
                      <td
                        key={ci}
                        className={cn(
                          "px-3 py-2",
                          n.num ? "whitespace-nowrap text-right" : ALIGN[block.align[ci] ?? "left"],
                          n.neg && "text-danger",
                        )}
                      >
                        <Inlines items={c} />
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    case "hr":
      return <hr className="m-0 border-0 border-t border-border-subtle" />;
  }
}

export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = useMemo(() => parseMarkdown(text), [text]);
  return (
    <div className={cn("flex flex-col gap-3 text-16 leading-[1.6] text-text-2", className)}>
      {blocks.map((b, i) => (
        <Block key={i} block={b} />
      ))}
    </div>
  );
}
