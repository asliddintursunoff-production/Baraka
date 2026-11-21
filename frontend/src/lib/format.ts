/** Chart helpers only. Money strings from the API are converted to numbers just to
 * position marks on a chart; every amount in prose comes formatted from the backend.
 * Axis ticks, chart tooltips and chart tables are formatted here (Uzbek, B2). */

export const toMln = (v: string): number => Number(v) / 1_000_000;

/** Thousands separator (same as the backend's `uz_format.NBSP`). */
export const NBSP = "\u00A0";
const MINUS = "\u2212";

export const MONTHS_SHORT_UZ = [
  "Yan",
  "Fev",
  "Mar",
  "Apr",
  "May",
  "Iyun",
  "Iyul",
  "Avg",
  "Sen",
  "Okt",
  "Noy",
  "Dek",
] as const;
export const MONTHS_UZ = [
  "yanvar",
  "fevral",
  "mart",
  "aprel",
  "may",
  "iyun",
  "iyul",
  "avgust",
  "sentyabr",
  "oktyabr",
  "noyabr",
  "dekabr",
] as const;
/** Monday first. */
export const WEEKDAYS_UZ = [
  "dushanba",
  "seshanba",
  "chorshanba",
  "payshanba",
  "juma",
  "shanba",
  "yakshanba",
] as const;

export type DateStyleUz = "tickMonth" | "tickDay" | "long" | "full";

interface DateParts {
  y: number;
  m: number; // 0-11
  d: number;
  wd: number; // 0 = dushanba
}

function dateParts(date: string | Date): DateParts {
  if (typeof date === "string") {
    const [y = 1970, m = 1, d = 1] = date.slice(0, 10).split("-").map(Number);
    const utc = new Date(Date.UTC(y, m - 1, d));
    return { y, m: m - 1, d, wd: (utc.getUTCDay() + 6) % 7 };
  }
  return {
    y: date.getFullYear(),
    m: date.getMonth(),
    d: date.getDate(),
    wd: (date.getDay() + 6) % 7,
  };
}

/**
 * Uzbek date text. "tickMonth" → "Noy 2026"; "tickDay" → "1-dek 2026"; "full" → "10-yanvar 2027";
 * "long" → "10-yanvar 2027, shanba". `year: false` drops the year from the tick styles.
 * ISO strings ("2026-11-21") are read as calendar dates (no timezone shift).
 */
export function formatDateUz(
  date: string | Date,
  style: DateStyleUz,
  opts: { year?: boolean } = {},
): string {
  const { y, m, d, wd } = dateParts(date);
  const year = opts.year ?? true;
  const short = MONTHS_SHORT_UZ[m] ?? "";
  switch (style) {
    case "tickMonth":
      return year ? `${short} ${y}` : short;
    case "tickDay":
      return year ? `${d}-${short.toLowerCase()} ${y}` : `${d}-${short.toLowerCase()}`;
    case "full":
      return `${d}-${MONTHS_UZ[m]} ${y}`;
    case "long":
      return `${d}-${MONTHS_UZ[m]} ${y}, ${WEEKDAYS_UZ[wd]}`;
  }
}

/** Axis tick labels: the year is shown on the first tick and whenever it changes. */
export function axisDateLabels(dates: string[], style: "tickMonth" | "tickDay"): string[] {
  let prev: number | null = null;
  return dates.map((iso) => {
    const y = Number(iso.slice(0, 4));
    const show = prev === null || y !== prev;
    prev = y;
    return formatDateUz(iso, style, { year: show });
  });
}

function groupDigits(n: number): string {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

/** One-decimal million amount with grouped thousands: 1439.5 → "1 439,5", 2000 → "2 000". */
function mlnNumber(mln: number, keepZeroDecimal: boolean): string {
  const tenths = Math.round(Math.abs(mln) * 10);
  const int = Math.floor(tenths / 10);
  const frac = tenths % 10;
  const sign = tenths > 0 && mln < 0 ? MINUS : "";
  const dec = frac || keepZeroDecimal ? `,${frac}` : "";
  return `${sign}${groupDigits(int)}${dec}`;
}

/** Y-axis tick: "0", "500 mln", "2 000 mln", "1 437,5 mln" (never "2000 mln"). */
export function formatMlnAxis(mln: number): string {
  if (Math.round(Math.abs(mln) * 10) === 0) return "0";
  return `${mlnNumber(mln, false)} mln`;
}

/** Tooltip / table amount, like the backend's `format_mln`: "1 439,5 mln", "−6,2 mln". */
export function formatMln(mln: number): string {
  return `${mlnNumber(mln, true)} mln`;
}

/** Groups 4+ digit numbers in backend chart labels ("Xavfsiz chegara · 1000 mln" → "1 000 mln"). */
export function groupMlnText(text: string): string {
  return text.replace(/\d{4,}/g, (digits) => groupDigits(Number(digits)));
}
