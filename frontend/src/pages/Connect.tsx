import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ConnectIntro, ConnectLayout, type ConnectStep } from "@/components/sources/ConnectLayout";
import {
  callbackError,
  DoneStep,
  GoogleStep,
  PickErrorBox,
  PickStep,
} from "@/components/sources/ConnectSteps";
import { MapStep } from "@/components/sources/MapStep";
import {
  errorText,
  invalidateFinance,
  isReauth,
  mergeProposals,
  normalizeProposals,
  safePath,
} from "@/components/sources/shared";
import type { RunResult } from "@/components/sources/useSseRun";
import { ErrorState, Skeleton } from "@/components/States";
import { apiGet, apiPost } from "@/lib/api";
import { useMe } from "@/lib/auth";
import type { GoogleStatus, Proposals } from "@/lib/sourcesTypes";

/** How long step 4 "Tayyor" stays on screen before following `redirect`. */
const DONE_DELAY_MS = 1500;
const REAUTH_TEXT = "Google ulanishi eskirdi. Davom etish uchun qayta ulang.";

function StepSkeleton() {
  return (
    <div className="flex flex-col gap-5" aria-busy="true" aria-label="Yuklanmoqda">
      <div className="flex flex-wrap gap-5">
        <Skeleton className="h-72 min-w-0 flex-[1_1_300px]" />
        <Skeleton className="h-72 min-w-0 flex-[999_1_560px]" />
      </div>
    </div>
  );
}

export default function ConnectPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const me = useMe();
  const businessName = me.data?.business?.name;

  const errorCode = params.get("error");
  const sourceParam = params.get("source");
  const remapId =
    params.get("step") === "map" && sourceParam && /^\d+$/.test(sourceParam) ? sourceParam : null;

  const status = useQuery({
    queryKey: ["google-status"],
    queryFn: () => apiGet<GoogleStatus>("/api/integrations/google/status"),
    enabled: remapId == null,
  });
  // POST, but read-only for the UI: one call per visit (StrictMode-safe via the query cache).
  const remap = useQuery({
    queryKey: ["remap", remapId],
    queryFn: () => apiPost<Proposals>(`/api/sources/${remapId}/remap`, {}),
    enabled: remapId != null,
    retry: false,
    staleTime: Infinity,
    gcTime: 0,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });

  const [local, setLocal] = useState<Proposals | null>(null);
  const [done, setDone] = useState<{ text: string; to: string } | null>(null);
  // Focus follows the step only after the user moved between steps, not on page load.
  const [moved, setMoved] = useState(false);
  const base = useMemo(() => (remap.data ? normalizeProposals(remap.data) : null), [remap.data]);
  const proposals = local ?? base;
  const fallbackRedirect = remapId ? "/sources" : "/";

  const onProposals = useCallback((p: Proposals) => {
    setMoved(true);
    setLocal((prev) => mergeProposals(prev, p));
  }, []);
  const onMerge = useCallback(
    (p: Proposals) => setLocal((prev) => mergeProposals(prev ?? base, p)),
    [base],
  );

  const onDone = (r: RunResult) => {
    invalidateFinance(qc);
    void qc.invalidateQueries({ queryKey: ["sources"] });
    void qc.invalidateQueries({ queryKey: ["google-status"] });
    setDone({ text: r.text || "Tayyor", to: safePath(r.redirect, fallbackRedirect) });
  };

  useEffect(() => {
    if (!done) return;
    const t = window.setTimeout(() => navigate(done.to, { replace: true }), DONE_DELAY_MS);
    return () => window.clearTimeout(t);
  }, [done, navigate]);

  const onBack = () => {
    if (remapId) {
      navigate("/sources");
      return;
    }
    setMoved(true);
    setLocal(null);
  };

  let step: ConnectStep;
  let body: ReactNode;
  if (done) {
    step = 4;
    body = <DoneStep text={done.text} to={done.to} />;
  } else if (proposals) {
    step = 3;
    body = (
      <MapStep
        proposals={proposals}
        businessName={businessName}
        onMerge={onMerge}
        onBack={onBack}
        onDone={onDone}
        autoFocus={moved}
      />
    );
  } else if (remapId) {
    step = 3;
    body = remap.isError ? (
      isReauth(remap.error) ? (
        <PickErrorBox error={{ message: errorText(remap.error, REAUTH_TEXT), reauth: true }} />
      ) : (
        <ErrorState error={remap.error} onRetry={() => void remap.refetch()} />
      )
    ) : (
      <StepSkeleton />
    );
  } else if (errorCode) {
    step = 1;
    body = (
      <GoogleStep
        error={callbackError(errorCode, params.get("message"))}
        needsReauth={false}
        businessName={businessName}
      />
    );
  } else if (status.isPending) {
    step = 1;
    body = <Skeleton className="h-64 w-[640px] max-w-full" />;
  } else if (status.isError) {
    step = 1;
    body = <ErrorState error={status.error} onRetry={() => void status.refetch()} />;
  } else if (!status.data.connected || status.data.needs_reauth) {
    step = 1;
    body = (
      <GoogleStep error={null} needsReauth={status.data.needs_reauth} businessName={businessName} />
    );
  } else {
    step = 2;
    body = (
      <PickStep
        email={status.data.email}
        businessName={businessName}
        onProposals={onProposals}
        autoFocus={moved}
      />
    );
  }

  return (
    <ConnectLayout step={step} finished={done != null}>
      <ConnectIntro full={step === 3} />
      {body}
    </ConnectLayout>
  );
}
