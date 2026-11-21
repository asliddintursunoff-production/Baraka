/** Chat API contract (docs/API_CHAT.md). All display text arrives formatted from the backend. */
import type { UiBlock } from "@/components/UiBlockRenderer";

export type AnswerVerdict = "yes" | "no" | "risky" | "info";

export interface Voice {
  duration: string;
}

export interface Plan {
  id: number;
  summary: string;
  status: "proposed" | "approved" | (string & {});
}

export interface Candidate {
  id: number;
  text: string;
  example: string;
  warning: string;
}

export interface Answer {
  verdict: AnswerVerdict;
  headline: string;
  reason: string;
  steps: string[];
  blocks: UiBlock[];
  chips: string[];
  plan: Plan | null;
  candidate: Candidate | null;
  explain: string[];
  speech: string;
  model: string;
}

export interface ChatMessage {
  id: number;
  role: "user" | "assistant";
  author: string;
  time: string;
  text: string;
  voice: Voice | null;
  answer: Answer | null;
}

export interface Brief {
  time: string;
  lead: string;
  strong: string;
  rest: string;
}

export interface Chip {
  id: string;
  label: string;
}

export interface BasisItem {
  icon: "sheets" | "rules" | "segment";
  title: string;
  note: string;
}

export interface Basis {
  items: BasisItem[];
  confidence: { label: string; level: "high" | "medium" | "low"; note: string } | null;
}

export interface ChatBootstrap {
  conversation_id: number;
  business_name: string;
  brief: Brief | null;
  messages: ChatMessage[];
  chips: Chip[];
  basis: Basis | null;
}

/** Body of POST /api/chat/messages (conversation_id is added by the page). */
export type SendPayload = ({ text: string; chip?: never } | { chip: string; text?: never }) & { voice?: Voice };

/** SSE events of POST /api/chat/messages, keyed by event name. */
export interface ChatStreamEvents {
  meta: { conversation_id: number; user_message_id: number };
  status: { text: string };
  blocks: { blocks: UiBlock[]; replace?: boolean };
  answer: Answer;
  done: { message_id: number; latency_ms: number; model: string };
  error: { message: string };
}

export interface ApproveResult {
  id: number;
  status: "approved";
  summary: string;
}

export interface AcceptResult {
  rule_id: number;
  text_uz: string;
  forecast_changed: boolean;
}

export interface TranscribeResult {
  text: string;
  duration: string;
}
