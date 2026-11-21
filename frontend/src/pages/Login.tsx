import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { apiMessage, AuthLayout, INPUT, LABEL, SUBMIT } from "@/components/public/AuthLayout";
import { apiPost } from "@/lib/api";
import { stepRoute } from "@/lib/auth";
import type { Me } from "@/lib/types";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;

  return (
    <AuthLayout
      asideLabel="Mahsulot haqida"
      aside={
        <>
          <h2 className="m-0 max-w-[460px] font-display text-[34px] font-bold leading-[1.2]">
            Bugun kassangizda nima bo'ladi — AI allaqachon hisoblab qo'ygan
          </h2>
          <div className="flex max-w-[460px] flex-col gap-2 rounded-card bg-surface p-[18px] text-ink">
            <span className="text-12 font-bold tracking-label text-primary">BUGUNGI MASLAHAT · 08:00</span>
            <span className="font-display text-[19px] font-bold">
              Pulingiz yetadi. Faqat 10-dekabrga ehtiyot bo'ling.
            </span>
            <span className="text-14 text-text-3">Namuna</span>
          </div>
        </>
      }
    >
      <form
        className="flex w-full max-w-[400px] flex-col gap-[18px]"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            const me = await apiPost<Me>("/api/auth/login", { email, password });
            qc.clear();
            qc.setQueryData(["me"], me);
            const step = stepRoute(me);
            navigate(step === "/dashboard" ? (from ?? step) : step, { replace: true });
          } catch (err) {
            setError(apiMessage(err, "Kirib bo'lmadi. Internet aloqasini tekshiring."));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-display text-32 font-bold">Xush kelibsiz</h1>
          <span className="text-16 text-text-3">Hisobingizga kiring</span>
        </div>
        <div className="flex flex-col gap-[6px]">
          <label htmlFor="email" className={LABEL}>
            Email
          </label>
          <input
            id="email"
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
          <div className="flex items-baseline justify-between">
            <label htmlFor="pw" className={LABEL}>
              Parol
            </label>
            <Link to="/login" className="text-14 font-semibold">
              Parolni unutdingizmi?
            </Link>
          </div>
          <input
            id="pw"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className={INPUT}
          />
        </div>
        {error && (
          <p role="alert" className="m-0 text-14 text-danger">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className={SUBMIT}>
          Kirish
        </button>
        <span className="text-center text-15 text-text-3">
          Hisobingiz yo'qmi?{" "}
          <Link to="/register" className="font-semibold">
            Ro'yxatdan o'ting
          </Link>
        </span>
      </form>
    </AuthLayout>
  );
}
