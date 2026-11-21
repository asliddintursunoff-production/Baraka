import { useCallback, useEffect, useRef, useState } from "react";

import type { SourcesStreamEvents } from "@/lib/sourcesTypes";
import { postSse } from "@/lib/sse";

import { errorText, isReauth, STREAM_FAILED } from "./shared";

export type RunState =
  | { status: "idle" }
  | { status: "running"; text: string; pct: number | null }
  | { status: "done"; text: string; redirect: string | null }
  | { status: "error"; message: string; reauth: boolean };

export interface RunResult {
  text: string;
  redirect: string | null;
}

/** One SSE job (`/api/sources/confirm`, `/api/sources/sync`): progress → done | error. */
export function useSseRun() {
  const [state, setState] = useState<RunState>({ status: "idle" });
  const ctrlRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const ref = ctrlRef;
    return () => ref.current?.abort();
  }, []);

  const run = useCallback(
    async (url: string, body: unknown, startText: string): Promise<RunResult | null> => {
      ctrlRef.current?.abort();
      const ctrl = new AbortController();
      ctrlRef.current = ctrl;
      setState({ status: "running", text: startText, pct: null });
      let result = null as RunResult | null;
      let failed = false;
      try {
        await postSse<SourcesStreamEvents>(
          url,
          body,
          {
            progress: (d) =>
              setState((prev) => ({
                status: "running",
                text: d?.text || (prev.status === "running" ? prev.text : startText),
                pct:
                  typeof d?.pct === "number" && Number.isFinite(d.pct)
                    ? d.pct
                    : prev.status === "running"
                      ? prev.pct
                      : null,
              })),
            done: (d) => {
              result = { text: d?.text ?? "", redirect: d?.redirect ?? null };
              setState({ status: "done", ...result });
            },
            error: (d) => {
              failed = true;
              setState({ status: "error", message: d?.message || STREAM_FAILED, reauth: false });
            },
          },
          ctrl.signal,
        );
        if (!result && !failed) {
          failed = true;
          setState({ status: "error", message: STREAM_FAILED, reauth: false });
        }
      } catch (e) {
        if (ctrl.signal.aborted) return null;
        failed = true;
        setState({ status: "error", message: errorText(e, STREAM_FAILED), reauth: isReauth(e) });
      } finally {
        if (ctrlRef.current === ctrl) ctrlRef.current = null;
      }
      return failed ? null : result;
    },
    [],
  );

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return { state, run, reset };
}
