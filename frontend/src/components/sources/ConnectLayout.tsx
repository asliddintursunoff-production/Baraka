import { Fragment, type ReactNode } from "react";

import { LogoMark } from "@/components/LogoMark";
import { appConfig } from "@/lib/config";
import { cn } from "@/lib/utils";

import { CheckIcon } from "./icons";

export type ConnectStep = 1 | 2 | 3 | 4;

const STEPS = ["Google hisob", "Fayllar", "AI ustunlarni tanidi", "Tayyor"] as const;

type StepState = "done" | "current" | "todo";

function Stepper({ step, finished }: { step: ConnectStep; finished: boolean }) {
  const stateOf = (n: number): StepState =>
    n < step || (finished && n === step) ? "done" : n === step ? "current" : "todo";
  return (
    <ol
      aria-label="Ulash bosqichlari"
      className="m-0 flex list-none flex-wrap items-center gap-[10px] p-0 text-14"
    >
      {STEPS.map((label, i) => {
        const n = i + 1;
        const s = stateOf(n);
        return (
          <Fragment key={label}>
            {i > 0 && (
              <li
                aria-hidden="true"
                className={cn(
                  "h-[2px] w-7",
                  s === "done" ? "bg-success" : s === "current" ? "bg-primary" : "bg-border-input",
                )}
              />
            )}
            <li
              aria-current={s === "current" ? "step" : undefined}
              className={cn(
                "flex items-center gap-2",
                s === "done" && "font-semibold text-success",
                s === "current" && "font-bold text-primary",
                s === "todo" && "font-semibold text-text-4",
              )}
            >
              <span
                className={cn(
                  "box-border flex h-[26px] w-[26px] items-center justify-center rounded-[13px] text-13",
                  s === "done" && "bg-success text-white",
                  s === "current" && "bg-primary text-white",
                  s === "todo" && "border-2 border-border-input",
                )}
              >
                {s === "done" ? <CheckIcon color="#FFFFFF" /> : n}
              </span>
              {label}
              {s === "done" && <span className="sr-only"> — bajarildi</span>}
            </li>
          </Fragment>
        );
      })}
    </ol>
  );
}

/** Connect has no sidebar (DESIGN.md): logo + stepper header, centred main column. */
export function ConnectLayout({
  step,
  finished = false,
  children,
}: {
  step: ConnectStep;
  finished?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-bg font-sans text-ink">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border bg-surface px-4 py-5 md:px-10">
        <div className="flex items-center gap-[10px]">
          <LogoMark />
          <span className="font-display text-[19px] font-bold">{appConfig.appName}</span>
        </div>
        <Stepper step={step} finished={finished} />
      </header>
      <main className="mx-auto box-border flex w-full max-w-[1280px] grow flex-col gap-6 px-4 pb-12 pt-8 md:px-10">
        {children}
      </main>
    </div>
  );
}

export function ConnectIntro({ full }: { full: boolean }) {
  return (
    <div className="flex max-w-[760px] flex-col gap-2">
      <h1 className="m-0 font-display text-32 font-bold">Jadvallaringizni o'z holicha qoldiring</h1>
      <p className="m-0 text-16 leading-[1.55] text-text-3">
        Ustun nomlari, varaqlar soni va tartibi muhim emas.
        {full &&
          " AI har bir ustun nimani anglatishini o'zi aniqladi — faqat tekshirib, tasdiqlang."}{" "}
        Bu <strong className="text-ink">bir marta</strong> qilinadi, keyin yangi qatorlar o'zi
        keladi.
      </p>
    </div>
  );
}
