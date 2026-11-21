import { useCallback, useMemo, useRef, useState } from "react";

import type { ColumnProposal, ConfirmBody, Proposals } from "@/lib/sourcesTypes";

import { useFocusHeading } from "./ConnectSteps";
import { FilesPanel } from "./FilesPanel";
import { ArrowRightIcon } from "./icons";
import { AutoSyncCard, IssuesPreviewCard, OpeningBalanceCard } from "./MapExtras";
import { MappingCard, sheetKey, type SheetRef } from "./MappingCard";
import { ErrorBox, parseAmount, PICK_NEXT, ProgressBar, startGoogleAuth, todayIso } from "./shared";
import { useSseRun, type RunResult } from "./useSseRun";

/** Step 3 "AI ustunlarni tanidi": files, mapping table, issues, opening balance, auto-sync, confirm. */
export function MapStep({
  proposals,
  businessName,
  onMerge,
  onBack,
  onDone,
  onConfirm,
  autoFocus,
}: {
  proposals: Proposals;
  businessName: string | null | undefined;
  onMerge: (p: Proposals) => void;
  onBack: () => void;
  onDone: (r: RunResult) => void;
  /** Onboarding: hand the confirm body to the FirstSync page instead of running it here. */
  onConfirm?: (body: ConfirmBody) => void;
  autoFocus: boolean;
}) {
  const sheets = useMemo<SheetRef[]>(
    () =>
      proposals.sources.flatMap((source) =>
        source.sheets.map((sheet) => ({ key: sheetKey(source.id, sheet.title), source, sheet })),
      ),
    [proposals.sources],
  );
  const [selKey, setSelKey] = useState<string | null>(null);
  const [selSource, setSelSource] = useState<number | null>(null);
  const [fields, setFields] = useState<Record<string, Record<number, string>>>({});
  const [kinds, setKinds] = useState<Record<string, string>>({});
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(() => todayIso());
  const [autoSync, setAutoSync] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const headingRef = useFocusHeading(autoFocus);
  const amountRef = useRef<HTMLInputElement>(null);
  const { state, run } = useSseRun();
  const running = state.status === "running" || state.status === "done";

  // A file without readable sheets can be selected too: then `current` is null.
  const current =
    sheets.find((s) => s.key === selKey) ??
    (selSource != null
      ? (sheets.find((s) => s.source.id === selSource) ?? null)
      : (sheets[0] ?? null));
  const selectedSourceId = selSource ?? current?.source.id ?? null;

  const fieldValue = useCallback(
    (key: string, col: ColumnProposal) => fields[key]?.[col.index] ?? col.field ?? "",
    [fields],
  );
  const kindValue = useCallback(
    (key: string) => kinds[key] ?? sheets.find((s) => s.key === key)?.sheet.kind ?? "",
    [kinds, sheets],
  );

  const selectSource = (sourceId: number) => {
    const first = sheets.find((s) => s.source.id === sourceId);
    setSelSource(sourceId);
    setSelKey(first?.key ?? null);
  };

  const switchSheet = (key: string) => {
    setSelKey(key);
    setSelSource(sheets.find((s) => s.key === key)?.source.id ?? null);
    headingRef.current?.focus();
  };

  const merge = (p: Proposals) => {
    const ids = new Set((p.sources ?? []).map((s) => s.id));
    const keep = <T,>(rec: Record<string, T>) =>
      Object.fromEntries(
        Object.entries(rec).filter(([k]) => !ids.has(Number(k.split("\u0000")[0]))),
      );
    // A re-picked file comes with a fresh proposal: drop edits made to its old one.
    setFields((f) => keep(f));
    setKinds((k) => keep(k));
    onMerge(p);
    const first = p.sources?.[0];
    if (first) {
      setSelSource(first.id);
      setSelKey(first.sheets?.[0] ? sheetKey(first.id, first.sheets[0].title) : null);
    }
  };

  const confirm = async () => {
    setFormError(null);
    let opening: ConfirmBody["opening_balance"] = null;
    if (proposals.needs_opening_balance) {
      const value = parseAmount(amount);
      if (!value || !date) {
        setFormError(
          !amount.trim()
            ? "Kassadagi summani kiriting."
            : !date
              ? "Sanani tanlang."
              : "Summani faqat raqamlarda yozing.",
        );
        amountRef.current?.focus();
        return;
      }
      opening = { amount: value, date };
    }
    const body: ConfirmBody = {
      mappings: sheets.map(({ key, source, sheet }) => {
        const columns: Record<string, string> = {};
        for (const col of sheet.columns) {
          const field = fieldValue(key, col);
          if (field) columns[String(col.index)] = field;
        }
        return { source_id: source.id, sheet: sheet.title, kind: kindValue(key), columns };
      }),
      opening_balance: opening,
      auto_sync: autoSync,
    };
    if (onConfirm) {
      onConfirm(body);
      return;
    }
    const result = await run("/api/sources/confirm", body, "Tahlil boshlanmoqda…");
    if (result) onDone(result);
  };

  return (
    <>
      <div className="flex flex-wrap items-start gap-5">
        <FilesPanel
          sources={proposals.sources}
          selectedId={selectedSourceId}
          onSelect={selectSource}
          onAdd={merge}
          businessName={businessName}
          disabled={running}
        />

        <section
          aria-label="Ustunlar xaritasi"
          className="flex min-w-0 flex-[999_1_560px] flex-col gap-5"
        >
          {current ? (
            <MappingCard
              current={current}
              sheets={sheets}
              fieldOptions={proposals.field_options}
              kindOptions={proposals.kind_options}
              fieldValue={fieldValue}
              onField={(key, index, value) =>
                setFields((f) => ({ ...f, [key]: { ...f[key], [index]: value } }))
              }
              kindValue={kindValue}
              onKind={(key, value) => setKinds((k) => ({ ...k, [key]: value }))}
              onSwitch={switchSheet}
              headingRef={headingRef}
              disabled={running}
            />
          ) : (
            <p className="m-0 rounded-card border border-border bg-surface px-6 py-5 text-15 text-text-3">
              Bu faylda o'qiladigan varaq topilmadi.
            </p>
          )}
          <IssuesPreviewCard issues={proposals.issues_preview} />
          {proposals.needs_opening_balance && (
            <OpeningBalanceCard
              hint={proposals.opening_balance_hint}
              amount={amount}
              date={date}
              onAmount={setAmount}
              onDate={setDate}
              amountRef={amountRef}
              disabled={running}
            />
          )}
          <AutoSyncCard checked={autoSync} onChange={setAutoSync} disabled={running} />
        </section>
      </div>

      <div className="flex flex-col">
        {/* Always mounted so screen readers announce each progress step. */}
        <div aria-live="polite">
          {state.status === "running" && (
            <div className="mb-3 rounded-card border border-border bg-surface px-4 py-5 sm:px-6">
              <ProgressBar text={state.text} pct={state.pct} label="Tahlil jarayoni" />
            </div>
          )}
        </div>
        {formError && (
          <p role="alert" className="m-0 mb-3 text-15 font-semibold text-danger">
            {formError}
          </p>
        )}
        {state.status === "error" && (
          <div className="mb-3">
            <ErrorBox
              action={
                <button
                  type="button"
                  onClick={() => (state.reauth ? startGoogleAuth(PICK_NEXT) : void confirm())}
                  className="inline-flex min-h-tap items-center self-start rounded-btn bg-primary px-[18px] text-15 font-semibold text-white hover:bg-primary-hover"
                >
                  {state.reauth ? "Qayta ulash" : "Qayta urinish"}
                </button>
              }
            >
              {state.message}
            </ErrorBox>
          </div>
        )}
        <div className="flex flex-wrap justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onBack}
            disabled={running}
            className="inline-flex min-h-12 items-center rounded-btn-lg border border-border-input bg-surface px-5 font-[inherit] text-15 font-semibold text-text-2 hover:bg-bg disabled:cursor-not-allowed disabled:opacity-60"
          >
            Orqaga
          </button>
          <button
            type="button"
            onClick={() => void confirm()}
            disabled={running || sheets.length === 0}
            aria-busy={state.status === "running"}
            className="inline-flex min-h-12 items-center gap-[10px] rounded-btn-lg border-0 bg-primary px-6 font-[inherit] text-15 font-semibold text-white hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60"
          >
            Tasdiqlash va tahlilni boshlash
            <ArrowRightIcon />
          </button>
        </div>
      </div>
    </>
  );
}
