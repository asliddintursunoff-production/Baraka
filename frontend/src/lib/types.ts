/** Payloads of the page APIs. All numbers/dates arrive formatted from the backend. */

export type Verdict = "yes" | "risky" | "no";
export type Severity = "success" | "warning" | "danger";

export type OnboardingStep = "business" | "connect" | "review" | "analyzing" | "done";
export type DataStatus = "no_data" | "needs_review" | "short_history" | "ok";

export interface Me {
  user: { email: string; first_name: string; last_name: string };
  business: { id: number; name: string; city: string; is_demo?: boolean } | null;
  businesses: { id: number; name: string; city: string; role: string; is_demo?: boolean }[];
  onboarding_step?: OnboardingStep;
  data_status?: DataStatus;
  history_days?: number;
  freshness?: { as_of?: string; stale?: boolean; missing_days?: number; text?: string; banner?: string } | null;
}

export interface SeriesPoint {
  i: number;
  date: string;
  label: string;
  close: string;
  p10: string;
  p90: string;
  display: string;
}

export interface HorizonSummary {
  days: number;
  verdict: Verdict | null;
  chip: string;
  lowest_index: number;
  lowest_date: string;
  lowest_display: string;
  lowest_date_label: string;
  text: string;
  callout_title: string;
  callout_text: string;
  title: string;
}

/** Actual cash history for the left chart panel (docs/API_CHARTS_ANSWERS.md). */
export interface ForecastHistory {
  title: string;
  points: { date: string; close: string }[];
  weekly: { week: string; in: string; out: string }[];
  markers: { date: string; label: string; amount: string }[];
  last_actual: string;
  caption: string;
}

export interface ForecastGap {
  from: string;
  to: string;
  label: string;
}

export interface HardestDay {
  date: string;
  label: string;
  balance: string;
  payments: { title: string; amount: string }[];
}

export interface ForecastBlock {
  series: SeriesPoint[];
  safe_min: string;
  safe_label: string;
  summaries: Record<string, HorizonSummary>;
  default_horizon: number;
  insufficient_data: boolean;
  /** Part B fields; optional so older payloads still render. */
  history?: ForecastHistory | null;
  title?: string;
  start?: string;
  today?: string;
  gap?: ForecastGap | null;
  hardest?: HardestDay | null;
  caption?: string;
  beyond?: string;
}

export interface Step {
  severity: Severity;
  label: string;
  text: string;
}

export interface Kpi {
  id: string;
  label: string;
  value: string;
  unit: string;
  note: string;
  tone: "muted" | "success" | "warning" | "danger";
}

export interface Dashboard {
  freshness?: { as_of: string; missing_from?: string; missing_to?: string; text: string } | null;
  user: { first_name: string };
  business: { id: number; name: string; city: string };
  today: { iso: string; label: string };
  sync: { connected: boolean; ok: boolean; label: string };
  alerts: { new: number };
  banner: { label: string; headline: string; reason: string; instruction: string; beyond?: string };
  kpis: Kpi[];
  forecast: ForecastBlock;
  steps: Step[];
  news: { kind: "learned" | "segment"; label: string; text: string }[];
  upcoming: {
    rows: {
      date_label: string;
      title: string;
      priority: "critical" | "deferrable" | "discretionary";
      priority_label: string;
      amount_display: string;
    }[];
    total_display: string;
  };
  monthly: {
    label: string;
    inflow: string;
    outflow: string;
    inflow_display: string;
    outflow_display: string;
    profit_label: string;
  }[];
  has_cash: boolean;
}

export interface ScenarioCard {
  verdict: Verdict;
  tone: Severity;
  title: string;
  body: { before: string; strong: string; after: string };
  tip: string;
  marker_index: number;
}

export interface ScenarioResult {
  card: ScenarioCard | null;
  overlay?: string[];
  marker_index?: number;
  needs?: string;
  error?: string;
  message?: string;
}

export interface ForecastPage {
  forecast: ForecastBlock;
  key_days: {
    i: number;
    date: string;
    label: string;
    title: string;
    balance: string;
    status: "ok" | "warn" | "danger";
    hardest: boolean;
  }[];
  presets: ({ id: string; label: string } & ScenarioResult)[];
  free_text_placeholder: string;
}

export interface CalendarDay {
  n: number;
  date: string;
  kind: "hot" | "pay" | "plain" | "out";
  items: { label: string; critical: boolean }[];
  bal: string | null;
  title: string;
  detail?:
    | {
        full: true;
        chip: string;
        status: "ok" | "warn" | "danger";
        rows: { label: string; value: string; tone: "plain" | "success" | "danger"; badge?: string }[];
        closing: string;
        advice: string;
        reminder: { date: string; label: string } | null;
      }
    | { full: false; text: string; closing: string };
}

export interface CalendarPage {
  month: string;
  title: string;
  prev: string;
  next: string;
  lead: number;
  weekdays: string[];
  days: CalendarDay[];
  selected: string;
}
