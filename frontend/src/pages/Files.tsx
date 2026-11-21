import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileSpreadsheet, Paperclip, Send, Trash2 } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { Markdown } from "@/components/Markdown";
import { BTN_PRIMARY, BTN_SECONDARY } from "@/components/sources/shared";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";

interface FileRow {
  id: string;
  filename: string;
  sheets: number;
  chip: string;
}
interface TableRow {
  table: string;
  sheet: string;
  role_label: string;
  layout: string;
  header: string;
  rows: number;
  ignored: boolean;
  hidden: boolean;
  from: string | null;
  to: string | null;
  columns: string[];
}
interface FileDetail extends FileRow {
  tables: TableRow[];
  notes: string[];
  template: string;
}
interface Msg {
  role: "user" | "model";
  text: string;
  chips?: string[];
  pending?: boolean;
}

function csrf(): string {
  const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return m?.[1] ? decodeURIComponent(m[1]) : "";
}

export async function uploadFile(file: File): Promise<FileDetail> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/files", {
    method: "POST",
    credentials: "same-origin",
    headers: { "X-CSRFToken": csrf() },
    body: fd,
  });
  const data = (await res.json().catch(() => null)) as { file?: FileDetail; message?: string } | null;
  if (!res.ok || !data?.file) throw new Error(data?.message || "Yuklab bo'lmadi");
  return data.file;
}

const CARD = "rounded-card border border-border bg-surface px-5 py-4";
const KEY = (id: string) => `files-chat-${id}`;

function loadMsgs(id: string): Msg[] {
  try {
    const raw = sessionStorage.getItem(KEY(id));
    return raw ? (JSON.parse(raw) as Msg[]) : [];
  } catch {
    return [];
  }
}

function Catalog({ file }: { file: FileDetail }) {
  const [open, setOpen] = useState(false);
  return (
    <section className={CARD}>
      <button type="button" className="flex w-full items-center justify-between text-left" onClick={() => setOpen(!open)}>
        <span className="font-semibold">
          Katalog: {file.tables.length} jadval · {file.sheets} varaq{file.template ? ` · ${file.template}` : ""}
        </span>
        <span className="text-13 text-text-3">{open ? "Yopish" : "Ko'rish"}</span>
      </button>
      {open && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-13">
            <thead>
              <tr className="text-left text-text-3">
                <th className="py-1 pr-3">Varaq</th>
                <th className="py-1 pr-3">Roli</th>
                <th className="py-1 pr-3">Tuzilishi</th>
                <th className="py-1 pr-3">Sarlavha</th>
                <th className="py-1 pr-3 text-right">Qator</th>
                <th className="py-1">Sanalar</th>
              </tr>
            </thead>
            <tbody>
              {file.tables.map((t) => (
                <tr key={t.table} className={cn("border-t border-border", t.ignored && "text-text-4")} title={t.columns.join(", ")}>
                  <td className="py-1 pr-3">{t.table === t.sheet ? t.sheet : `${t.sheet} (${t.table})`}{t.hidden ? " · yashirin" : ""}</td>
                  <td className="py-1 pr-3">{t.role_label}</td>
                  <td className="py-1 pr-3">{t.layout}</td>
                  <td className="py-1 pr-3">{t.header}</td>
                  <td className="py-1 pr-3 text-right tabular-nums">{t.rows.toLocaleString("ru-RU")}</td>
                  <td className="py-1">{t.from ? `${t.from} – ${t.to}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {file.notes.length > 0 && <p className="mt-2 text-13 text-text-3">Izohlar: {file.notes.join("; ")}</p>}
        </div>
      )}
    </section>
  );
}

function FileChat({ file }: { file: FileDetail }) {
  const [msgs, setMsgs] = useState<Msg[]>(() => loadMsgs(file.id));
  const [text, setText] = useState("");
  const busy = msgs.some((m) => m.pending);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      sessionStorage.setItem(KEY(file.id), JSON.stringify(msgs.filter((m) => !m.pending)));
    } catch {
      /* ignore */
    }
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [msgs, file.id]);

  async function ask(q: string) {
    const history = msgs.filter((m) => !m.pending).map((m) => ({ role: m.role, text: m.text }));
    setMsgs((m) => [...m, ...(q === "__summary__" ? [] : [{ role: "user" as const, text: q }]), { role: "model", text: "", pending: true }]);
    try {
      const r = await apiPost<{ markdown: string; chips: string[] }>(`/api/files/${file.id}/ask`, { question: q, history });
      setMsgs((m) => [...m.filter((x) => !x.pending), { role: "model", text: r.markdown, chips: r.chips }]);
    } catch (e) {
      const msg = e instanceof ApiError ? "Xato yuz berdi, qayta urinib ko'ring." : "Tarmoq xatosi.";
      setMsgs((m) => [...m.filter((x) => !x.pending), { role: "model", text: msg }]);
    }
  }

  useEffect(() => {
    // first open: the automatic "Fayl xulosasi"
    // eslint-disable-next-line react-hooks/set-state-in-effect, react-hooks/exhaustive-deps
    if (msgs.length === 0) void ask("__summary__");
  }, [file.id]);

  function submit(e: FormEvent) {
    e.preventDefault();
    const q = text.trim();
    if (!q || busy) return;
    setText("");
    void ask(q);
  }

  const last = msgs[msgs.length - 1];
  return (
    <section className="flex flex-col gap-3">
      {msgs.map((m, i) =>
        m.role === "user" ? (
          <div key={i} className="self-end rounded-card bg-ink px-4 py-2.5 text-white">{m.text}</div>
        ) : (
          <div key={i} className={CARD}>
            {i === 0 && <div className="mb-2 text-12 font-bold uppercase tracking-label text-text-3">Fayl xulosasi</div>}
            {m.pending ? (
              <div className="animate-pulse text-text-3">Fayl to&apos;liq tahlil qilinmoqda… (20–60 soniya)</div>
            ) : (
              <Markdown text={m.text} />
            )}
          </div>
        ),
      )}
      {last?.chips && last.chips.length > 0 && !busy && (
        <div className="flex flex-wrap gap-2">
          {last.chips.map((c) => (
            <button key={c} type="button" className={BTN_SECONDARY} onClick={() => void ask(c)}>
              {c}
            </button>
          ))}
        </div>
      )}
      <form onSubmit={submit} className="sticky bottom-3 flex gap-2 rounded-card border border-border bg-surface p-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Fayl haqida istalgan savol: «Oktyabrda qancha foyda qildik?»"
          className="min-w-0 flex-1 bg-transparent px-2 outline-none"
          disabled={busy}
        />
        <button type="submit" className={BTN_PRIMARY} disabled={busy || !text.trim()} aria-label="Yuborish">
          <Send size={18} />
        </button>
      </form>
      <div ref={end} />
    </section>
  );
}

export default function FilesPage() {
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const current = params.get("id");
  const input = useRef<HTMLInputElement>(null);
  const list = useQuery({ queryKey: ["files"], queryFn: () => apiGet<{ files: FileRow[] }>("/api/files") });
  const detail = useQuery({
    queryKey: ["file", current],
    queryFn: () => apiGet<{ file: FileDetail }>(`/api/files/${current}`),
    enabled: !!current,
  });
  const upload = useMutation({
    mutationFn: uploadFile,
    onSuccess: (f) => {
      void qc.invalidateQueries({ queryKey: ["files"] });
      setParams({ id: f.id });
    },
  });
  const del = useMutation({
    mutationFn: async (id: string) => {
      await fetch(`/api/files/${id}`, { method: "DELETE", credentials: "same-origin", headers: { "X-CSRFToken": csrf() } });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["files"] });
      setParams({});
    },
  });

  return (
    <AppShell active="files">
      <div className="mx-auto flex w-full max-w-[960px] flex-col gap-4 px-4 py-6">
        <header>
          <h1 className="m-0 font-display text-[26px] font-bold">Fayl tahlili</h1>
          <p className="m-0 text-text-3">
            Istalgan Excel (.xlsx, .xls, .csv, 20 MB gacha) yuklang — AI barcha varaqlarni to&apos;liq o&apos;qib, istalgan
            savolga aniq javob beradi. Asosiy ma&apos;lumotlaringiz o&apos;zgarmaydi.
          </p>
        </header>
        <div
          className={cn(CARD, "flex cursor-pointer flex-col items-center gap-2 border-dashed py-8 text-center")}
          onClick={() => input.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            const f = e.dataTransfer.files[0];
            if (f) upload.mutate(f);
          }}
        >
          <Paperclip size={22} />
          <span className="font-semibold">{upload.isPending ? "Yuklanmoqda va o'qilmoqda…" : "Faylni shu yerga tashlang yoki bosing"}</span>
          {upload.isError && <span className="text-13 text-[#B42318]">{(upload.error as Error).message}</span>}
          <input
            ref={input}
            type="file"
            accept=".xlsx,.xlsm,.xls,.csv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) upload.mutate(f);
              e.target.value = "";
            }}
          />
        </div>
        {(list.data?.files.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-2">
            {list.data?.files.map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setParams({ id: f.id })}
                className={cn("flex items-center gap-2 rounded-full border px-3 py-1.5 text-13", f.id === current ? "border-ink bg-ink text-white" : "border-border bg-surface")}
              >
                <FileSpreadsheet size={15} /> {f.chip}
              </button>
            ))}
          </div>
        )}
        {detail.data?.file && (
          <>
            <div className="flex items-center justify-between gap-2">
              <span className="rounded-full bg-[#EEF4FF] px-3 py-1 text-13 font-semibold">{detail.data.file.chip}</span>
              <button type="button" className={BTN_SECONDARY} onClick={() => del.mutate(detail.data.file.id)}>
                <Trash2 size={15} /> O&apos;chirish
              </button>
            </div>
            <Catalog file={detail.data.file} />
            <FileChat key={detail.data.file.id} file={detail.data.file} />
          </>
        )}
      </div>
    </AppShell>
  );
}
