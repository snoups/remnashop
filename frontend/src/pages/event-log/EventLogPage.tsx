import {
  AlertCircle,
  Check,
  ChevronDown,
  Clock,
  Copy,
  Filter,
  Globe,
  History,
  Inbox,
  Loader2,
  Search,
  Tag,
  User,
  X,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  DEFAULT_PAGE_SIZE,
  type EventLogEntry,
  type EventLogFilters,
  listEventLog,
} from "@entities/event-log/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { InfoRow } from "@shared/ui/InfoRow";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: EventLogEntry[]; total: number };

const CATEGORIES = ["AUTH", "ADMIN_MANAGEMENT", "USER", "SETTINGS"] as const;
const CATEGORY_LABEL_KEYS: Record<(typeof CATEGORIES)[number], string> = {
  AUTH: "eventLog.filters.categoryAuth",
  ADMIN_MANAGEMENT: "eventLog.filters.categoryAdminManagement",
  USER: "eventLog.filters.categoryUser",
  SETTINGS: "eventLog.filters.categorySettings",
};
const FILTER_DEBOUNCE_MS = 200;
// Only surface the dimmed-loading state once a refetch has been in flight
// this long -- most requests resolve well under it, so typing quickly no
// longer flashes the list dim/opaque on every keystroke pause.
const FETCH_INDICATOR_DELAY_MS = 150;
// Matches `ActorTargetEvent.target` (backend/app/core/events.py) -- `build_payload`
// derives payload keys from that dataclass's field names, so this has to stay in sync by hand.
const PAYLOAD_TARGET_KEY = "target";

function isKnownCategory(category: string): category is (typeof CATEGORIES)[number] {
  return (CATEGORIES as readonly string[]).includes(category);
}

function getTargetLogin(entry: EventLogEntry): string | undefined {
  return entry.payload &&
    typeof entry.payload === "object" &&
    PAYLOAD_TARGET_KEY in entry.payload
    ? (entry.payload as { [PAYLOAD_TARGET_KEY]?: { login?: string } })[PAYLOAD_TARGET_KEY]?.login
    : undefined;
}

function describeEntry(entry: EventLogEntry): string {
  const actor = entry.actor_login ?? "—";
  const target = getTargetLogin(entry);
  return target ? `${actor} → ${target}` : actor;
}

function formatOccurredAt(iso: string): string {
  return new Date(iso).toLocaleString().replace(",", "");
}

const fieldLabelClassName = "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";
const fieldClassName =
  "rounded-xl border border-border bg-input/60 py-2 text-sm text-foreground outline-none focus:border-primary";

interface EventDetailDialogProps {
  entry: EventLogEntry;
  onClose: () => void;
}

function EventDetailDialog({ entry, onClose }: EventDetailDialogProps) {
  return (
    <Modal onClose={onClose} size="sm" scrollable>
      <EventDetailDialogBody entry={entry} />
    </Modal>
  );
}

function EventDetailDialogBody({ entry }: { entry: EventLogEntry }) {
  const { t } = useTranslation();
  const close = useModalClose();
  const target = getTargetLogin(entry);
  const otherPayload = Object.fromEntries(
    Object.entries(entry.payload ?? {}).filter(([key]) => key !== PAYLOAD_TARGET_KEY),
  );
  const hasOtherPayload = Object.keys(otherPayload).length > 0;
  const [isCopied, setIsCopied] = useState(false);

  const handleCopyPayload = () => {
    navigator.clipboard?.writeText(JSON.stringify(otherPayload, null, 2)).catch(() => {});
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
  };

  return (
    <>
      <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <History className="size-4" />
          </div>
          {t(`eventLog.events.${entry.event_type}`)}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("profile.edit.close")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
        <div className="flex flex-col gap-1 px-3 py-3">
          <InfoRow icon={Clock} label={t("eventLog.columns.occurredAt")}>
            {formatOccurredAt(entry.occurred_at)}
          </InfoRow>
          <InfoRow icon={Tag} label={t("eventLog.filters.category")}>
            {isKnownCategory(entry.category) ? t(CATEGORY_LABEL_KEYS[entry.category]) : entry.category}
          </InfoRow>
          <InfoRow
            icon={User}
            label={t("eventLog.columns.actor")}
            copyValue={entry.actor_login ?? entry.actor_name ?? undefined}
          >
            {entry.actor_login ?? entry.actor_name ?? "—"}
            {entry.actor_id !== null && <span className="text-muted-foreground">#{entry.actor_id}</span>}
          </InfoRow>
          {target && (
            <InfoRow icon={User} label={t("eventLog.detail.target")} copyValue={target}>
              {target}
            </InfoRow>
          )}
          {entry.ip_address && (
            <InfoRow icon={Globe} label={t("eventLog.detail.ip")} copyValue={entry.ip_address}>
              {entry.ip_address}
            </InfoRow>
          )}
        </div>

        {hasOtherPayload && (
          <div className="border-t border-border px-5 py-4">
            <p className={fieldLabelClassName}>{t("eventLog.detail.payload")}</p>
            <div className="relative mt-2">
              <button
                type="button"
                onClick={handleCopyPayload}
                aria-label={t("eventLog.detail.copyPayload")}
                className="absolute right-2 top-2 flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
              >
                {isCopied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
              </button>
              <pre
                className={`overflow-x-auto rounded-xl border border-border p-3 pr-10 font-mono text-[11.5px] text-foreground/80 transition-colors ${
                  isCopied ? "bg-success/10" : "bg-input/60"
                }`}
              >
                {JSON.stringify(otherPayload, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export function EventLogPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [category, setCategory] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [dateFromInput, setDateFromInput] = useState("");
  const [dateToInput, setDateToInput] = useState("");
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [selectedEntry, setSelectedEntry] = useState<EventLogEntry | null>(null);
  // Bumped on every primary load; a load-more from before a filter change
  // discards its result instead of appending to an already-replaced list.
  const loadGenRef = useRef(0);

  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);
  const debouncedDateFrom = useDebouncedValue(dateFromInput, FILTER_DEBOUNCE_MS);
  const debouncedDateTo = useDebouncedValue(dateToInput, FILTER_DEBOUNCE_MS);

  const baseFilters = useMemo<Omit<EventLogFilters, "page" | "pageSize">>(
    () => ({
      category: category || undefined,
      search: debouncedSearch || undefined,
      dateFrom: debouncedDateFrom || undefined,
      dateTo: debouncedDateTo || undefined,
    }),
    [category, debouncedSearch, debouncedDateFrom, debouncedDateTo],
  );

  useEffect(() => {
    const controller = new AbortController();
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    loadGenRef.current += 1;
    setPage(1);
    listEventLog({ ...baseFilters, page: 1, pageSize: DEFAULT_PAGE_SIZE }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setState({ kind: "ready", items: result.items, total: result.total });
        }
      })
      .catch(() => {
        // keep showing whatever's already on screen; only surface the error
        // state when there's nothing else to show
        if (!controller.signal.aborted) {
          setState((prev) => (prev.kind === "ready" ? prev : { kind: "error" }));
        }
      })
      .finally(() => {
        clearTimeout(showFetchingTimeout);
        if (!controller.signal.aborted) setIsFetching(false);
      });
    return () => {
      controller.abort();
      clearTimeout(showFetchingTimeout);
    };
  }, [baseFilters]);

  const handleLoadMore = async () => {
    const gen = loadGenRef.current;
    const nextPage = page + 1;
    setIsLoadingMore(true);
    try {
      const result = await listEventLog({ ...baseFilters, page: nextPage, pageSize: DEFAULT_PAGE_SIZE });
      if (gen !== loadGenRef.current) return;
      setState((prev) =>
        prev.kind === "ready"
          ? { kind: "ready", items: [...prev.items, ...result.items], total: result.total }
          : prev,
      );
      setPage(nextPage);
    } catch {
      // keep current items on failure; the load-more button stays available to retry
    } finally {
      setIsLoadingMore(false);
    }
  };

  const hasMore = state.kind === "ready" && state.items.length < state.total;

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={fieldLabelClassName}>{t("eventLog.filters.category")}</label>
            <SelectDropdown
              id="event-log-category"
              value={category}
              onChange={setCategory}
              icon={Filter}
              placeholder={t("eventLog.filters.categoryAll")}
              options={[
                { value: "", label: t("eventLog.filters.categoryAll") },
                ...CATEGORIES.map((cat) => ({ value: cat, label: t(CATEGORY_LABEL_KEYS[cat]) })),
              ]}
            />
          </div>

          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={fieldLabelClassName}>{t("eventLog.filters.actor")}</label>
            <motion.div
              className="group relative"
              {...bounceTap(bounceStrength)}
            >
              <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus-within:group-hover:text-foreground group-focus-within:text-primary" />
              <input
                id="event-log-actor"
                type="text"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder={t("eventLog.filters.actorPlaceholder")}
                className={`${fieldClassName} w-full pl-9 pr-3`}
              />
            </motion.div>
          </div>

          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={fieldLabelClassName}>{t("eventLog.filters.dateFrom")}</label>
            <DatePickerField
              id="event-log-date-from"
              value={dateFromInput}
              onChange={setDateFromInput}
              placeholder={t("eventLog.filters.dateFrom")}
              clearAriaLabel={t("eventLog.filters.clearDate")}
            />
          </div>

          <div className="flex min-w-40 flex-1 flex-col gap-1.5">
            <label className={fieldLabelClassName}>{t("eventLog.filters.dateTo")}</label>
            <DatePickerField
              id="event-log-date-to"
              value={dateToInput}
              onChange={setDateToInput}
              placeholder={t("eventLog.filters.dateTo")}
              clearAriaLabel={t("eventLog.filters.clearDate")}
            />
          </div>
        </div>
      </div>

      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && (
          <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            <p className="text-sm">{t("eventLog.loading")}</p>
          </div>
        )}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">{t("eventLog.loadError")}</p>
          </div>
        )}
        {state.kind === "ready" && (
          <>
            {state.items.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
                <Inbox className="size-5" />
                <p className="text-sm">{t("eventLog.empty")}</p>
              </div>
            )}
            {state.items.length > 0 && (
              <>
                <div className="overflow-x-auto">
                  {/* px-2 reserves headroom so the rows' whileTap scale (below) grows into
                      padding, not past this track's own box -- keeps the scroll container's
                      measured width stable and avoids a scrollbar flicker on tap. */}
                  <div className="min-w-[640px] px-2">
                    <div className="grid grid-cols-[170px_1.2fr_1fr_140px] gap-4 border-b border-border px-3 pb-2.5">
                      <span className={fieldLabelClassName}>
                        {t("eventLog.columns.occurredAt")}
                      </span>
                      <span className={fieldLabelClassName}>
                        {t("eventLog.columns.eventType")}
                      </span>
                      <span className={fieldLabelClassName}>{t("eventLog.columns.actor")}</span>
                      <span className={fieldLabelClassName}>{t("eventLog.detail.ip")}</span>
                    </div>
                    <div className="mt-1 flex flex-col divide-y divide-border/50">
                      {state.items.map((entry) => (
                        <motion.div
                          key={entry.id}
                          role="button"
                          tabIndex={0}
                          onClick={() => setSelectedEntry(entry)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              setSelectedEntry(entry);
                            }
                          }}
                          {...bounceTap(bounceStrength, 0.03)}
                          className="grid cursor-pointer grid-cols-[170px_1.2fr_1fr_140px] items-center gap-4 rounded-full px-3 py-2.5 transition-colors hover:bg-white/[0.04]"
                        >
                          <span className="truncate font-mono text-[12.5px] text-foreground/80">
                            {formatOccurredAt(entry.occurred_at)}
                          </span>
                          <span className="truncate text-[13.5px] font-medium text-foreground/90">
                            {t(`eventLog.events.${entry.event_type}`)}
                          </span>
                          <span className="truncate text-[12.5px] text-foreground">
                            {describeEntry(entry)}
                          </span>
                          <span className="truncate font-mono text-[12.5px] text-foreground">
                            {entry.ip_address ?? "—"}
                          </span>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </div>
                {hasMore && (
                  <div className="mt-4 flex justify-center">
                    <motion.button
                      type="button"
                      onClick={() => void handleLoadMore()}
                      disabled={isLoadingMore}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isLoadingMore ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                      {isLoadingMore
                        ? t("eventLog.pagination.loadingMore")
                        : t("eventLog.pagination.loadMore")}
                    </motion.button>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      {selectedEntry && (
        <EventDetailDialog entry={selectedEntry} onClose={() => setSelectedEntry(null)} />
      )}
    </div>
  );
}
