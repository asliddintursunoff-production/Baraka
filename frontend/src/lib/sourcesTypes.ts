/** Google / Sources API contract (docs/API_SOURCES.md). All texts arrive in Uzbek, already formatted. */

export interface GoogleStatus {
  connected: boolean;
  email: string | null;
  needs_reauth: boolean;
}

/** `GET /api/integrations/google/picker-config` (short-lived token). */
export interface PickerConfig {
  access_token: string;
  developer_key: string;
  app_id: string;
  expires_at?: string;
}

export interface Option {
  value: string;
  label: string;
}

export interface ColumnProposal {
  index: number;
  header: string;
  sample: string;
  field: string | null;
  field_label: string;
  confidence: number;
  status: "sure" | "confirm";
  question: string | null;
}

export interface SheetProposal {
  title: string;
  rows: number;
  rows_display: string;
  header_row: number;
  kind: string;
  kind_label: string;
  recognized: string;
  columns: ColumnProposal[];
}

export interface SourceProposal {
  id: number;
  title: string;
  kind: "google_sheet" | "xlsx";
  summary: string;
  sheets: SheetProposal[];
}

export interface IssuePreview {
  source_id: number;
  sheet: string;
  row: number | string;
  message: string;
  action_label: string;
}

export interface Proposals {
  sources: SourceProposal[];
  field_options: Option[];
  kind_options: Option[];
  issues_preview: IssuePreview[];
  needs_opening_balance: boolean;
  opening_balance_hint: { amount_display: string; date_display: string } | null;
}

export interface SheetMapping {
  source_id: number;
  sheet: string;
  kind: string;
  columns: Record<string, string>;
}

export interface ConfirmBody {
  mappings: SheetMapping[];
  opening_balance: { amount: string; date: string } | null;
  auto_sync: boolean;
}

/** SSE events of `POST /api/sources/confirm` and `POST /api/sources/sync`. */
export interface SourcesStreamEvents {
  progress: { text?: string; pct?: number } | null;
  done: { text?: string; redirect?: string } | null;
  error: { message?: string } | null;
}

export interface SourceFileRow {
  source_id: number;
  label: string;
  kind_label: string;
  rows: string;
  state: string;
  state_tone: "new" | "same" | "error";
}

export interface SourceIssue {
  id: number;
  message: string;
  action: "set_amount" | "use_suggestion" | "ignore";
  action_label: string;
}

export interface SyncLogEntry {
  when: string;
  text: string;
  /** Colour hint: green when rows changed, red on error. */
  tone?: "success" | "info" | "muted" | "error";
}

export interface SourcesPage {
  connected: boolean;
  email: string | null;
  needs_reauth: boolean;
  status: { ok: boolean; title: string; subtitle: string } | null;
  files: SourceFileRow[];
  issues: SourceIssue[];
  log: SyncLogEntry[];
}

/** Error bodies: `{"error": "no_access" | "reauth_required" | …, "message": "…"}`. */
export interface SourcesErrorBody {
  error?: string;
  message?: string;
}
