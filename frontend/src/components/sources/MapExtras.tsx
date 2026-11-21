import { useId, type Ref } from "react";

import type { IssuePreview, Proposals } from "@/lib/sourcesTypes";

const CARD = "rounded-card border bg-surface px-4 py-5 sm:px-6";
const INPUT =
  "min-h-tap rounded-btn border border-border-input bg-surface px-3 font-[inherit] text-15 font-normal text-ink";

/** "N ta qatorni tekshirish kerak" from `issues_preview` (fixed later on the Sources page). */
export function IssuesPreviewCard({ issues }: { issues: IssuePreview[] }) {
  if (issues.length === 0) return null;
  const manySheets = new Set(issues.map((i) => `${i.source_id}\u0000${i.sheet}`)).size > 1;
  return (
    <section
      aria-labelledby="issues-title"
      className={`${CARD} flex flex-col gap-3 border-[#FEDF89]`}
    >
      <h2 id="issues-title" className="m-0 font-display text-[18px] font-bold">
        {issues.length} ta qatorni tekshirish kerak
      </h2>
      <ul className="m-0 flex list-none flex-col p-0">
        {issues.map((it, i) => (
          <li
            key={`${it.source_id}-${it.sheet}-${it.row}-${i}`}
            className="flex flex-wrap items-center gap-3 border-t border-border-subtle py-[10px] text-14"
          >
            <span className="flex min-w-[90px] flex-col">
              <span className="font-semibold">Qator {it.row}</span>
              {manySheets && it.sheet && <span className="text-13 text-text-4">"{it.sheet}"</span>}
            </span>
            <span className="flex-[1_1_260px] text-text-2">{it.message}</span>
            {it.action_label && (
              // Suggested fix only: preview rows have no id, so they are resolved on the Sources page.
              <span className="text-13 font-semibold text-text-3">→ {it.action_label}</span>
            )}
          </li>
        ))}
      </ul>
      <span className="text-13 text-text-4">
        Bu qatorlarni tahlildan keyin «Ma'lumotlar» sahifasida tuzatasiz.
      </span>
    </section>
  );
}

/** One question when the sheets have no cash balance: "Bugun kassada qancha pul bor?" */
export function OpeningBalanceCard({
  hint,
  amount,
  date,
  onAmount,
  onDate,
  amountRef,
  disabled,
}: {
  hint: Proposals["opening_balance_hint"];
  amount: string;
  date: string;
  onAmount: (v: string) => void;
  onDate: (v: string) => void;
  amountRef: Ref<HTMLInputElement>;
  disabled: boolean;
}) {
  const hintId = useId();
  return (
    <fieldset className={`${CARD} m-0 flex min-w-0 flex-col gap-3 border-border`}>
      <legend className="float-left mb-1 w-full p-0 text-16 font-bold">
        Bugun kassada qancha pul bor?
      </legend>
      {hint && (
        <span id={hintId} className="text-14 leading-normal text-text-3">
          Jadvalingizga ko'ra: {hint.amount_display} · {hint.date_display}
        </span>
      )}
      <div className="flex flex-wrap gap-3">
        <label className="flex min-w-0 flex-[1_1_200px] flex-col gap-1 text-13 font-semibold text-text-3">
          Summa (so'm)
          <input
            ref={amountRef}
            required
            inputMode="decimal"
            autoComplete="off"
            value={amount}
            disabled={disabled}
            aria-describedby={hint ? hintId : undefined}
            onChange={(e) => onAmount(e.target.value)}
            className={INPUT}
          />
        </label>
        <label className="flex min-w-0 flex-[1_1_160px] flex-col gap-1 text-13 font-semibold text-text-3">
          Sana
          <input
            required
            type="date"
            value={date}
            disabled={disabled}
            onChange={(e) => onDate(e.target.value)}
            className={INPUT}
          />
        </label>
      </div>
    </fieldset>
  );
}

export function AutoSyncCard({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled: boolean;
}) {
  const descId = useId();
  return (
    <div className={`${CARD} flex flex-wrap items-center gap-4 border-border`}>
      <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1">
        <span className="text-16 font-bold">Avtomatik sinxronlash</span>
        <span id={descId} className="text-14 leading-normal text-text-3">
          Har 15 daqiqada yangi qatorlar o'qiladi. Yangi varaq yoki ustun qo'shsangiz, AI uni ham
          taniydi va faqat noaniq bo'lsa so'raydi.
        </span>
      </div>
      <label className="inline-flex min-h-tap cursor-pointer items-center gap-[10px] text-14 font-semibold">
        <input
          type="checkbox"
          checked={checked}
          disabled={disabled}
          aria-describedby={descId}
          onChange={(e) => onChange(e.target.checked)}
          className="h-[22px] w-[22px] accent-primary"
        />
        <span>
          <span className="sr-only">Avtomatik sinxronlash: </span>
          {checked ? "Yoqilgan" : "O'chirilgan"}
        </span>
      </label>
    </div>
  );
}
