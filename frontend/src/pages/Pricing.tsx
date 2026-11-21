import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import { PublicFooter, PublicHeader } from "@/components/public/PublicChrome";
import { appConfig } from "@/lib/config";

/** `null` → the design placeholder verbatim; numbers only come from `app_settings.PRICING`. */
function n(value: number | null | undefined, placeholder = "[N]"): string {
  return value == null ? placeholder : new Intl.NumberFormat("ru-RU").format(value).replace(/\s/g, " ");
}

const FAQ = [
  {
    q: "Jadvalimni o'zgartirishim kerakmi?",
    a: "Yo'q. Ustunlar qanday nomlangan bo'lishidan qat'i nazar, AI ularni taniydi. Siz faqat bir marta tasdiqlaysiz.",
  },
  {
    q: "Ma'lumotlarim xavfsizmi?",
    a: "Ilova faqat siz tanlagan jadvallarni o'qiydi va ularni o'zgartirmaydi. Ruxsatni istalgan payt Google sozlamalarida bekor qilishingiz mumkin.",
  },
  {
    q: "AI pulimni o'tkazadimi?",
    a: "Yo'q. AI faqat hisoblaydi, maslahat beradi va siz tasdiqlagan reja hamda eslatmalarni saqlaydi.",
  },
  {
    q: "Jadvalim Excel'da bo'lsa-chi?",
    a: "Faylni Google Drive'ga yuklang va ulashda tanlang — ilova uni o'zi o'qib boradi.",
  },
];

function Features({ items, dark = false }: { items: string[]; dark?: boolean }) {
  return (
    <ul className={`m-0 flex list-none flex-col gap-[10px] p-0 text-15 leading-[1.45] ${dark ? "text-border-subtle" : ""}`}>
      {items.map((t) => (
        <li key={t} className="flex gap-[10px]">
          <Check size={18} className={`mt-[1px] shrink-0 ${dark ? "text-[#B2CCFF]" : "text-success"}`} aria-hidden="true" />
          {t}
        </li>
      ))}
    </ul>
  );
}

export default function PricingPage() {
  const trial = appConfig.pricing?.trial;
  const business = appConfig.pricing?.business;
  return (
    <div className="min-h-screen bg-bg font-sans text-ink">
      <PublicHeader />
      <main className="mx-auto flex max-w-[1200px] flex-col gap-10 px-6 pb-[72px] pt-14">
        <div className="flex flex-col items-center gap-3 text-center">
          <h1 className="m-0 font-display text-[36px] font-bold md:text-[44px]">Oddiy va tushunarli narxlar</h1>
          <p className="m-0 max-w-[620px] text-[18px] leading-[1.55] text-text-3">
            Avval bepul sinab ko'ring. Foydali bo'lsa, davom etasiz. Pul o'tkazmalari va yashirin to'lovlar yo'q.
          </p>
        </div>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] items-stretch gap-5">
          <article className="flex flex-col gap-[18px] rounded-[20px] border border-border bg-surface p-7">
            <div className="flex flex-col gap-[6px]">
              <h2 className="m-0 text-20 font-bold">Sinov</h2>
              <span className="text-15 text-text-3">Biznesingizda qanday ishlashini ko'rish uchun</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-[40px] font-bold">{n(trial?.price_uzs ?? 0)} so'm</span>
              <span className="text-15 text-text-3">· {n(trial?.days)} kun</span>
            </div>
            <Link
              to="/register"
              className="inline-flex min-h-12 items-center justify-center rounded-btn-lg border border-border-input text-16 font-semibold text-text-2 no-underline hover:text-ink"
            >
              Bepul boshlash
            </Link>
            <Features
              items={[
                `1 ta biznes, ${n(trial?.sheets)} ta jadval`,
                "Kunlik prognoz va ogohlantirishlar",
                `AI chat: kuniga ${n(trial?.chat_per_day)} ta savol`,
                `Jonli ovoz: ${n(trial?.voice_minutes)} daqiqa`,
              ]}
            />
          </article>

          <article className="flex flex-col gap-[18px] rounded-[20px] border-2 border-primary bg-surface p-[27px] shadow-[0_12px_32px_rgba(29,78,216,.12)]">
            <div className="flex items-start justify-between gap-[10px]">
              <div className="flex flex-col gap-[6px]">
                <h2 className="m-0 text-20 font-bold">Biznes</h2>
                <span className="text-15 text-text-3">Har kuni ishlatadigan kafe va do'konlar uchun</span>
              </div>
              <span className="whitespace-nowrap rounded-pill bg-primary-soft px-[10px] py-1 text-12 font-bold text-primary">
                Tavsiya
              </span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display text-[40px] font-bold">{n(business?.price_uzs_month, "[narx]")}</span>
              <span className="text-15 text-text-3">so'm / oy</span>
            </div>
            <Link
              to="/register"
              className="inline-flex min-h-12 items-center justify-center rounded-btn-lg bg-primary text-16 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white"
            >
              Boshlash
            </Link>
            <Features
              items={[
                "Cheksiz jadvallar va varaqlar",
                "\"Agar...?\" simulyatori",
                "Jonli o'zbekcha ovoz",
                "AI biznesingizdan o'rganadi",
                "Hisobchi uchun qo'shimcha foydalanuvchi",
              ]}
            />
          </article>

          <article className="flex flex-col gap-[18px] rounded-[20px] bg-ink p-7 text-white">
            <div className="flex flex-col gap-[6px]">
              <h2 className="m-0 text-20 font-bold">Bank · white-label</h2>
              <span className="text-15 text-border-input">Bankning biznes mijozlari uchun</span>
            </div>
            <div className="font-display text-32 font-bold leading-[1.2]">Kelishuv asosida</div>
            <Link
              to="/"
              className="inline-flex min-h-12 items-center justify-center rounded-btn-lg bg-surface text-16 font-bold text-ink no-underline hover:text-ink"
            >
              Bog'lanish
            </Link>
            <Features
              dark
              items={["Bank brendi va ilovasi ichida", "Ko'p biznesli boshqaruv paneli", "API va alohida joylashtirish"]}
            />
          </article>
        </div>

        <section
          aria-label="Ko'p so'raladigan savollar"
          className="flex flex-col gap-1 rounded-[20px] border border-border bg-surface p-7"
        >
          <h2 className="m-0 mb-[10px] font-display text-24 font-bold">Ko'p so'raladigan savollar</h2>
          {FAQ.map((f) => (
            <details key={f.q} className="border-t border-border-subtle py-[14px]">
              <summary className="flex min-h-8 cursor-pointer items-center text-16 font-semibold">{f.q}</summary>
              <p className="m-0 mt-[10px] text-15 leading-[1.6] text-text-3">{f.a}</p>
            </details>
          ))}
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}
