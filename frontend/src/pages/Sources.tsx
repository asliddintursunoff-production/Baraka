import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { BTN_PRIMARY, invalidateFinance } from "@/components/sources/shared";
import {
  connectHref,
  DisconnectGoogle,
  FilesTable,
  IssuesList,
  ReauthBanner,
  SourcesEmpty,
  SyncLog,
  SyncStatusCard,
} from "@/components/sources/SourcesParts";
import { ErrorState, PageSkeleton } from "@/components/States";
import { apiGet } from "@/lib/api";
import type { SourcesPage } from "@/lib/sourcesTypes";

function normalize(d: Partial<SourcesPage>): SourcesPage {
  return {
    connected: Boolean(d.connected),
    email: d.email ?? null,
    needs_reauth: Boolean(d.needs_reauth),
    status: d.status ?? null,
    files: d.files ?? [],
    issues: d.issues ?? [],
    log: d.log ?? [],
  };
}

export default function SourcesPageView() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["sources"], queryFn: () => apiGet<SourcesPage>("/api/sources") });

  if (q.isPending)
    return (
      <AppShell active="sources">
        <PageSkeleton />
      </AppShell>
    );
  if (q.isError)
    return (
      <AppShell active="sources">
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      </AppShell>
    );

  const d = normalize(q.data);
  const empty = d.files.length === 0;
  const onSynced = async () => {
    invalidateFinance(qc);
    await q.refetch();
  };

  return (
    <AppShell active="sources">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-[6px]">
          <h1 className="m-0 font-display text-30 font-bold">Ma'lumotlar</h1>
          <span className="text-16 text-text-3">
            Google Sheets'dan avtomatik keladi. Siz faqat jadvalingizni odatdagidek to'ldirib
            borasiz.
          </span>
        </div>
        {!empty && (
          <Link to={connectHref(d.connected)} className={BTN_PRIMARY}>
            + Yangi fayl ulash
          </Link>
        )}
      </header>

      {d.connected && d.needs_reauth && <ReauthBanner />}

      {empty ? (
        <SourcesEmpty connected={d.connected} />
      ) : (
        <>
          <SyncStatusCard data={d} onSynced={onSynced} />
          <div className="flex flex-wrap items-start gap-5">
            <FilesTable files={d.files} />
            {(d.issues.length > 0 || d.log.length > 0) && (
              <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-5">
                <IssuesList issues={d.issues} />
                <SyncLog log={d.log} />
              </div>
            )}
          </div>
        </>
      )}

      {d.connected && <DisconnectGoogle email={d.email} />}
    </AppShell>
  );
}
