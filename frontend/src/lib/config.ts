export interface Pricing {
  trial: {
    price_uzs: number | null;
    days: number | null;
    sheets: number | null;
    chat_per_day: number | null;
    voice_minutes: number | null;
  };
  business: { price_uzs_month: number | null };
}

export interface AppConfig {
  appName: string;
  pricing: Pricing | null;
}

declare global {
  interface Window {
    __APP_CONFIG__?: Partial<AppConfig>;
  }
}

/** Injected by Django (`window.__APP_CONFIG__`). The product name is never hard-coded. */
export const appConfig: AppConfig = {
  appName: window.__APP_CONFIG__?.appName ?? "",
  pricing: window.__APP_CONFIG__?.pricing ?? null,
};
