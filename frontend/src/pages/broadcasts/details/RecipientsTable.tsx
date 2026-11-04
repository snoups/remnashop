import type { ParseKeys } from "i18next";
import { Ban, CircleAlert, CircleCheck, CircleX, Clock, Filter, Mail, Send, Undo2, Users } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { DEFAULT_PAGE_SIZE, listBroadcastRecipients } from "@entities/broadcasts/api";
import type { Broadcast, BroadcastChannel, BroadcastRecipient, BroadcastRecipientStatus } from "@entities/broadcasts/api";
import { processedCount, RECIPIENT_STATUS_TONE } from "@entities/broadcasts/display";
import { formatDateTime } from "@shared/lib/relative-time";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { Badge } from "@shared/ui/Badge";
import { GLASS_LIST_HEAD_CLASS, GLASS_LIST_ROW_CLASS, LIST_BODY_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Section } from "@shared/ui/glass/Section";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { PillTabs } from "@shared/ui/PillTabs";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";

const ROW_GRID_CLASS = "grid grid-cols-[minmax(0,1.6fr)_minmax(0,0.5fr)_minmax(0,1fr)_minmax(0,1.6fr)_minmax(0,0.9fr)] items-center gap-3";
const CHANNELS: BroadcastChannel[] = ["TELEGRAM", "EMAIL"];
// the backend stores these as fixed English markers (broadcasts/repository.py)
const REASON_KEYS: Record<string, ParseKeys> = {
  stopped: "broadcasts.details.stopped",
  "no telegram": "broadcasts.details.reasons.noTelegram",
  "opted out": "broadcasts.details.reasons.optedOut",
  blocked: "broadcasts.details.reasons.blocked",
};
const RECALL_FAILED_PREFIX = "recall failed: ";

type TabKey = "all" | BroadcastRecipientStatus;

const TAB_ICON: Record<TabKey, LucideIcon> = {
  all: Users,
  SENT: CircleCheck,
  FAILED: CircleAlert,
  BLOCKED: Ban,
  PENDING: Clock,
  RECALLED: Undo2,
  CANCELED: CircleX,
};

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
  const isMultiChannel = broadcast.delivery === "ALL" || (broadcast.delivery === "TELEGRAM" && broadcast.email_fallback);
  // finished (completed or stopped): nothing is queued, the unsent rows are canceled, e.g. a customer
  // blocked in the panel mid-send; the canceled filter shows only when there are some
  const finished = stopped || broadcast.status === "COMPLETED";
  const unsent = Math.max(broadcast.total_count - processedCount(broadcast), 0);
  const visibleTabs = TABS.filter((entry) =>
    entry.key === "PENDING" ? !finished : entry.key === "CANCELED" ? finished && unsent > 0 : true,
  );
  const tab = visibleTabs.some((entry) => entry.key === selectedTab) ? selectedTab : "all";
  const status = TABS.find((entry) => entry.key === tab)?.status;
  const [channel, setChannel] = useState<BroadcastChannel | undefined>(undefined);
  const filters = useMemo(() => ({ status, channel }), [status, channel]);
  const { state, isLoadingMore, hasMore, loadMore, reload } = usePaginatedList(
    (current, page, signal) =>
      listBroadcastRecipients(broadcast.id, { status: current.status, channel: current.channel, page, pageSize: DEFAULT_PAGE_SIZE }, signal),
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
    if (r.error) {
      const key = REASON_KEYS[r.error];
      if (key) return t(key);
      if (r.error.startsWith(RECALL_FAILED_PREFIX)) {
        return t("broadcasts.details.reasons.recallFailed", { reason: r.error.slice(RECALL_FAILED_PREFIX.length) });
      }
      return r.error;
    }
    if (r.status !== "SENT") return t("common.none");
    return t(r.channel === "EMAIL" ? "broadcasts.details.sentEmail" : "broadcasts.details.sentTelegram");
  };

  // the broadcast's counters span every channel; with a channel picked only the open tab's total is known
  const countOf = (key: TabKey): number | undefined => {
    if (channel === undefined) return tabCount(broadcast, key);
    return key === tab && state.kind === "ready" ? state.total : undefined;
  };

  return (
    // a settings card: icon, title and description, the status dropdown and channel switch on its right
    <Section
      icon={Users}
      title={t("broadcasts.details.recipients")}
      description={t("broadcasts.details.recipientsHint")}
      className="min-w-0"
      aside={
          <div className="flex flex-wrap items-center gap-2">
          {/* the status as a dropdown, its count in each option, beside the channel switch */}
          <div className="w-52">
            <SelectDropdown
              value={tab}
              onChange={(key) => setTab(key as TabKey)}
              icon={Filter}
              size="compact"
              glassPopover
              placeholder={t("broadcasts.details.tabs.all")}
              options={visibleTabs.map(({ key }) => {
                const count = countOf(key);
                const label = t(`broadcasts.details.tabs.${key}` as ParseKeys);
                return {
                  value: key,
                  label: count !== undefined ? `${label} · ${count.toLocaleString(i18n.language)}` : label,
                  icon: TAB_ICON[key],
                };
              })}
            />
          </div>
          {isMultiChannel && (
            // PillTabs fills its box: w-fit keeps it to its tabs, as the editor's locale tabs
            <div className="w-fit max-w-full">
            <PillTabs
              items={[
                { key: "all", label: t("broadcasts.recipients.channelAll") },
                ...CHANNELS.map((value) => ({ key: value, label: t(`broadcasts.channel.${value}`) })),
              ]}
              activeKey={channel ?? "all"}
              onSelect={(key) => setChannel(key === "all" ? undefined : (key as BroadcastChannel))}
            />
            </div>
          )}
          </div>
      }
    >
      <div className="mt-4">
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
      {state.kind === "ready" && state.items.length === 0 && (
        <EmptyState text={t("broadcasts.details.noRecipients")} size="page" />
      )}
      {state.kind === "ready" && state.items.length > 0 && (
        <div className="overflow-x-auto">
          <div className="min-w-[680px]">
            <div className={`${ROW_GRID_CLASS} ${GLASS_LIST_HEAD_CLASS}`}>
              <span>{t("broadcasts.details.columns.customer")}</span>
              <span>{t("broadcasts.recipients.channel")}</span>
              <span>{t("broadcasts.details.columns.status")}</span>
              <span>{t("broadcasts.details.columns.details")}</span>
              <span>{t("broadcasts.details.columns.time")}</span>
            </div>
            <div className={LIST_BODY_CLASS}>
              {state.items.map((r) => (
                <div key={r.id} className={`${ROW_GRID_CLASS} ${GLASS_LIST_ROW_CLASS}`}>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-[13px] font-medium text-foreground">{r.user_name}</span>
                    <span className="truncate text-[12px] text-muted-foreground">
                      {r.channel === "EMAIL"
                        ? (r.email ?? t("common.none"))
                        : r.username
                          ? `@${r.username}`
                          : t("broadcasts.details.idLabel", { id: r.telegram_id ?? r.user_id })}{" "}
                      · {r.language.toUpperCase()}
                    </span>
                  </span>
                  <span className="text-muted-foreground">
                    {r.channel === "EMAIL" ? <Mail className="size-4" /> : <Send className="size-4" />}
                  </span>
                  <span>
                    <Badge borderless tone={RECIPIENT_STATUS_TONE[r.status]}>{t(`broadcasts.recipientStatus.${r.status}`)}</Badge>
                  </span>
                  <span className="truncate text-[12px] text-muted-foreground">{details(r)}</span>
                  <span className="text-[13px] tabular-nums text-foreground">
                    {r.sent_at ? formatDateTime(r.sent_at, i18n.language) : t("common.none")}
                  </span>
                </div>
              ))}
            </div>
            {hasMore && (
              <div className="mx-3 mt-4">
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
      </div>
    </Section>
  );
}
