import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";

import { apiPost } from "@/lib/api";
import type { AcceptResult, ApproveResult } from "@/lib/chatTypes";

export type ActionStatus = "pending" | "done" | "error";

export interface AnswerActions {
  plans: Record<number, { status: ActionStatus; summary?: string }>;
  candidates: Record<number, ActionStatus>;
  approve: (planId: number) => void;
  accept: (candidateId: number) => void;
}

/**
 * Approve/accept state lives on the page (keyed by plan / candidate id), so it survives a
 * bubble being re-keyed when the bootstrap history is refetched.
 */
export function useAnswerActions(): AnswerActions {
  const qc = useQueryClient();
  const [plans, setPlans] = useState<AnswerActions["plans"]>({});
  const [candidates, setCandidates] = useState<AnswerActions["candidates"]>({});

  const approve = useCallback(
    (planId: number) => {
      setPlans((p) => ({ ...p, [planId]: { status: "pending" } }));
      apiPost<ApproveResult>(`/api/actions/${planId}/approve`, {})
        .then((r) => {
          setPlans((p) => ({ ...p, [planId]: { status: "done", summary: r?.summary } }));
          void qc.invalidateQueries({ queryKey: ["calendar"] });
        })
        .catch(() => setPlans((p) => ({ ...p, [planId]: { status: "error" } })));
    },
    [qc],
  );

  const accept = useCallback(
    (candidateId: number) => {
      setCandidates((c) => ({ ...c, [candidateId]: "pending" }));
      apiPost<AcceptResult>(`/api/knowledge/candidates/${candidateId}/accept`, {})
        .then(() => {
          setCandidates((c) => ({ ...c, [candidateId]: "done" }));
          for (const key of ["dashboard", "forecast", "calendar"]) void qc.invalidateQueries({ queryKey: [key] });
        })
        .catch(() => setCandidates((c) => ({ ...c, [candidateId]: "error" })));
    },
    [qc],
  );

  return useMemo(() => ({ plans, candidates, approve, accept }), [plans, candidates, approve, accept]);
}
