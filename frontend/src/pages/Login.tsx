import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { LogoMark } from "@/components/LogoMark";
import { ApiError, apiPost } from "@/lib/api";
import { appConfig } from "@/lib/config";
import type { Me } from "@/lib/types";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from ?? "/";

  return (
    <main className="flex min-h-screen items-center justify-center bg-bg px-4">
      <form
        className="flex w-full max-w-[400px] flex-col gap-4 rounded-card border border-border bg-surface p-7"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            const me = await apiPost<Me>("/api/auth/login", { email, password });
            qc.clear();
            qc.setQueryData(["me"], me);
            navigate(from, { replace: true });
          } catch (err) {
            const msg = err instanceof ApiError ? (err.body as { message?: string } | null)?.message : null;
            setError(msg ?? "Kirib bo'lmadi. Internet aloqasini tekshiring.");
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="flex items-center gap-[10px]">
          <LogoMark />
          <span className="font-display text-[19px] font-bold">{appConfig.appName}</span>
        </div>
        <h1 className="m-0 font-display text-24 font-bold">Kirish</h1>
        <label className="flex flex-col gap-1 text-14 font-semibold text-text-2">
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="min-h-tap rounded-btn border border-border-input px-3 text-15 font-normal"
          />
        </label>
        <label className="flex flex-col gap-1 text-14 font-semibold text-text-2">
          Parol
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="min-h-tap rounded-btn border border-border-input px-3 text-15 font-normal"
          />
        </label>
        {error && (
          <p role="alert" className="m-0 text-14 text-danger">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy}
          className="min-h-12 rounded-btn-lg bg-primary text-16 font-semibold text-white hover:bg-primary-hover disabled:opacity-60"
        >
          Kirish
        </button>
      </form>
    </main>
  );
}
