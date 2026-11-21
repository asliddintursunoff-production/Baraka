import { ArrowRight, Check, X } from "lucide-react";
import { Link } from "react-router-dom";

import { PublicFooter, PublicHeader } from "@/components/public/PublicChrome";

const H2 = "m-0 font-display text-[36px] font-bold leading-[1.15]";
const CTA =
  "inline-flex min-h-[52px] items-center gap-[10px] rounded-btn-lg bg-primary px-6 text-17 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white";

const PROBLEMS = [
  {
    title: "To'lovlar bir kunga tushadi",
    text: "Oylik, kredit va ta'minotchi bir haftaga to'g'ri kelsa, foydali biznes ham qiynaladi.",
    box: "bg-danger-bg",
    color: "text-[#912018]",
  },
  {
    title: "Xarid qarori taxminan qilinadi",
    text: "\"Hozir olsam bo'ladimi?\" degan savolga jadvaldan aniq javob topish qiyin.",
    box: "bg-warning-bg",
    color: "text-[#93370D]",
  },
  {
    title: "Muammo kech bilinadi",
    text: "Kassa tugaganini to'lov kuni bilasiz — o'shanda tuzatishga kech bo'ladi.",
    box: "bg-bg",
    color: "",
  },
];

const HOW = [
  {
    title: "Jadvalingizni ulang",
    text: "Google Sheets yoki Drive'dagi Excel — qanday ustunlar bo'lishidan qat'i nazar. AI ularni o'zi taniydi, siz faqat tasdiqlaysiz.",
  },
  {
    title: "AI kuzatib boradi",
    text: "Har 15 daqiqada yangi qatorlarni o'qiydi, kassani har kunga hisoblaydi va xavfli kun chiqsa o'zi xabar beradi.",
  },
  {
    title: "So'rang — qaror oling",
    text: "Yozib yoki gapirib so'rang. AI aniq javob, sabab va qadamlarni beradi. Reja faqat sizning tasdig'ingiz bilan saqlanadi.",
  },
];

const FEATURES = [
  { title: "Kunlik kassa prognozi", text: "7, 30, 60, 90 kun oldinga. Eng qiyin kun va sababi ko'rinib turadi." },
  { title: "\"Agar...?\" simulyatori", text: "Xarid, yangi xodim yoki savdo tushishi — natijasini darhol ko'ring." },
  {
    title: "O'zi ogohlantiradi",
    text: "So'ramasangiz ham: \"10-dekabrga ehtiyot bo'ling\" — va nima qilish kerakligi.",
  },
  { title: "Jonli o'zbekcha ovoz", text: "Telefon qilgandek gaplashing. AI gapirayotganda grafik ham chizadi." },
  {
    title: "Sizdan o'rganadi",
    text: "\"Bizda bu to'lov doim 15 kun keyin\" — bir marta ayting, prognoz shunga moslashadi.",
  },
  {
    title: "Ma'lumot faqat sizniki",
    text: "Faqat siz tanlagan jadvallar o'qiladi. Boshqa bizneslar sizning raqamlaringizni hech qachon ko'rmaydi.",
  },
];

const TRUST = [
  "Hech qachon pul o'tkazmaydi — faqat reja va eslatma",
  "Har bir amal sizning tasdig'ingiz bilan",
  "Ma'lumot yetarli bo'lmasa — \"bilmayman\" deydi, taxmin qilmaydi",
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-surface font-sans text-ink">
      <PublicHeader />

      <section className="border-b border-border-subtle bg-bg">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-12 px-6 py-[72px]">
          <div className="flex flex-[1_1_480px] flex-col gap-[22px]">
            <span className="self-start rounded-pill bg-primary-soft px-3 py-[6px] text-14 font-semibold text-primary">
              Kichik biznes uchun shaxsiy AI moliyaviy direktor
            </span>
            <h1 className="m-0 font-display text-[40px] font-bold leading-[1.08] md:text-[52px]">
              Pul sarflashdan oldin bilib oling: oylik va kreditga yetadimi?
            </h1>
            <p className="m-0 max-w-[560px] text-[19px] leading-[1.6] text-text-2">
              Google Sheets jadvalingizni ulang. AI har kuni kassangizni hisoblaydi, xavfli kunni oldindan aytadi va
              aniq qaror beradi — o'zbek tilida, ovoz bilan ham.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/register" className={CTA}>
                Bepul boshlash
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
              <Link
                to="/register"
                className="inline-flex min-h-[52px] items-center rounded-btn-lg border border-border-input bg-surface px-[22px] text-17 font-semibold text-text-2 no-underline hover:text-ink"
              >
                Demo kafeni ko'rish
              </Link>
            </div>
            <span className="text-14 text-text-3">
              Karta talab qilinmaydi · jadvalni o'zgartirish shart emas · pul o'tkazmaydi
            </span>
          </div>

          <div aria-label="Mahsulot namunasi" className="flex min-w-0 flex-[1_1_420px] flex-col gap-[14px]">
            <div className="max-w-[380px] self-end rounded-[16px_4px_16px_16px] bg-primary px-4 py-[14px] text-16 leading-[1.5] text-white">
              25 million so'mga jihoz olsam, keyingi oy oylik va kreditga pulim yetadimi?
            </div>
            <div className="flex flex-col gap-[14px] rounded-card border border-border bg-surface p-5 shadow-[0_12px_32px_rgba(16,24,40,.08)]">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-[18px] bg-danger-bg text-danger">
                  <X size={18} aria-hidden="true" />
                </span>
                <span className="font-display text-22 font-bold">Yo'q, hozir olmang.</span>
              </div>
              <span className="text-15 leading-[1.5] text-text-2">
                Hozir olsangiz, 10-dekabrda oylikka <strong className="text-ink">6,2 mln yetmaydi</strong>.
                12-yanvarda oling.
              </span>
              <div className="flex flex-col gap-[10px] rounded-inner border border-border-subtle bg-surface-muted p-[14px]">
                <div className="flex items-center gap-[10px]">
                  <span className="flex-[0_0_110px] text-13 font-semibold">Hozir olsangiz</span>
                  <div className="flex h-[22px] flex-auto">
                    <div className="flex w-1/4 justify-end border-r-2 border-text-2">
                      <div className="w-[93%] rounded-l-[5px] bg-danger" />
                    </div>
                    <div className="w-3/4" />
                  </div>
                  <strong className="flex-[0_0_70px] text-right text-13 text-danger">−6,2 mln</strong>
                </div>
                <div className="flex items-center gap-[10px]">
                  <span className="flex-[0_0_110px] text-13 font-semibold">12-yanvarda</span>
                  <div className="flex h-[22px] flex-auto">
                    <div className="w-1/4 border-r-2 border-text-2" />
                    <div className="flex w-3/4">
                      <div className="w-[94%] rounded-r-[5px] bg-success" />
                    </div>
                  </div>
                  <strong className="flex-[0_0_70px] text-right text-13 text-success">+18,8 mln</strong>
                </div>
              </div>
              <span className="text-12 text-text-4">Namuna: demo kafe ma'lumotlari</span>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto flex max-w-[1200px] flex-col gap-7 px-6 pb-6 pt-[72px]">
        <h2 className={`${H2} max-w-[760px]`}>Biznes foyda ko'rsatadi, lekin oylik kuni kassada pul yo'q</h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,1fr))] gap-4">
          {PROBLEMS.map((p) => (
            <div key={p.title} className={`flex flex-col gap-2 rounded-card p-[22px] ${p.box}`}>
              <span className={`text-17 font-bold ${p.color}`}>{p.title}</span>
              <span className="text-15 leading-[1.55] text-text-2">{p.text}</span>
            </div>
          ))}
        </div>
      </section>

      <section id="qanday" className="mx-auto flex max-w-[1200px] flex-col gap-7 px-6 py-14">
        <div className="flex flex-col gap-2">
          <span className="text-14 font-bold uppercase tracking-label text-primary">Qanday ishlaydi</span>
          <h2 className={H2}>Uch qadam — va AI ishga tushadi</h2>
        </div>
        <ol className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4 p-0">
          {HOW.map((h, i) => (
            <li key={h.title} className="flex flex-col gap-[10px] rounded-card border border-border p-6">
              <span className="flex h-10 w-10 items-center justify-center rounded-[20px] bg-ink font-bold text-white">
                {i + 1}
              </span>
              <span className="text-[19px] font-bold">{h.title}</span>
              <span className="text-15 leading-[1.55] text-text-3">{h.text}</span>
            </li>
          ))}
        </ol>
      </section>

      <section id="imkoniyatlar" className="border-y border-border-subtle bg-bg">
        <div className="mx-auto flex max-w-[1200px] flex-col gap-7 px-6 py-16">
          <h2 className={H2}>Nimalar qila oladi</h2>
          <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
            {FEATURES.map((f) => (
              <div key={f.title} className="flex flex-col gap-2 rounded-card border border-border bg-surface p-[22px]">
                <span className="text-[18px] font-bold">{f.title}</span>
                <span className="text-15 leading-[1.55] text-text-3">{f.text}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto flex max-w-[1200px] flex-wrap items-center gap-8 px-6 py-16">
        <div className="flex flex-[1_1_420px] flex-col gap-3">
          <h2 className="m-0 font-display text-32 font-bold">Raqamlarni AI o'ylab topmaydi</h2>
          <p className="m-0 text-17 leading-[1.6] text-text-2">
            Har bir summa va sana sizning jadvalingizdan aniq formulalar bilan hisoblanadi. AI faqat natijani sodda
            tilda tushuntiradi va qaror taklif qiladi.
          </p>
        </div>
        <ul className="m-0 flex flex-[1_1_420px] list-none flex-col gap-3 p-0">
          {TRUST.map((t) => (
            <li key={t} className="flex items-start gap-3 text-16 leading-[1.5]">
              <Check size={20} className="mt-[2px] shrink-0 text-success" aria-hidden="true" />
              {t}
            </li>
          ))}
        </ul>
      </section>

      <section id="banklar" className="mx-auto max-w-[1200px] px-6 pb-16">
        <div className="flex flex-wrap items-center gap-6 rounded-[20px] bg-ink p-10 text-white">
          <div className="flex flex-[1_1_460px] flex-col gap-[10px]">
            <span className="text-14 font-bold uppercase tracking-label text-[#B2CCFF]">Banklar uchun</span>
            <h2 className="m-0 font-display text-32 font-bold">O'z ilovangizda — o'z brendingiz bilan</h2>
            <p className="m-0 text-17 leading-[1.6] text-border-input">
              Kichik biznes mijozlaringizga AI moliyaviy maslahatchini white-label sifatida taqdim eting.
            </p>
          </div>
          <Link
            to="/pricing"
            className="inline-flex min-h-[52px] items-center rounded-btn-lg bg-surface px-6 text-16 font-bold text-ink no-underline hover:text-ink"
          >
            Bog'lanish
          </Link>
        </div>
      </section>

      <section className="border-t border-[#D1E0FF] bg-primary-soft">
        <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-5 px-6 py-14">
          <h2 className="m-0 font-display text-30 font-bold">5 daqiqada ulang — bugunoq birinchi xulosani oling</h2>
          <Link to="/register" className={CTA}>
            Bepul boshlash
          </Link>
        </div>
      </section>

      <PublicFooter />
    </div>
  );
}
