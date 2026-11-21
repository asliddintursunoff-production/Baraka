import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiMessage, INPUT, LABEL, SUBMIT } from "@/components/public/AuthLayout";
import { ConnectLayout } from "@/components/sources/ConnectLayout";
import { ArrowRightIcon, LockIcon } from "@/components/sources/icons";
import { apiPost } from "@/lib/api";
import type { Me } from "@/lib/types";
import { cn } from "@/lib/utils";

const KINDS = [
  { value: "cafe", label: "Kafe / restoran" },
  { value: "shop", label: "Do'kon" },
  { value: "pharmacy", label: "Dorixona" },
  { value: "other", label: "Boshqa" },
] as const;
const CITIES = ["Toshkent", "Samarqand", "Buxoro", "Andijon", "Boshqa"];

export default function OnboardingPage() {
  const [name, setName] = useState("");
  const [kind, setKind] = useState<string>("cafe");
  const [city, setCity] = useState(CITIES[0]!);
  const [staff, setStaff] = useState("");
  const [salaryDay, setSalaryDay] = useState("");
  const [safeMin, setSafeMin] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  return (
    <ConnectLayout step={1} mainClassName="max-w-[1100px] flex-row flex-wrap items-start gap-7">
      <form
        className="flex min-w-0 flex-[999_1_520px] flex-col gap-[22px] rounded-[20px] border border-border bg-surface p-8"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            const me = await apiPost<Me>("/api/onboarding/business", {
              name: name.trim(),
              kind,
              city,
              staff_count: Number(staff),
              salary_day: Number(salaryDay),
              ...(safeMin.trim() ? { safe_min: safeMin.trim() } : {}),
            });
            qc.setQueryData(["me"], me);
            navigate("/onboarding/connect", { replace: true });
          } catch (err) {
            setError(apiMessage(err, "Saqlab bo'lmadi. Internet aloqasini tekshiring."));
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="flex flex-col gap-2">
          <h1 className="m-0 font-display text-30 font-bold">Biznesingiz haqida</h1>
          <span className="text-16 text-text-3">Bir daqiqa. AI hisob-kitobni shunga moslaydi.</span>
        </div>

        <div className="flex flex-col gap-[6px]">
          <label htmlFor="bn" className={LABEL}>
            Biznes nomi
          </label>
          <input
            id="bn"
            type="text"
            required
            placeholder="Masalan: Navro'z Kafe"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className={INPUT}
          />
        </div>

        <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
          <legend className="pb-2 text-14 font-semibold text-text-2">Turi</legend>
          <div className="flex flex-wrap gap-2">
            {KINDS.map((k) => (
              <button
                key={k.value}
                type="button"
                aria-pressed={kind === k.value}
                onClick={() => setKind(k.value)}
                className={cn(
                  "min-h-tap cursor-pointer rounded-pill px-4 font-sans text-15",
                  kind === k.value
                    ? "border-2 border-primary bg-primary-soft font-bold text-primary"
                    : "border border-border-input bg-surface font-semibold text-text-2",
                )}
              >
                {k.label}
              </button>
            ))}
          </div>
        </fieldset>

        <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
          <div className="flex flex-col gap-[6px]">
            <label htmlFor="ct" className={LABEL}>
              Shahar
            </label>
            <select id="ct" value={city} onChange={(e) => setCity(e.target.value)} className={cn(INPUT, "bg-surface px-3")}>
              {CITIES.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-[6px]">
            <label htmlFor="st" className={LABEL}>
              Xodimlar soni
            </label>
            <input
              id="st"
              type="number"
              min={0}
              required
              placeholder="15"
              value={staff}
              onChange={(e) => setStaff(e.target.value)}
              className={INPUT}
            />
          </div>
          <div className="flex flex-col gap-[6px]">
            <label htmlFor="pd" className={LABEL}>
              Oylik har oyning nechanchi sanasida?
            </label>
            <input
              id="pd"
              type="number"
              min={1}
              max={31}
              required
              placeholder="10"
              value={salaryDay}
              onChange={(e) => setSalaryDay(e.target.value)}
              className={INPUT}
            />
          </div>
          <div className="flex flex-col gap-[6px]">
            <label htmlFor="sm" className={LABEL}>
              Kassada doim qolsin (so'm)
            </label>
            <input
              id="sm"
              type="text"
              inputMode="numeric"
              placeholder="10 000 000"
              aria-describedby="smh"
              value={safeMin}
              onChange={(e) => setSafeMin(e.target.value)}
              className={INPUT}
            />
            <span id="smh" className="text-13 text-text-4">
              Ixtiyoriy. Bundan pastga tushsa, AI ogohlantiradi.
            </span>
          </div>
        </div>

        {error && (
          <p role="alert" className="m-0 text-14 text-danger">
            {error}
          </p>
        )}
        <div className="flex flex-wrap justify-end gap-3 pt-1">
          <button type="submit" disabled={busy} className={SUBMIT}>
            Davom etish: jadval ulash
            <ArrowRightIcon />
          </button>
        </div>
      </form>

      <aside aria-label="Nega so'raymiz" className="flex min-w-0 flex-[1_1_280px] flex-col gap-[14px]">
        <div className="flex flex-col gap-[10px] rounded-card bg-ink p-[22px] text-white">
          <span className="text-12 font-bold tracking-label text-[#B2CCFF]">NEGA SO'RAYMIZ</span>
          <span className="text-15 leading-[1.55]">
            Oylik kuni va xodimlar soni — eng muhim to'lovni to'g'ri hisoblash uchun. Turi va shahri — shunga
            o'xshash bizneslarning umumiy tajribasidan foydalanish uchun.
          </span>
        </div>
        <div className="flex gap-[10px] rounded-card border border-border bg-surface p-[18px] text-14 leading-[1.5] text-text-3">
          <LockIcon />
          <span>Hammasini keyin sozlamalarda o'zgartirish mumkin.</span>
        </div>
      </aside>
    </ConnectLayout>
  );
}
