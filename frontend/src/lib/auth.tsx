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

export function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe();
  const location = useLocation();
  if (me.isPending) return null;
  if (me.error instanceof ApiError && (me.error.status === 401 || me.error.status === 403)) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}
