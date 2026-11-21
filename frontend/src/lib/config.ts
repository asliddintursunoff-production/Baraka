export interface AppConfig {
  appName: string;
}

declare global {
  interface Window {
    __APP_CONFIG__?: Partial<AppConfig>;
  }
}

/** Injected by Django (`window.__APP_CONFIG__`). The product name is never hard-coded. */
export const appConfig: AppConfig = {
  appName: window.__APP_CONFIG__?.appName ?? "",
};
