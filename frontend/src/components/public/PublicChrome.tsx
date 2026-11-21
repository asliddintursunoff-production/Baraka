import { Link } from "react-router-dom";

import { LogoMark } from "@/components/LogoMark";
import { appConfig } from "@/lib/config";

const NAV_LINK = "text-text-2 no-underline hover:text-primary";

/** Landing.html / Pricing.html top nav. Section anchors point at the landing page. */
export function PublicHeader() {
  return (
    <header className="sticky top-0 z-[5] border-b border-border-subtle bg-surface">
      <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-4 px-6 py-[14px]">
        <Link to="/" className="flex items-center gap-[10px] text-ink no-underline hover:text-ink">
          <LogoMark />
          <span className="font-display text-[19px] font-bold">{appConfig.appName}</span>
        </Link>
        <nav aria-label="Sayt menyusi" className="flex flex-wrap items-center gap-6 text-15 font-medium">
          <a className={NAV_LINK} href="/#qanday">
            Qanday ishlaydi
          </a>
          <a className={NAV_LINK} href="/#imkoniyatlar">
            Imkoniyatlar
          </a>
          <Link className={NAV_LINK} to="/pricing">
            Narxlar
          </Link>
          <a className={NAV_LINK} href="/#banklar">
            Banklar uchun
          </a>
        </nav>
        <div className="flex gap-[10px]">
          <Link
            to="/login"
            className="inline-flex min-h-tap items-center rounded-btn border border-border-input px-[18px] text-15 font-semibold text-text-2 no-underline hover:text-ink"
          >
            Kirish
          </Link>
          <Link
            to="/register"
            className="inline-flex min-h-tap items-center rounded-btn bg-primary px-[18px] text-15 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white"
          >
            Bepul boshlash
          </Link>
        </div>
      </div>
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="mx-auto flex max-w-[1200px] flex-wrap justify-between gap-4 px-6 pb-10 pt-7 text-14 text-text-3">
      <span>© {appConfig.appName}</span>
      <div className="flex flex-wrap gap-5">
        <Link to="/pricing">Narxlar</Link>
        <Link to="/">Maxfiylik siyosati</Link>
        <Link to="/">Foydalanish shartlari</Link>
      </div>
    </footer>
  );
}
