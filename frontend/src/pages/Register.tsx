import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { apiMessage, AuthLayout, INPUT, LABEL, SUBMIT } from "@/components/public/AuthLayout";
import { apiPost } from "@/lib/api";
import type { Me } from "@/lib/types";

const NEXT_STEPS = [
  { title: "Biznesingiz haqida", text: "Nomi, turi va oylik kuni — 1 daqiqa" },
  { title: "Jadvallarni ulash", text: "Google Sheets yoki Drive'dagi Excel" },
  { title: "Birinchi xulosa", text: "AI kassangizni hisoblab, xavfli kunni aytadi" },
];

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [terms, setTerms] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  return (
    <AuthLayout
      asideLabel="Keyingi qadamlar"
      aside={
        <>
          <h2 className="m-0 max-w-[440px] font-display text-32 font-bold leading-[1.2]">Keyingi 5 daqiqada</h2>
          <ol className="m-0 flex max-w-[440px] list-none flex-col gap-[18px] p-0">
            {NEXT_STEPS.map((s, i) => (
              <li key={s.title} className="flex items-start gap-[14px]">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-primary font-bold">
                  {i + 1}
                </span>
                <span className="flex flex-col gap-[2px]">
                  <strong className="text-17">{s.title}</strong>
                  <span className="text-15 text-border-input">{s.text}</span>
                </span>
              </li>
            ))}
          </ol>
        </>
      }
    >
      <form
        className="flex w-full max-w-[400px] flex-col gap-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            const me = await apiPost<Me>("/api/auth/register", {
              first_name: name.trim(),
              email,
              password,
              accept_terms: terms,
            });
            qc.clear();
            qc.setQueryData(["me"], me);
            navigate("/onboarding/business", { replace: true });
          } catch (err) {
            setError(apiMessage(err, "Hisob yaratib bo'lmadi. Internet aloqasini tekshiring."));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-display text-32 font-bold">Hisob yaratish</h1>
          <span className="text-16 text-text-3">Bepul. Karta talab qilinmaydi.</span>
        </div>
        <div className="flex flex-col gap-[6px]">
          <label htmlFor="nm" className={LABEL}>
            Ismingiz
          </label>
          <input
            id="nm"
            type="text"
            required
            autoComplete="name"
            placeholder="Abdusamad Karimov"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={INPUT}
          />
        </div>
        <div className="flex flex-col gap-[6px]">
          <label htmlFor="em" className={LABEL}>
            Email
          </label>
          <input
            id="em"
            type="email"
            required
            autoComplete="email"
            placeholder="siz@misol.uz"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={INPUT}
          />
        </div>
        <div className="flex flex-col gap-[6px]">
          <label htmlFor="pw" className={LABEL}>
            Parol
          </label>
          <input
            id="pw"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            aria-describedby="pwh"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={INPUT}
          />
          <span id="pwh" className="text-13 text-text-4">
            Kamida 8 ta belgi
          </span>
        </div>
        <label className="flex cursor-pointer items-start gap-[10px] text-14 leading-[1.45] text-text-2">
          <input
            type="checkbox"
            required
            checked={terms}
            onChange={(e) => setTerms(e.target.checked)}
            className="m-0 h-5 w-5 shrink-0 accent-primary"
          />
          <span>
            <Link to="/">Foydalanish shartlari</Link> va <Link to="/">maxfiylik siyosati</Link>ga roziman
          </span>
        </label>
        {error && (
          <p role="alert" className="m-0 text-14 text-danger">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className={SUBMIT}>
          Hisob yaratish
        </button>
        <span className="text-center text-15 text-text-3">
          Hisobingiz bormi?{" "}
          <Link to="/login" className="font-semibold">
            Kirish
          </Link>
        </span>
      </form>
    </AuthLayout>
  );
}
