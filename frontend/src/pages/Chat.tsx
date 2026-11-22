import { useQuery } from "@tanstack/react-query";
import { ArrowDown } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { AnswerCard, hasCardContent } from "@/components/chat/AnswerCard";
import { AssistantRow, AssistantText, MessageActions, MessageUser, metaLabel } from "@/components/chat/Bubbles";
import { ChatHeader, SuggestionGrid } from "@/components/chat/ChatChrome";
import { Composer } from "@/components/chat/Composer";
import { HistoryList, type ConvRow } from "@/components/chat/HistoryList";
import { WaveIcon } from "@/components/chat/icons";
import { LearningCard } from "@/components/chat/LearningCard";
import { prefetchLive } from "@/components/chat/live";
import { StreamingCard } from "@/components/chat/StreamingCard";
import { useAnswerActions, type AnswerActions } from "@/components/chat/useAnswerActions";
import { RichText } from "@/components/RichText";
import { ErrorState, Skeleton } from "@/components/States";
import type { UiBlock } from "@/components/UiBlockRenderer";
import { ApiError, apiGet } from "@/lib/api";
import type { Answer, ChatBootstrap, ChatMessage, ChatStreamEvents, SendPayload, Voice } from "@/lib/chatTypes";
import { postSse } from "@/lib/sse";
import { track } from "@/lib/telemetry";

const STREAM_FAILED = "Javob olib bo'lmadi. Internet aloqasini tekshirib, qaytadan urinib ko'ring.";

/** One bubble: a history message from bootstrap, or one sent/streamed in this session. */
interface Turn {
  key: string;
  serverId: number | null;
  role: "user" | "assistant";
  author: string;
  time: string;
  text: string;
  voice: Voice | null;
  answer: Answer | null;
  /** Streamed in this session (gets `aria-live`). */
  live: boolean;
  pending: boolean;
  status: string | null;
  blocks: UiBlock[] | null;
  error: string | null;
  /** Markdown received so far from `delta` events. */
  stream: string;
}

let keySeq = 0;
const nextKey = () => `local-${++keySeq}`;

function fromServer(m: ChatMessage): Turn {
  return {
    key: `msg-${m.id}`,
    serverId: m.id,
    role: m.role,
    author: m.author,
    time: m.time,
    text: m.text ?? "",
    voice: m.voice ?? null,
    answer: m.answer ?? null,
    live: false,
    pending: false,
    status: null,
    blocks: null,
    error: null,
    stream: "",
  };
}

function ChatSkeleton() {
  return (
    <div className="mx-auto flex w-full max-w-chat flex-col gap-6 px-4 py-8 md:px-6" aria-busy="true" aria-label="Yuklanmoqda">
      <Skeleton className="h-12 w-72 max-w-full" />
      <Skeleton className="h-24 w-[620px] max-w-full" />
      <Skeleton className="h-20 w-[420px] max-w-[85%] self-end" />
      <Skeleton className="h-80" />
      <Skeleton className="h-16" />
    </div>
  );
}

function answerText(t: Turn): string {
  const a = t.answer;
  if (!a) return t.stream || t.text;
  return (a.markdown ?? "").trim() || [a.headline, a.reason].filter(Boolean).join("\n\n").replace(/\*\*/g, "");
}

function AssistantTurn({
  turn,
  busy,
  onAsk,
  onEdit,
  actions,
  regenerate,
}: {
  turn: Turn;
  busy: boolean;
  onAsk: (text: string) => void;
  onEdit: (text: string) => void;
  actions: AnswerActions;
  /** The question this answer replied to ("Qayta javob" asks it again). */
  regenerate?: string;
}) {
  const a = turn.answer;
  let body: ReactNode;
  if (a) {
    const card = <AnswerCard answer={a} messageId={turn.serverId} busy={busy} onAsk={onAsk} actions={actions} />;
    const c = a.candidate;
    const learning = c && (
      <LearningCard
        candidate={c}
        status={actions.candidates[c.id]}
        onAccept={() => actions.accept(c.id)}
        onEdit={() => onEdit(c.text)}
      />
    );
    body = learning ? (
      hasCardContent(a) ? (
        <>
          {card}
          {learning}
        </>
      ) : (
        learning
      )
    ) : (
      card
    );
  } else if (turn.pending || turn.error || (turn.blocks?.length ?? 0) > 0 || turn.stream) {
    body = (
      <StreamingCard
        status={turn.status}
        pending={turn.pending}
        blocks={turn.blocks}
        error={turn.error}
        markdown={turn.stream}
      />
    );
  } else {
    body = (
      <AssistantText>
        <RichText text={turn.text} />
      </AssistantText>
    );
  }
  const done = !turn.pending && !turn.error;
  return (
    <AssistantRow live={turn.live} footer={done ? <MessageActions text={answerText(turn)} onRegenerate={regenerate ? () => onAsk(regenerate) : undefined} busy={busy} /> : null}>
      {body}
    </AssistantRow>
  );
}

function ChatView({ boot }: { boot: ChatBootstrap }) {
  const actions = useAnswerActions();
  const [local, setLocal] = useState<Turn[]>([]);
  const [localConv, setLocalConv] = useState(boot.conversation_id);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const busyRef = useRef(false);
  const convRef = useRef(boot.conversation_id);
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const composerRef = useRef<HTMLDivElement>(null);
  const lastTurnRef = useRef<HTMLDivElement>(null);
  const scrolledOnce = useRef(false);

  // Another business (another conversation) was loaded: drop this session's bubbles.
  if (localConv !== boot.conversation_id) {
    setLocalConv(boot.conversation_id);
    setLocal([]);
  }

  useEffect(() => {
    convRef.current = boot.conversation_id;
  }, [boot.conversation_id]);

  useEffect(() => {
    const ref = abortRef;
    return () => ref.current?.abort();
  }, []);

  const patch = useCallback((key: string, fn: (t: Turn) => Turn) => {
    setLocal((prev) => prev.map((t) => (t.key === key ? fn(t) : t)));
  }, []);

  const send = useCallback(
    async (payload: SendPayload, display: string) => {
      if (busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      const userKey = nextKey();
      const botKey = nextKey();
      const now = new Date().toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit", hour12: false });
      const base = { serverId: null, answer: null, status: null, blocks: null, error: null, time: now, stream: "" };
      setLocal((prev) => [
        ...prev,
        { ...base, key: userKey, role: "user", author: "Siz", text: display, voice: payload.voice ?? null, live: false, pending: false },
        { ...base, key: botKey, role: "assistant", author: "AI CFO", text: "", voice: null, live: true, pending: true },
      ]);
      const bot = (fn: (t: Turn) => Turn) => patch(botKey, fn);
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const t0 = performance.now();
      const meta = { kind: payload.chip ? "chip" : payload.voice ? "voice" : "text" };
      let sawBlocks = false;
      let finished = false;
      try {
        await postSse<ChatStreamEvents>(
          "/api/chat/messages",
          { ...payload, conversation_id: convRef.current },
          {
            meta: (d) => {
              if (d?.conversation_id) convRef.current = d.conversation_id;
              patch(userKey, (t) => ({ ...t, serverId: d?.user_message_id ?? null }));
            },
            status: (d) => bot((t) => ({ ...t, status: d?.text ?? t.status })),
            delta: (d) => {
              const chunk = typeof d?.text === "string" ? d.text : "";
              if (chunk) bot((t) => ({ ...t, stream: t.stream + chunk }));
            },
            blocks: (d) => {
              if (!sawBlocks) {
                sawBlocks = true;
                track("chat", "send_to_blocks", performance.now() - t0, meta);
              }
              const next = d?.blocks ?? [];
              bot((t) => ({ ...t, blocks: d?.replace === false ? [...(t.blocks ?? []), ...next] : next }));
            },
            answer: (d) => {
              finished = true;
              track("chat", "send_to_answer", performance.now() - t0, meta);
              bot((t) => ({ ...t, answer: d }));
            },
            done: (d) => bot((t) => ({ ...t, serverId: d?.message_id ?? null })),
            error: (d) => {
              finished = true;
              bot((t) => ({ ...t, error: d?.message || STREAM_FAILED }));
            },
          },
          ctrl.signal,
        );
        // Stream closed without an answer or error: keep cards that arrived, otherwise say so.
        if (!finished) bot((t) => ((t.blocks?.length ?? 0) > 0 || t.stream ? t : { ...t, error: STREAM_FAILED }));
      } catch (e) {
        if (!ctrl.signal.aborted) {
          const body = e instanceof ApiError ? (e.body as { message?: string } | null) : null;
          bot((t) => ({ ...t, error: body?.message || STREAM_FAILED }));
        }
      } finally {
        if (abortRef.current === ctrl) abortRef.current = null;
        if (!ctrl.signal.aborted) {
          bot((t) => ({ ...t, pending: false }));
          busyRef.current = false;
          setBusy(false);
        }
      }
    },
    [patch],
  );

  const ask = useCallback((text: string) => void send({ text }, text), [send]);
  const onComposerSend = useCallback((p: SendPayload, display: string) => void send(p, display), [send]);
  const editCandidate = useCallback((text: string) => {
    setDraft(text.replace(/\*\*/g, ""));
    inputRef.current?.focus();
  }, []);

  const turns = useMemo(() => {
    const serverIds = new Set(boot.messages.map((m) => m.id));
    const fresh = localConv === boot.conversation_id ? local : [];
    return [
      ...boot.messages.map(fromServer),
      ...fresh.filter((t) => t.serverId == null || !serverIds.has(t.serverId)),
    ];
  }, [boot.messages, boot.conversation_id, local, localConv]);

  const last = turns[turns.length - 1];
  const scrollKey = last
    ? `${turns.length}|${last.key}|${last.status ?? ""}|${last.blocks?.length ?? 0}|${Math.floor(last.stream.length / 240)}|${last.answer ? 1 : 0}|${last.error ? 1 : 0}`
    : "";

  const stop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    busyRef.current = false;
    setBusy(false);
    setLocal((prev) =>
      prev.map((t) => (t.pending ? { ...t, pending: false, error: t.answer || t.stream || t.blocks?.length ? null : "To'xtatildi." } : t)),
    );
  }, []);

  // The list always ends above the composer: bottom padding = composer height + 24px.
  const [pad, setPad] = useState(160);
  useLayoutEffect(() => {
    const el = composerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setPad(el.offsetHeight + 24));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // Auto-scroll only when the reader is near the bottom (≤120px); otherwise offer "↓".
  const [down, setDown] = useState(false);
  const nearBottom = useRef(true);
  useEffect(() => {
    const onScroll = () => {
      const gap = document.documentElement.scrollHeight - (window.scrollY + window.innerHeight);
      nearBottom.current = gap < 120;
      setDown(!nearBottom.current);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  const toBottom = useCallback((smooth: boolean) => {
    window.scrollTo({ top: document.documentElement.scrollHeight, behavior: smooth ? "smooth" : "auto" });
  }, []);
  useEffect(() => {
    if (!lastTurnRef.current) return;
    if (!scrolledOnce.current) {
      scrolledOnce.current = true;
      toBottom(false); // opening an old chat: jump, no animation
      return;
    }
    if (nearBottom.current) toBottom(!window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }, [scrollKey, toBottom]);

  const prevUser = (i: number) => {
    for (let j = i - 1; j >= 0; j--) if (turns[j]?.role === "user") return turns[j]?.text ?? "";
    return "";
  };

  return (
    <div className="flex min-h-dvh flex-col md:min-h-dvh">
      <ChatHeader businessName={boot.business_name} basis={boot.basis} />
      <div className="mx-auto box-border flex w-full max-w-chat grow flex-col gap-6 px-4 pt-6 md:px-6" style={{ paddingBottom: pad }}>
        {turns.length === 0 ? (
          <SuggestionGrid brief={boot.brief} disabled={busy} onAsk={ask} />
        ) : (
          turns.map((t, i) => (
            <div key={t.key} ref={i === turns.length - 1 ? lastTurnRef : undefined}>
              {t.role === "user" ? (
                <MessageUser label={metaLabel(t.author, t.time)} text={t.text} voice={t.voice} />
              ) : (
                <AssistantTurn
                  turn={t}
                  busy={busy}
                  onAsk={ask}
                  onEdit={editCandidate}
                  actions={actions}
                  regenerate={prevUser(i)}
                />
              )}
            </div>
          ))
        )}
      </div>

      {down && turns.length > 0 && (
        <button
          type="button"
          aria-label="Pastga"
          onClick={() => toBottom(true)}
          style={{ bottom: pad }}
          className="fixed left-1/2 z-30 grid size-10 -translate-x-1/2 place-items-center rounded-full border border-border bg-surface text-ink shadow-lg md:left-[calc(50%+32px)] lg:left-[calc(50%+130px)]"
        >
          <ArrowDown size={18} />
        </button>
      )}
      <Composer
        busy={busy}
        value={draft}
        onChange={setDraft}
        onSend={onComposerSend}
        onStop={stop}
        inputRef={inputRef}
        containerRef={composerRef}
      />
    </div>
  );
}

export default function ChatPage() {
  const [params] = useSearchParams();
  const isNew = params.get("new");
  const cid = params.get("c");
  const url = isNew ? "/api/chat/bootstrap?new=1" : cid ? `/api/chat/bootstrap?conversation_id=${cid}` : "/api/chat/bootstrap";
  const q = useQuery({
    queryKey: ["chat", "bootstrap", isNew ? `new-${isNew}` : (cid ?? "last")],
    queryFn: () => apiGet<ChatBootstrap & { conversations?: ConvRow[] }>(url),
    // History is merged with bubbles streamed in this session; refetch only on mount/invalidation.
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  });
  const convs = q.data?.conversations ?? [];
  const live = (
    <Link to="/live" aria-label="Jonli gaplashish" onMouseEnter={prefetchLive} className="grid size-tap place-items-center rounded-full bg-ink no-underline">
      <WaveIcon size={20} />
    </Link>
  );
  const history = <HistoryList items={convs} activeId={q.data?.conversation_id} />;
  let body: ReactNode;
  if (q.isPending) body = <ChatSkeleton />;
  else if (q.isError)
    body = (
      <div className="p-6">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </div>
    );
  else body = <ChatView key={q.data.conversation_id} boot={q.data} />;
  return (
    <AppShell active="chat" bleed hideTabs history={history} action={live}>
      {body}
    </AppShell>
  );
}
