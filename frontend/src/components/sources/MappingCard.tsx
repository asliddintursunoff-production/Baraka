import { useId, useState, type Ref } from "react";

import { appConfig } from "@/lib/config";
import type { ColumnProposal, Option, SheetProposal, SourceProposal } from "@/lib/sourcesTypes";
import { cn } from "@/lib/utils";

import { CheckIcon } from "./icons";

export interface SheetRef {
  key: string;
  source: SourceProposal;
  sheet: SheetProposal;
}

export const sheetKey = (sourceId: number, sheet: string) => `${sourceId}\u0000${sheet}`;

const SELECT =
  "min-h-tap max-w-full rounded-lg border bg-surface px-[10px] font-[inherit] text-14 text-ink disabled:opacity-60";

/** `"A", "B" va "C"` */
function uzList(items: string[]): string {
  const quoted = items.map((t) => `"${t}"`);
  if (quoted.length <= 1) return quoted.join("");
  return `${quoted.slice(0, -1).join(", ")} va ${quoted[quoted.length - 1]}`;
}

/** Options for one column: `field_options`, plus the proposed field if the list lacks it. */
function optionsFor(col: ColumnProposal, fieldOptions: Option[]): Option[] {
  if (!col.field || fieldOptions.some((o) => o.value === col.field)) return fieldOptions;
  return [{ value: col.field, label: col.field_label || col.field }, ...fieldOptions];
}

function ColumnRow({
  col,
  value,
  fieldOptions,
  onChange,
  disabled,
}: {
  col: ColumnProposal;
  value: string;
  fieldOptions: Option[];
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  const id = useId();
  if (col.status !== "confirm") {
    return (
      <tr className="border-t border-border-subtle">
        <td className="py-3 pr-3 font-semibold">{col.header}</td>
        <td className="py-3 pr-3 text-text-3">{col.sample}</td>
        <td className="py-3 pr-3">{col.field_label}</td>
        <td className="py-3 font-semibold text-success">Aniq</td>
      </tr>
    );
  }
  const options = optionsFor(col, fieldOptions);
  return (
    <tr className="border-t border-border-subtle bg-warning-bg">
      <td className="px-2 py-3 font-semibold">{col.header}</td>
      <td className="py-3 pr-3 text-text-3">{col.sample}</td>
      <td className="py-3 pr-3">
        <div className="flex flex-col gap-1">
          <label htmlFor={id} className="sr-only">
            {col.header} ustuni uchun maydon
          </label>
          <select
            id={id}
            value={value}
            disabled={disabled}
            onChange={(e) => onChange(e.target.value)}
            aria-describedby={col.question ? `${id}-q` : undefined}
            className={cn(SELECT, "border-[#FEC84B]")}
          >
            {value === "" && (
              <option value="" disabled>
                {col.question || "Tanlang"}
              </option>
            )}
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {col.question && (
            <span id={`${id}-q`} className="text-13 text-text-3">
              {col.question}
            </span>
          )}
        </div>
      </td>
      <td className="py-3 pr-2 font-semibold text-warning">Tasdiqlang</td>
    </tr>
  );
}

function SheetSwitcher({
  current,
  sheets,
  kindOptions,
  kindValue,
  onKind,
  onSwitch,
  disabled,
}: {
  current: SheetRef;
  sheets: SheetRef[];
  kindOptions: Option[];
  kindValue: (key: string) => string;
  onKind: (key: string, value: string) => void;
  onSwitch: (key: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const others = sheets.filter((s) => s.key !== current.key);
  if (others.length === 0) return null;
  const names = [...new Set(others.map((s) => s.sheet.title))];
  return (
    <div className="flex flex-col gap-2">
      <span className="text-13 text-text-4">
        {uzList(names)} {names.length > 1 ? "varaqlari" : "varag'i"} ham shu tarzda tanildi ·{" "}
        <button
          type="button"
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex min-h-tap items-center border-0 bg-transparent p-0 font-[inherit] text-13 text-primary underline hover:text-primary-hover"
        >
          ko'rish
        </button>
      </span>
      {open && (
        <ul id={listId} aria-label="Varaqlar" className="m-0 flex list-none flex-col p-0">
          {sheets.map((s, i) => {
            const isCurrent = s.key === current.key;
            const kind = kindValue(s.key);
            const kinds =
              kind && !kindOptions.some((o) => o.value === kind)
                ? [{ value: kind, label: s.sheet.kind_label || kind }, ...kindOptions]
                : kindOptions;
            const selectId = `${listId}-kind-${i}`;
            return (
              <li
                key={s.key}
                className={cn(
                  "flex flex-wrap items-center gap-3 border-t border-border-subtle px-2 py-[10px] text-14",
                  isCurrent && "bg-primary-soft",
                )}
              >
                <span className="flex min-w-0 flex-[1_1_200px] flex-col gap-[2px]">
                  <span className="break-words font-semibold">
                    {s.source.title} › {s.sheet.title}
                  </span>
                  <span className="text-13 text-text-4">
                    {s.sheet.rows_display} qator
                    {s.sheet.recognized ? ` · ${s.sheet.recognized}` : ""}
                  </span>
                </span>
                {kinds.length > 0 && (
                  <>
                    <label htmlFor={selectId} className="sr-only">
                      "{s.sheet.title}" varag'i turi
                    </label>
                    <select
                      id={selectId}
                      value={kind}
                      disabled={disabled}
                      onChange={(e) => onKind(s.key, e.target.value)}
                      className={cn(SELECT, "border-border-input")}
                    >
                      {kinds.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </>
                )}
                {isCurrent ? (
                  <span className="inline-flex min-h-tap items-center text-13 font-semibold text-primary">
                    Ko'rsatilmoqda
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => onSwitch(s.key)}
                    aria-label={`"${s.sheet.title}" varag'ini ko'rish`}
                    className="min-h-tap rounded-lg border border-border-input bg-surface px-[14px] font-[inherit] text-13 font-semibold text-text-2 hover:bg-bg"
                  >
                    Ko'rish
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

/** "Chiqim" varag'i · N qator — column mapping table + switcher for the other sheets. */
export function MappingCard({
  current,
  sheets,
  fieldOptions,
  kindOptions,
  fieldValue,
  onField,
  kindValue,
  onKind,
  onSwitch,
  headingRef,
  disabled,
}: {
  current: SheetRef;
  sheets: SheetRef[];
  fieldOptions: Option[];
  kindOptions: Option[];
  fieldValue: (key: string, col: ColumnProposal) => string;
  onField: (key: string, index: number, value: string) => void;
  kindValue: (key: string) => string;
  onKind: (key: string, value: string) => void;
  onSwitch: (key: string) => void;
  headingRef: Ref<HTMLHeadingElement>;
  disabled: boolean;
}) {
  const { sheet } = current;
  return (
    <div className="flex flex-col gap-[14px] rounded-card border border-border bg-surface px-4 py-5 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-[10px]">
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="m-0 font-display text-[18px] font-bold outline-none"
        >
          "{sheet.title}" varag'i · {sheet.rows_display} qator
        </h2>
        {sheet.recognized && (
          <span className="inline-flex items-center gap-[6px] text-13 font-semibold text-success">
            <CheckIcon strokeWidth={2.5} />
            {sheet.recognized}
          </span>
        )}
      </div>
      {sheet.columns.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] border-collapse text-14">
            <thead>
              <tr className="text-left text-12 uppercase tracking-label text-text-4">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Sizning ustuningiz
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Namuna
                </th>
                <th scope="col" className="py-2 pr-3 font-semibold">
                  {appConfig.appName} maydoni
                </th>
                <th scope="col" className="py-2 font-semibold">
                  Holat
                </th>
              </tr>
            </thead>
            <tbody>
              {sheet.columns.map((col) => (
                <ColumnRow
                  key={col.index}
                  col={col}
                  value={fieldValue(current.key, col)}
                  fieldOptions={fieldOptions}
                  onChange={(v) => onField(current.key, col.index, v)}
                  disabled={disabled}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="m-0 text-14 text-text-3">Bu varaqda ustun topilmadi.</p>
      )}
      <SheetSwitcher
        current={current}
        sheets={sheets}
        kindOptions={kindOptions}
        kindValue={kindValue}
        onKind={onKind}
        onSwitch={onSwitch}
        disabled={disabled}
      />
    </div>
  );
}
