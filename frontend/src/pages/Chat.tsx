import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { AnswerCard, hasCardContent } from "@/components/chat/AnswerCard";
import { BasisPanel } from "@/components/chat/BasisPanel";
import { AssistantRow, AssistantText, DaySeparator, metaLabel, UserMessage } from "@/components/chat/Bubbles";
import { Composer } from "@/components/chat/Composer";
import { SparkIcon, WaveIcon } from "@/components/chat/icons";
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
import { cn } from "@/lib/utils";

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
    <div className="flex flex-col gap-[22px]" aria-busy="true" aria-label="Yuklanmoqda">
      <Skeleton className="h-12 w-72 max-w-full" />
      <Skeleton className="h-24 w-[620px] max-w-full" />
      <Skeleton className="h-20 w-[420px] max-w-[85%] self-end" />
      <Skeleton className="h-80" />
      <Skeleton className="h-16" />
    </div>
  );
}

function AssistantTurn({
  turn,
  busy,
  onAsk,
  onEdit,
  actions,
}: {
  turn: Turn;
  busy: boolean;
  onAsk: (text: string) => void;
  onEdit: (text: string) => void;
  actions: AnswerActions;
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
      <AssistantText label={metaLabel(turn.author, turn.time)}>
        <RichText text={turn.text} />
      </AssistantText>
    );
  }
  return <AssistantRow live={turn.live}>{body}</AssistantRow>;
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
  const inputRef = useRef<HTMLInputElement>(null);
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

  // Keep the newest bubble visible above the sticky composer. A bubble taller than the
  // screen is scrolled to its top so the verdict is read first.
  const [newPill, setNewPill] = useState(false);
  const nearBottom = useRef(true);
  useEffect(() => {
    const onScroll = () => {
      const room = window.innerHeight - (composerRef.current?.offsetHeight ?? 0);
      const el = lastTurnRef.current;
      nearBottom.current = !el || el.getBoundingClientRect().top < room + 120;
      if (nearBottom.current) setNewPill(false);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  useEffect(() => {
    const el = lastTurnRef.current;
    if (!el) return;
    if (scrolledOnce.current && !nearBottom.current) {
      setNewPill(true); // the user scrolled up to read: don't yank the page
      return;
    }
    const smooth = scrolledOnce.current && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    scrolledOnce.current = true;
    const room = window.innerHeight - (composerRef.current?.offsetHeight ?? 0);
    const r = el.getBoundingClientRect();
    const delta = r.height > room - 32 ? r.top - 16 : r.bottom - room + 16;
    if (delta > 0) window.scrollBy({ top: delta, behavior: smooth ? "smooth" : "auto" });
  }, [scrollKey]);

  return (
    <div className="-mx-4 -mb-12 -mt-7 flex min-h-screen flex-wrap md:-mx-9">
      <div className="flex min-w-0 flex-[999_1_560px] flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-surface px-4 py-[18px] sm:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-inner bg-ink" aria-hidden="true">
              <SparkIcon size={20} strokeWidth={2} />
            </div>
            <div className="flex min-w-0 flex-col gap-[2px]">
              <h1 className="m-0 font-display text-20 font-bold">AI CFO</h1>
              {boot.business_name && (
                <span className="text-13 text-text-3">{boot.business_name}'ning moliyaviy maslahatchisi</span>
              )}
            </div>
          </div>
          <Link
            to="/live"
            onMouseEnter={prefetchLive}
            onFocus={prefetchLive}
            className="inline-flex min-h-tap items-center gap-[10px] rounded-pill bg-ink px-[18px] text-15 font-semibold text-white no-underline hover:text-white"
          >
            <WaveIcon />
            Jonli gaplashish
          </Link>
        </header>

        <div className="mx-auto box-border flex w-full max-w-[900px] grow flex-col gap-[22px] px-4 py-7 sm:px-8">
          <DaySeparator label="Bugun" />
          {boot.brief && (
            <AssistantRow>
              <AssistantText label={metaLabel("AI CFO", boot.brief.time)}>
                <RichText text={boot.brief.lead} /> <strong>{boot.brief.strong}</strong> <RichText text={boot.brief.rest} />
              </AssistantText>
            </AssistantRow>
          )}
          {turns.map((t, i) => (
            <div key={t.key} ref={i === turns.length - 1 ? lastTurnRef : undefined}>
              {t.role === "user" ? (
                <UserMessage label={metaLabel(t.author, t.time)} text={t.text} voice={t.voice} />
              ) : (
                <AssistantTurn turn={t} busy={busy} onAsk={ask} onEdit={editCandidate} actions={actions} />
              )}
            </div>
          ))}
        </div>

        {newPill && (
          <button
            type="button"
            onClick={() => {
              setNewPill(false);
              nearBottom.current = true;
              lastTurnRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
            }}
            className="fixed bottom-28 left-1/2 z-20 -translate-x-1/2 rounded-pill bg-ink px-4 py-2 text-14 font-semibold text-white shadow-lg"
          >
            ↓ yangi xabar
          </button>
        )}
        <Composer
          chips={boot.chips ?? []}
          busy={busy}
          value={draft}
          onChange={setDraft}
          onSend={onComposerSend}
          inputRef={inputRef}
          containerRef={composerRef}
        />
      </div>

      <BasisPanel basis={boot.basis} />
    </div>
  );
}

export default function ChatPage() {
  const [sel, setSel] = useState<{ id?: number; isNew?: boolean }>({});
  const url = sel.isNew
    ? "/api/chat/bootstrap?new=1"
    : sel.id
      ? `/api/chat/bootstrap?conversation_id=${sel.id}`
      : "/api/chat/bootstrap";
  const q = useQuery({
    queryKey: ["chat", "bootstrap", sel.isNew ? `new-${sel.id ?? 0}` : (sel.id ?? "last")],
    queryFn: () => apiGet<ChatBootstrap & { conversations?: ConvRow[] }>(url),
    // History is merged with bubbles streamed in this session; refetch only on mount/invalidation.
    refetchOnWindowFocus: false,
    staleTime: Infinity,
  });

  if (q.isPending)
    return (
      <AppShell active="chat">
        <ChatSkeleton />
      </AppShell>
    );
  if (q.isError)
    return (
      <AppShell active="chat">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </AppShell>
    );
  const convs = q.data.conversations ?? [];
  return (
    <AppShell active="chat">
      <div className="flex min-h-0 w-full flex-1">
        <aside className="hidden w-[230px] shrink-0 flex-col gap-1 border-r border-border bg-surface p-3 lg:flex">
          <button
            type="button"
            onClick={() => setSel({ isNew: true, id: Date.now() })}
            className="mb-2 rounded-card bg-ink px-3 py-2 text-left text-14 font-semibold text-white"
          >
            + Yangi chat
          </button>
          <div className="flex flex-col gap-0.5 overflow-y-auto">
            {convs.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => setSel({ id: c.id })}
                className={cn(
                  "truncate rounded-inner px-2 py-1.5 text-left text-13",
                  c.id === q.data.conversation_id ? "bg-[#EEF4FF] font-semibold text-primary" : "text-text-2 hover:bg-bg",
                )}
                title={c.title}
              >
                {c.channel === "voice" ? "🎙 " : ""}
                {c.title}
              </button>
            ))}
          </div>
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <button
            type="button"
            onClick={() => setSel({ isNew: true, id: Date.now() })}
            className="m-2 self-start rounded-card border border-border px-3 py-1.5 text-13 font-semibold lg:hidden"
          >
            + Yangi chat
          </button>
          <ChatView key={q.data.conversation_id} boot={q.data} />
        </div>
      </div>
    </AppShell>
  );
}

interface ConvRow {
  id: number;
  title: string;
  channel: string;
  date: string;
}
