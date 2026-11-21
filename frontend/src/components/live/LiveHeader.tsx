/** Live header (design/pages/Live.html): logo, title, business line, "Jonli" pill, close. */
import { LogoMark } from "@/components/LogoMark";

export function LiveHeader({ businessName, onClose }: { businessName: string; onClose: () => void }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-live-border px-4 py-[18px] sm:px-8">
      <div className="flex min-w-0 items-center gap-3">
        <LogoMark size={32} />
        <div className="flex min-w-0 flex-col gap-[2px]">
          <h1 className="m-0 font-display text-[18px] font-bold">Jonli suhbat · AI CFO</h1>
          <span className="text-13 text-[#98A2B3]">
            {businessName ? `${businessName} · ` : ""}o'zbek tilida
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="inline-flex min-h-[36px] items-center gap-2 rounded-pill bg-live-border px-[14px] text-14 font-semibold text-[#D0D5DD]">
          <span className="h-2 w-2 rounded-[4px] bg-[#F04438]" aria-hidden="true" />
          Jonli
        </span>
        <button
          type="button"
          onClick={onClose}
          aria-label="Jonli suhbatni yopish"
          className="flex h-11 w-11 items-center justify-center rounded-inner border-0 bg-live-border"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#D0D5DD" strokeWidth="2" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
    </header>
  );
}
