import type { ParseKeys } from "i18next";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { DEFAULT_PAGE_SIZE, listBroadcastRecipients } from "@entities/broadcasts/api";
import type { Broadcast, BroadcastRecipient, BroadcastRecipientStatus } from "@entities/broadcasts/api";
import { processedCount, RECIPIENT_STATUS_TONE } from "@entities/broadcasts/display";
import { formatDateTime } from "@shared/lib/relative-time";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { Spinner } from "@shared/ui/Spinner";

const ROW_GRID_CLASS = "grid grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)_minmax(0,1.6fr)_minmax(0,0.9fr)] items-center gap-3";
const STOPPED_ERROR = "stopped";

type TabKey = "all" | BroadcastRecipientStatus;

const TABS: { key: TabKey; status: BroadcastRecipientStatus | undefined }[] = [
  { key: "all", status: undefined },
  { key: "SENT", status: "SENT" },
  { key: "FAILED", status: "FAILED" },
  { key: "BLOCKED", status: "BLOCKED" },
  { key: "PENDING", status: "PENDING" },
  { key: "RECALLED", status: "RECALLED" },
  { key: "CANCELED", status: "CANCELED" },
];

// a stopped broadcast's unsent rows are CANCELED, not queued
function isStopped(b: Broadcast): boolean {
  return b.status === "CANCELED" || b.status === "FAILED";
}

function tabCount(b: Broadcast, key: TabKey): number {
  switch (key) {
    case "all":
      return b.total_count;
    case "SENT":
      return b.sent_count;
    case "FAILED":
      return b.failed_count;
    case "BLOCKED":
      return b.blocked_count;
    case "RECALLED":
      return b.recalled_count;
    case "CANCELED":
      return Math.max(b.total_count - processedCount(b), 0);
    default:
      return Math.max(b.total_count - processedCount(b), 0);
  }
}

interface RecipientsTableProps {
  broadcast: Broadcast;
  /** bumped by the page's poll; refetches the current tab's first page */
  refreshKey: number;
}

export function RecipientsTable({ broadcast, refreshKey }: RecipientsTableProps) {
  const { t, i18n } = useTranslation();
  const [selectedTab, setTab] = useState<TabKey>("all");
  const stopped = isStopped(broadcast);
  const visibleTabs = TABS.filter((entry) => stopped || entry.key !== "CANCELED");
  const tab = visibleTabs.some((entry) => entry.key === selectedTab) ? selectedTab : "all";
  const status = TABS.find((entry) => entry.key === tab)?.status;
  const filters = useMemo(() => ({ status }), [status]);
  const { state, isLoadingMore, hasMore, loadMore, reload } = usePaginatedList(
    (current, page, signal) =>
      listBroadcastRecipients(broadcast.id, { status: current.status, page, pageSize: DEFAULT_PAGE_SIZE }, signal),
    filters,
  );

  // a refetch drops the pages loaded past the first, so a poll only refreshes while there are none;
  // a status change refreshes regardless
  const loadedCount = state.kind === "ready" ? state.items.length : 0;
  const loadedCountRef = useRef(loadedCount);
  loadedCountRef.current = loadedCount;
  const statusRef = useRef(broadcast.status);
  useEffect(() => {
    const statusChanged = statusRef.current !== broadcast.status;
    statusRef.current = broadcast.status;
    if (refreshKey > 0 && (statusChanged || loadedCountRef.current <= DEFAULT_PAGE_SIZE)) reload();
  }, [refreshKey, broadcast.status, reload]);

  const details = (r: BroadcastRecipient): string => {
    if (r.error) return r.error === STOPPED_ERROR ? t("broadcasts.details.stopped") : r.error;
    return r.status === "SENT" ? t("broadcasts.details.messageSent") : t("common.none");
  };

  return (
    <Card variant="list" className="min-w-0">
      <div className="flex flex-wrap items-center gap-1.5 px-2 pb-2.5 pt-2">
        <span className={`mr-1.5 ${EYEBROW_CLASS}`}>{t("broadcasts.details.recipients")}</span>
        {visibleTabs.map(({ key }) => (
          <ChoiceChip key={key} size="md" active={tab === key} onClick={() => setTab(key)}>
            {t(`broadcasts.details.tabs.${key}` as ParseKeys)}
            {!(stopped && key === "PENDING") && (
              <span className="text-[11px] tabular-nums opacity-70">
                {tabCount(broadcast, key).toLocaleString(i18n.language)}
              </span>
            )}
          </ChoiceChip>
        ))}
      </div>
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("broadcasts.details.recipientsError")} size="page" />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState text={t("broadcasts.details.noRecipients")} size="page" />
      )}
      {state.kind === "ready" && state.items.length > 0 && (
        <div className="overflow-x-auto">
          <div className="min-w-[620px]">
            <div className={`${ROW_GRID_CLASS} ${LIST_HEAD_CLASS}`}>
              <span>{t("broadcasts.details.columns.customer")}</span>
              <span>{t("broadcasts.details.columns.status")}</span>
              <span>{t("broadcasts.details.columns.details")}</span>
              <span>{t("broadcasts.details.columns.time")}</span>
            </div>
            <div className={LIST_BODY_CLASS}>
              {state.items.map((r) => (
                <div key={r.id} className={`${ROW_GRID_CLASS} px-3 py-2.5`}>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-[13px] font-semibold text-foreground">{r.user_name}</span>
                    <span className="truncate text-[12px] text-muted-foreground">
                      {r.username ? `@${r.username}` : t("broadcasts.details.idLabel", { id: r.telegram_id ?? r.user_id })} ·{" "}
                      {r.language.toUpperCase()}
                    </span>
                  </span>
                  <span>
                    <Badge tone={RECIPIENT_STATUS_TONE[r.status]}>{t(`broadcasts.recipientStatus.${r.status}`)}</Badge>
                  </span>
                  <span className="truncate text-[12.5px] text-muted-foreground">{details(r)}</span>
                  <span className="text-[12.5px] tabular-nums text-foreground/80">
                    {r.sent_at ? formatDateTime(r.sent_at, i18n.language) : t("common.none")}
                  </span>
                </div>
              ))}
            </div>
            {hasMore && (
              <div className="mx-3 my-3">
                <LoadMoreButton
                  onClick={() => void loadMore()}
                  isLoading={isLoadingMore}
                  shown={state.items.length}
                  total={state.total}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
