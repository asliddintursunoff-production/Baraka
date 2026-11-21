import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

type Callback = (data: Record<string, unknown>) => void;

/** A fake `google.picker` namespace that records what the builder was told. */
function installFakePicker() {
  const calls: Record<string, unknown[]> = {};
  const views: {
    id: string | undefined;
    mime?: string;
    folders?: boolean;
    selectFolder?: boolean;
  }[] = [];
  let callback: Callback | null = null;
  let disposed = 0;
  let visible = false;
  const record = (name: string, value: unknown) => {
    (calls[name] ??= []).push(value);
  };

  class DocsView {
    v: (typeof views)[number];
    constructor(id?: string) {
      this.v = { id };
      views.push(this.v);
    }
    setMimeTypes(m: string) {
      this.v.mime = m;
      return this;
    }
    setIncludeFolders(b: boolean) {
      this.v.folders = b;
      return this;
    }
    setSelectFolderEnabled(b: boolean) {
      this.v.selectFolder = b;
      return this;
    }
  }
  class PickerBuilder {
    addView(v: unknown) {
      record("addView", v);
      return this;
    }
    enableFeature(f: string) {
      record("enableFeature", f);
      return this;
    }
    setOAuthToken(t: string) {
      record("setOAuthToken", t);
      return this;
    }
    setDeveloperKey(k: string) {
      record("setDeveloperKey", k);
      return this;
    }
    setAppId(a: string) {
      record("setAppId", a);
      return this;
    }
    setLocale(l: string) {
      record("setLocale", l);
      return this;
    }
    setTitle(t: string) {
      record("setTitle", t);
      return this;
    }
    setCallback(cb: Callback) {
      callback = cb;
      return this;
    }
    build() {
      return {
        setVisible(v: boolean) {
          visible = v;
          return this;
        },
        dispose() {
          disposed++;
        },
      };
    }
  }
  const picker = {
    PickerBuilder,
    DocsView,
    ViewId: { SPREADSHEETS: "spreadsheets", DOCS: "all" },
    Feature: { MULTISELECT_ENABLED: "multiselectEnabled" },
    Action: { PICKED: "picked", CANCEL: "cancel" },
    Response: { ACTION: "action", DOCUMENTS: "docs" },
    Document: { ID: "id" },
  };
  (globalThis as unknown as { window: unknown }).window = {
    gapi: { load: (_api: string, cfg: { callback: () => void }) => cfg.callback() },
    google: { picker },
  };
  return {
    calls,
    views,
    fire: (data: Record<string, unknown>) => callback?.(data),
    get disposed() {
      return disposed;
    },
    get visible() {
      return visible;
    },
  };
}

const cfg = { access_token: "tok", developer_key: "key", app_id: "123" };
const tick = () => new Promise((r) => setTimeout(r, 0));

// The module caches the loaded picker: import a fresh copy per test.
const load = () => import("@/lib/googlePicker");

describe("openPicker", () => {
  beforeEach(() => {
    vi.resetModules();
  });
  afterEach(() => {
    delete (globalThis as { window?: unknown }).window;
  });

  it("configures Sheets + .xlsx views, multi-select, token, key, app id, locale and title", async () => {
    const fake = installFakePicker();
    const { openPicker, PICKER_TITLE } = await load();
    const result = openPicker(cfg);
    await tick();
    expect(fake.visible).toBe(true);
    expect(fake.views).toEqual([
      { id: "spreadsheets", folders: true, selectFolder: false },
      {
        id: "all",
        mime: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        folders: true,
        selectFolder: false,
      },
    ]);
    expect(fake.calls.enableFeature).toEqual(["multiselectEnabled"]);
    expect(fake.calls.setOAuthToken).toEqual(["tok"]);
    expect(fake.calls.setDeveloperKey).toEqual(["key"]);
    expect(fake.calls.setAppId).toEqual(["123"]);
    expect(fake.calls.setLocale).toEqual(["uz"]);
    expect(fake.calls.setTitle).toEqual([PICKER_TITLE]);

    fake.fire({ action: "loaded" });
    fake.fire({ action: "picked", docs: [{ id: "a" }, { id: "b" }, { name: "no id" }] });
    await expect(result).resolves.toEqual(["a", "b"]);
    expect(fake.disposed).toBe(1);
  });

  it("resolves with [] on cancel", async () => {
    const fake = installFakePicker();
    const { openPicker } = await load();
    const result = openPicker(cfg);
    await tick();
    fake.fire({ action: "cancel" });
    await expect(result).resolves.toEqual([]);
  });
});
