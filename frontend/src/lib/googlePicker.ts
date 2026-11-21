/**
 * Google Picker without an npm package: `api.js` is injected once on first use (Connect and
 * Sources pages only), then `gapi.load("picker")`. The browser only ever gets the short-lived
 * access token from `/api/integrations/google/picker-config`.
 */
import type { PickerConfig } from "./sourcesTypes";

const GAPI_SRC = "https://apis.google.com/js/api.js";
const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
export const PICKER_TITLE = "Jadvallaringizni belgilang (papkani emas)";
const LOAD_TIMEOUT_MS = 15_000;

// Minimal declarations for the globals used here.
interface GapiLoadConfig {
  callback: () => void;
  onerror: () => void;
  timeout: number;
  ontimeout: () => void;
}

interface Gapi {
  load(api: "picker", config: GapiLoadConfig): void;
}

interface DocsView {
  setMimeTypes(mimeTypes: string): DocsView;
  setIncludeFolders(include: boolean): DocsView;
  setSelectFolderEnabled(enabled: boolean): DocsView;
}

type PickerResponse = Record<string, unknown>;

interface Picker {
  setVisible(visible: boolean): Picker;
  dispose(): void;
}

interface PickerBuilder {
  addView(view: DocsView): PickerBuilder;
  enableFeature(feature: string): PickerBuilder;
  setOAuthToken(token: string): PickerBuilder;
  setDeveloperKey(key: string): PickerBuilder;
  setAppId(appId: string): PickerBuilder;
  setLocale(locale: string): PickerBuilder;
  setTitle(title: string): PickerBuilder;
  setCallback(callback: (data: PickerResponse) => void): PickerBuilder;
  build(): Picker;
}

interface PickerNamespace {
  PickerBuilder: new () => PickerBuilder;
  DocsView: new (viewId?: string) => DocsView;
  ViewId: { SPREADSHEETS: string; DOCS: string };
  Feature: { MULTISELECT_ENABLED: string };
  Action: { PICKED: string; CANCEL: string };
  Response: { ACTION: string; DOCUMENTS: string };
  Document: { ID: string };
}

declare global {
  interface Window {
    gapi?: Gapi;
    google?: { picker?: PickerNamespace };
  }
}

export class PickerLoadError extends Error {
  constructor(reason: string) {
    super(`Google Picker: ${reason}`);
  }
}

let scriptPromise: Promise<void> | null = null;
let pickerPromise: Promise<PickerNamespace> | null = null;

function loadScript(): Promise<void> {
  if (window.gapi) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise<void>((resolve, reject) => {
      const script = document.createElement("script");
      script.src = GAPI_SRC;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        script.remove();
        scriptPromise = null; // allow a retry
        reject(new PickerLoadError("api.js failed to load"));
      };
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
}

/** Loads `api.js` + the picker module once; a failed load can be retried. */
export function loadPicker(): Promise<PickerNamespace> {
  if (!pickerPromise) {
    pickerPromise = loadScript().then(
      () =>
        new Promise<PickerNamespace>((resolve, reject) => {
          const gapi = window.gapi;
          if (!gapi) {
            reject(new PickerLoadError("gapi missing"));
            return;
          }
          gapi.load("picker", {
            callback: () => {
              const ns = window.google?.picker;
              if (ns) resolve(ns);
              else reject(new PickerLoadError("picker missing"));
            },
            onerror: () => reject(new PickerLoadError("picker failed to load")),
            timeout: LOAD_TIMEOUT_MS,
            ontimeout: () => reject(new PickerLoadError("picker load timed out")),
          });
        }),
    );
    pickerPromise.catch(() => {
      pickerPromise = null;
    });
  }
  return pickerPromise;
}

/** Opens the Picker (Google Sheets + .xlsx, multi-select). Resolves with the picked file ids, or `[]` on cancel. */
export async function openPicker(cfg: PickerConfig): Promise<string[]> {
  const ns = await loadPicker();
  return new Promise<string[]>((resolve) => {
    let picker: Picker | null = null;
    const finish = (ids: string[]) => {
      try {
        picker?.dispose();
      } catch {
        // already gone
      }
      resolve(ids);
    };
    const sheets = new ns.DocsView(ns.ViewId.SPREADSHEETS)
      .setIncludeFolders(true)
      .setSelectFolderEnabled(false);
    const xlsx = new ns.DocsView(ns.ViewId.DOCS)
      .setMimeTypes(XLSX_MIME)
      .setIncludeFolders(true)
      .setSelectFolderEnabled(false);
    picker = new ns.PickerBuilder()
      .addView(sheets)
      .addView(xlsx)
      .enableFeature(ns.Feature.MULTISELECT_ENABLED)
      .setOAuthToken(cfg.access_token)
      .setDeveloperKey(cfg.developer_key)
      .setAppId(cfg.app_id)
      .setLocale("uz")
      .setTitle(PICKER_TITLE)
      .setCallback((data) => {
        const action = data[ns.Response.ACTION];
        if (action === ns.Action.PICKED) {
          const docs = data[ns.Response.DOCUMENTS];
          const ids = Array.isArray(docs)
            ? docs
                .map((d: unknown) =>
                  d && typeof d === "object"
                    ? (d as Record<string, unknown>)[ns.Document.ID]
                    : null,
                )
                .filter((id): id is string => typeof id === "string" && id.length > 0)
            : [];
          finish(ids);
        } else if (action === ns.Action.CANCEL) {
          finish([]);
        }
        // Other actions ("loaded") are informational.
      })
      .build();
    picker.setVisible(true);
  });
}
