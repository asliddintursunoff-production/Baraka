import { useQuery } from "@tanstack/react-query";

import { apiGet } from "@/lib/api";
import { appConfig } from "@/lib/config";

interface Health {
  ok: boolean;
  app: string;
}

/** M0 placeholder; the real Main page (design/pages/Main.html) arrives in M2. */
export function HomePlaceholder() {
  const health = useQuery({ queryKey: ["health"], queryFn: () => apiGet<Health>("/api/health") });
  return (
    <main className="mx-auto max-w-[560px] px-4 py-7">
      <div className="flex items-center gap-[10px]">
        <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="#1D4ED8" />
          <path
            d="M9 21l5-6 4 3 5-7"
            stroke="#FFFFFF"
            strokeWidth="2.4"
            fill="none"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <h1 className="m-0 font-display text-[19px] font-bold">{appConfig.appName}</h1>
      </div>
      <p className="mt-4 text-15 text-text-3">
        API:{" "}
        {health.isPending ? "…" : health.data?.ok ? `ishlayapti (${health.data.app})` : "javob yo'q"}
      </p>
      <p className="text-15">
        <a href="/dev/voice">/dev/voice</a> — ovozli sinov sahifasi
      </p>
    </main>
  );
}
