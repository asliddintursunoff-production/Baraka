import { useCallback, useRef, useState } from "react";

import { apiGet, apiPost } from "@/lib/api";
import { loadPicker, openPicker } from "@/lib/googlePicker";
import type { PickerConfig, Proposals } from "@/lib/sourcesTypes";

import { errorText, isReauth } from "./shared";

export type PickPhase = "idle" | "opening" | "picking" | "reading";

export interface PickError {
  message: string;
  reauth: boolean;
}

const READ_FAILED = "Fayllarni o'qib bo'lmadi. Qaytadan urinib ko'ring.";

/** picker-config → Google Picker → `POST /api/sources {file_ids}` → proposals. */
export function usePickFiles(onProposals: (p: Proposals) => void) {
  const [phase, setPhase] = useState<PickPhase>("idle");
  const [error, setError] = useState<PickError | null>(null);
  const busy = useRef(false);

  const pick = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setError(null);
    setPhase("opening");
    try {
      // A fresh short-lived token every time the Picker opens.
      const [cfg] = await Promise.all([
        apiGet<PickerConfig>("/api/integrations/google/picker-config"),
        loadPicker(),
      ]);
      setPhase("picking");
      const ids = await openPicker(cfg);
      if (ids.length === 0) return;
      setPhase("reading");
      const proposals = await apiPost<Proposals>("/api/sources", { file_ids: ids });
      onProposals(proposals);
    } catch (e) {
      setError({ message: errorText(e, READ_FAILED), reauth: isReauth(e) });
    } finally {
      busy.current = false;
      setPhase("idle");
    }
  }, [onProposals]);

  return { phase, error, pick };
}
