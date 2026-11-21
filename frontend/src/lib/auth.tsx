import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { ApiError, apiGet, apiPost } from "./api";
import type { Me } from "./types";

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => apiGet<Me>("/api/me"),
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export function useSwitchBusiness() {
  const qc = useQueryClient();
  return async (businessId: number) => {
    const me = await apiPost<Me>("/api/me/business", { business_id: businessId });
    qc.setQueryData(["me"], me);
    await qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "me" });
  };
}

/** Route of the user's current onboarding step, or `/dashboard` when onboarding is done. */
export function stepRoute(me: Me | undefined): string {
  switch (me?.onboarding_step) {
    case "business":
      return "/onboarding/business";
    case "connect":
    case "review":
      return "/onboarding/connect";
    case "analyzing":
      return "/onboarding/analyzing";
    default:
      return "/dashboard";
  }
}

function isAnonymous(error: unknown): boolean {
  return error instanceof ApiError && (error.status === 401 || error.status === 403);
}

/**
 * App routes: anonymous → /login; unfinished onboarding → the current step.
 * `onboarding` routes are always allowed for a logged-in user.
 */
export function RequireAuth({ children, onboarding = false }: { children: ReactNode; onboarding?: boolean }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return null;
  if (isAnonymous(me.error)) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (!onboarding && me.data && (me.data.onboarding_step ?? "done") !== "done") {
    return <Navigate to={stepRoute(me.data)} replace />;
  }
  return <>{children}</>;
}

/** `/`, `/login`, `/register`: a logged-in user goes to the current step (or /dashboard). */
export function PublicOnly({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) return null;
  if (me.data) return <Navigate to={stepRoute(me.data)} replace />;
  return <>{children}</>;
}
