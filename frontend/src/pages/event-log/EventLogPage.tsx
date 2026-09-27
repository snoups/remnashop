import {
  Activity,
  AlertCircle,
  Anchor,
  AtSign,
  Ban,
  Braces,
  CalendarClock,
  Check,
  ChevronDown,
  CircleCheck,
  Clock,
  Coins,
  Copy,
  Crosshair,
  Crown,
  Filter,
  Fingerprint,
  Gift,
  Globe,
  HandCoins,
  Hash,
  History,
  Inbox,
  Info,
  KeyRound,
  Languages,
  Link,
  Loader2,
  Lock,
  LockOpen,
  LogIn,
  LogOut,
  Mail,
  Package,
  PackagePlus,
  RefreshCcw,
  RefreshCw,
  Repeat,
  Search,
  Send,
  Server,
  Shield,
  ShieldAlert,
  ShieldBan,
  ShieldCheck,
  ShieldMinus,
  ShieldPlus,
  ShieldX,
  ShoppingCart,
  Siren,
  Star,
  Tag,
  Tags,
  Ticket,
  TicketCheck,
  Undo2,
  Unlink,
  User,
  UserMinus,
  UserPlus,
  UserX,
  Users,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { TFunction } from "i18next";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import {
  DEFAULT_PAGE_SIZE,
  type EventLogEntry,
  type EventLogFilters,
  listEventLog,
} from "@entities/event-log/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { BounceIcon } from "@shared/ui/BounceIcon";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { InfoRow } from "@shared/ui/InfoRow";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";

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
const EVENT_ICONS: Record<string, LucideIcon> = {
  LoginSucceededEvent: LogIn,
  LoginFailedEvent: ShieldX,
  OwnerBootstrappedEvent: Crown,
  BootstrapConflictEvent: ShieldAlert,
  OAuthLoginSucceededEvent: LogIn,
  OAuthLoginFailedEvent: ShieldX,
  OAuthIdentityConnectedEvent: Link,
  OAuthIdentityDisconnectedEvent: Unlink,
  SessionRevokedEvent: LogOut,
  SessionTheftDetectedEvent: Siren,
  UserSessionRevokedByAdminEvent: LogOut,
  AdminCreatedEvent: UserPlus,
  AdminPromotedEvent: ShieldPlus,
  AdminPermissionsUpdatedEvent: ShieldCheck,
  AdminDemotedEvent: ShieldMinus,
  AdminDeletedEvent: UserMinus,
  UserDeletedEvent: UserX,
  TelegramUserRegisteredEvent: Send,
  LocaleActivatedEvent: Languages,
  LocaleDeactivatedEvent: Languages,
  AnchorSwitchedEvent: Anchor,
  BasePricesAdjustedEvent: Tags,
  ApiTokenCreatedEvent: KeyRound,
  ApiTokenRevokedEvent: KeyRound,
  BlacklistEntryAddedEvent: Ban,
  BlacklistEntryRemovedEvent: CircleCheck,
  BlacklistReconciledEvent: RefreshCw,
  CurrencyRateChangedEvent: Coins,
  OidcIssuerChangedEvent: Server,
  PasskeyLoginFailedEvent: Fingerprint,
  PasskeyLoginSucceededEvent: Fingerprint,
  PasskeyRegisteredEvent: Fingerprint,
  PasskeyRemovedEvent: Fingerprint,
  PlanChangedEvent: Package,
  PointsWithdrawalRequestedEvent: HandCoins,
  PromocodeActivatedEvent: TicketCheck,
  PromocodeChangedEvent: Ticket,
  ReferralAttachedEvent: Users,
  ReferralRewardIssuedEvent: Gift,
  SubscriptionAddOnGrantedEvent: PackagePlus,
  SubscriptionChangedEvent: Repeat,
  SubscriptionPurchasedEvent: ShoppingCart,
  SubscriptionRenewedEvent: CalendarClock,
  SubscriptionStatusSyncedEvent: RefreshCcw,
  TelegramRegistrationBlockedEvent: ShieldBan,
  UserBlockedEvent: Lock,
  UserPointsAdjustedEvent: Star,
  UserUnblockedEvent: LockOpen,
  UsersBulkBlockedEvent: Lock,
  UsersBulkUnblockedEvent: LockOpen,
  PaymentOrderRefundedEvent: Undo2,
};

function EventTypeIcon({ eventType, className }: { eventType: string; className?: string }) {
  const Icon = EVENT_ICONS[eventType] ?? History;
  return <Icon className={className} />;
}

const FILTER_DEBOUNCE_MS = 200;
// Only surface the dimmed-loading state once a refetch has been in flight
// this long -- most requests resolve well under it, so typing quickly no
// longer flashes the list dim/opaque on every keystroke pause.
const FETCH_INDICATOR_DELAY_MS = 150;
// Matches `ActorTargetEvent.target` (backend/app/core/events.py) -- `build_payload`
// derives payload keys from that dataclass's field names, so this has to stay in sync by hand.
const PAYLOAD_TARGET_KEY = "target";

function getTargetLogin(entry: EventLogEntry): string | undefined {
  return entry.payload &&
    typeof entry.payload === "object" &&
    PAYLOAD_TARGET_KEY in entry.payload
    ? (entry.payload as { [PAYLOAD_TARGET_KEY]?: { login?: string } })[PAYLOAD_TARGET_KEY]?.login
    : undefined;
}

interface UserSnapshot {
  id?: number | null;
  login?: string | null;
  name?: string | null;
  role?: string | null;
  telegram_id?: number | null;
  username?: string | null;
  email?: string | null;
}

// Mirrors `_sanitize_user` (backend/app/core/outbox_event_publisher.py); rows
// written before telegram_id/username/email were added carry only id/login/name/role.
function getUserSnapshot(entry: EventLogEntry, key: string): UserSnapshot | undefined {
  const value = entry.payload?.[key];
  return value && typeof value === "object" ? (value as UserSnapshot) : undefined;
}

function getInitiator(entry: EventLogEntry): UserSnapshot | undefined {
  const snapshot = getUserSnapshot(entry, "actor") ?? getUserSnapshot(entry, "user");
  if (snapshot) return snapshot;
  if (entry.actor_id === null && !entry.actor_login && !entry.actor_name) return undefined;
  return { id: entry.actor_id, login: entry.actor_login, name: entry.actor_name };
}

// Requests from someone not signed in -- no actor exists, only the request's IP.
const ANONYMOUS_EVENT_TYPES: ReadonlySet<string> = new Set([
  "LoginFailedEvent",
  "OAuthLoginFailedEvent",
  "PasskeyLoginFailedEvent",
  "BootstrapConflictEvent",
  "SessionTheftDetectedEvent",
]);

// The API-token actor has id 0 (api/dependencies/public.py), the system actor role SYSTEM.
function isApiToken(user: UserSnapshot): boolean {
  return user.id === 0;
}

function isSystemActor(user: UserSnapshot): boolean {
  return user.role === "SYSTEM";
}

function getMissingInitiatorKey(entry: EventLogEntry): string {
  return ANONYMOUS_EVENT_TYPES.has(entry.event_type) ? "eventLog.detail.anonymous" : "eventLog.detail.system";
}

function describeEntry(entry: EventLogEntry, t: TFunction): string {
  const initiator = getInitiator(entry);
  const actor = !initiator
    ? t(getMissingInitiatorKey(entry))
    : isSystemActor(initiator)
      ? t("eventLog.detail.system")
      : (initiator.login ?? initiator.name ?? "—");
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

type EventDetailTab = "details" | "payload";

const sectionClassName = "rounded-2xl border border-white/[0.08] bg-white/[0.03] p-1.5";
const sectionTitleClassName =
  "flex items-center gap-1.5 px-2.5 pb-1 pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground";

interface ParticipantSectionProps {
  title: string;
  icon: ComponentType<{ className?: string }>;
  user: UserSnapshot | undefined;
  missingLabel?: string;
  ipAddress?: string | null;
}

function ParticipantSection({ title, icon: Icon, user, missingLabel, ipAddress }: ParticipantSectionProps) {
  const { t } = useTranslation();
  const isSystem = user !== undefined && isSystemActor(user);
  const name = isSystem ? t("eventLog.detail.system") : (user?.name ?? missingLabel ?? "—");
  const roleLabel =
    user === undefined || isSystem
      ? undefined
      : isApiToken(user)
        ? t("eventLog.detail.apiToken")
        : user.role
          ? t(`roles.${user.role}`)
          : undefined;
  // id 0 and below is a synthetic actor (API token / system), not a real row
  const userId = user?.id && user.id > 0 ? String(user.id) : undefined;
  // the system actor carries telegram_id -1 (core/usecase.py's _system_actor)
  const telegramId = user?.telegram_id && user.telegram_id > 0 ? String(user.telegram_id) : undefined;

  return (
    <section className={sectionClassName}>
      <h3 className={sectionTitleClassName}>
        <Icon className="size-3.5" />
        {title}
      </h3>
      <InfoRow icon={User} label={t("eventLog.detail.name")} copyValue={user?.name ?? undefined}>
        <span className="truncate">{name}</span>
      </InfoRow>
      {user?.login && (
        <InfoRow icon={KeyRound} label={t("users.details.login")} copyValue={user.login}>
          <span className="truncate">{user.login}</span>
        </InfoRow>
      )}
      {userId && (
        <InfoRow icon={Hash} label={t("users.details.id")} copyValue={userId}>
          {userId}
        </InfoRow>
      )}
      {user?.email && (
        <InfoRow icon={Mail} label={t("users.details.email")} copyValue={user.email}>
          <span className="truncate">{user.email}</span>
        </InfoRow>
      )}
      {roleLabel && (
        <InfoRow icon={Shield} label={t("eventLog.detail.role")}>
          {roleLabel}
        </InfoRow>
      )}
      {ipAddress && (
        <InfoRow icon={Globe} label={t("eventLog.detail.ip")} copyValue={ipAddress}>
          {ipAddress}
        </InfoRow>
      )}
      {(telegramId || user?.username) && (
        <div className="m-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-1">
          <h4 className={sectionTitleClassName}>
            <Send className="size-3.5" />
            {t("eventLog.detail.telegram")}
          </h4>
          {telegramId && (
            <InfoRow icon={Hash} label={t("users.details.telegramId")} copyValue={telegramId}>
              {telegramId}
            </InfoRow>
          )}
          {user?.username && (
            <InfoRow icon={AtSign} label={t("users.details.username")} copyValue={user.username}>
              <span className="truncate">@{user.username}</span>
            </InfoRow>
          )}
        </div>
      )}
    </section>
  );
}

function EventDetailDialog({ entry, onClose }: EventDetailDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <EventDetailDialogBody entry={entry} />
    </Modal>
  );
}

function EventDetailDialogBody({ entry }: { entry: EventLogEntry }) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [tab, setTab] = useState<EventDetailTab>("details");
  const targetUser = getUserSnapshot(entry, PAYLOAD_TARGET_KEY);
  const otherPayload = Object.fromEntries(
    Object.entries(entry.payload ?? {}).filter(([key]) => key !== PAYLOAD_TARGET_KEY),
  );
  const hasOtherPayload = Object.keys(otherPayload).length > 0;
  const [isCopied, setIsCopied] = useState(false);
  const [contentRef, contentHeight] = useMeasuredHeight();

  const tabs: { key: EventDetailTab; label: string; icon: ComponentType<{ className?: string }> }[] = [
    { key: "details", label: t("eventLog.detail.tabs.details"), icon: Info },
    ...(hasOtherPayload
      ? [{ key: "payload" as const, label: t("eventLog.detail.tabs.payload"), icon: Braces }]
      : []),
  ];

  const handleCopyPayload = () => {
    navigator.clipboard?.writeText(JSON.stringify(otherPayload, null, 2)).catch(() => {});
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
  };

  return (
    <>
      <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <EventTypeIcon eventType={entry.event_type} className="size-4" />
          </div>
          <h2 className="truncate text-base font-bold text-foreground">
            {t(`eventLog.events.${entry.event_type}`)}
          </h2>
        </div>
        <button
          type="button"
          onClick={close}
          aria-label={t("profile.edit.close")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      {tabs.length > 1 && (
        <div className="px-4 pb-3 pt-4">
          <div
            role="tablist"
            className="flex gap-1 rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md"
          >
            {tabs.map((item) => {
              const isActive = tab === item.key;
              return (
                <motion.button
                  key={item.key}
                  type="button"
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => setTab(item.key)}
                  className="group relative isolate block min-w-0 flex-1 rounded-full text-sm font-medium"
                  initial="rest"
                  whileHover="hover"
                  whileTap="tap"
                >
                  <motion.span
                    aria-hidden
                    variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
                    className={`absolute inset-0 rounded-full transition-colors ${
                      isActive ? "bg-accent" : "group-hover:bg-white/[0.06]"
                    }`}
                  />
                  <span
                    className={`relative z-10 flex items-center justify-center gap-1.5 whitespace-nowrap px-3 py-1.5 text-[13px] ${
                      isActive ? "text-primary" : "text-foreground"
                    }`}
                  >
                    <BounceIcon icon={item.icon} size={14} hoverSize={17} />
                    {item.label}
                  </span>
                </motion.button>
              );
            })}
          </div>
        </div>
      )}

      <div className={`min-h-0 flex-1 overflow-y-auto px-4 pb-4 ${tabs.length > 1 ? "" : "pt-4"}`}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {tab === "details" && (
              <div className="flex flex-col gap-3">
                <section className={sectionClassName}>
                  <h3 className={sectionTitleClassName}>
                    <Activity className="size-3.5" />
                    {t("eventLog.detail.sections.event")}
                  </h3>
                  <InfoRow icon={Hash} label={t("eventLog.detail.id")} copyValue={String(entry.id)}>
                    {entry.id}
                  </InfoRow>
                  <InfoRow icon={Clock} label={t("eventLog.columns.occurredAt")}>
                    {formatOccurredAt(entry.occurred_at)}
                  </InfoRow>
                  <InfoRow icon={Tag} label={t("eventLog.detail.eventCode")} copyValue={entry.event_type}>
                    {entry.event_type}
                  </InfoRow>
                </section>

                <ParticipantSection
                  title={t("eventLog.columns.actor")}
                  icon={User}
                  user={getInitiator(entry)}
                  missingLabel={t(getMissingInitiatorKey(entry))}
                  ipAddress={entry.ip_address}
                />
                {targetUser && (
                  <ParticipantSection title={t("eventLog.detail.target")} icon={Crosshair} user={targetUser} />
                )}
              </div>
            )}

            {tab === "payload" && (
              <section className={sectionClassName}>
                <div className="flex items-center justify-between py-1 pl-2.5 pr-1">
                  <h3 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-foreground">
                    <Braces className="size-3.5" />
                    {t("eventLog.detail.json")}
                  </h3>
                  <button
                    type="button"
                    onClick={handleCopyPayload}
                    aria-label={t("eventLog.detail.copyPayload")}
                    className="flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
                  >
                    <Copy className="size-3.5" />
                  </button>
                </div>
                <div className="relative m-1">
                  <pre
                    className={`overflow-x-auto rounded-xl bg-input/60 p-3 font-mono text-[11.5px] text-foreground/80 transition-opacity ${
                      isCopied ? "opacity-20" : ""
                    }`}
                  >
                    {JSON.stringify(otherPayload, null, 2)}
                  </pre>
                  {isCopied && (
                    <span className="absolute inset-0 flex items-center justify-center gap-1.5 text-[12.5px] font-medium text-success">
                      <Check className="size-3.5" />
                      {t("app.copied")}
                    </span>
                  )}
                </div>
              </section>
            )}
          </div>
        </motion.div>
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
  const [searchInput, setSearchInput] = useUrlSearch();
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
        {state.kind === "loading" && <Spinner className="py-12" />}
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
                <div className="-mx-2 overflow-x-auto">
                  {/* px-2 reserves headroom so the rows' whileTap scale (below) grows into
                      padding, not past this track's own box -- keeps the scroll container's
                      measured width stable and avoids a scrollbar flicker on tap. */}
                  <div className="min-w-[640px] px-2">
                    <div className="grid grid-cols-[1.2fr_170px_1fr_140px] gap-4 border-b border-border px-3 pb-2.5">
                      <span className={fieldLabelClassName}>
                        {t("eventLog.columns.eventType")}
                      </span>
                      <span className={fieldLabelClassName}>
                        {t("eventLog.columns.occurredAt")}
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
                          className="grid cursor-pointer grid-cols-[1.2fr_170px_1fr_140px] items-center gap-4 rounded-full px-3 py-2.5 transition-colors hover:bg-white/[0.04]"
                        >
                          <span className="flex min-w-0 items-center gap-3 text-[13.5px] font-medium text-foreground/90">
                            <span
                              aria-hidden
                              className="flex size-9 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground"
                            >
                              <EventTypeIcon eventType={entry.event_type} className="size-4" />
                            </span>
                            <span className="truncate">{t(`eventLog.events.${entry.event_type}`)}</span>
                          </span>
                          <span className="truncate font-mono text-[12.5px] text-foreground/80">
                            {formatOccurredAt(entry.occurred_at)}
                          </span>
                          <span className="truncate text-[12.5px] text-foreground">
                            {describeEntry(entry, t)}
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
                      aria-label={isLoadingMore ? t("eventLog.pagination.loadingMore") : undefined}
                      {...bounceTap(bounceStrength)}
                      className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {isLoadingMore ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <ChevronDown className="size-3.5" />
                      )}
                      {!isLoadingMore && t("eventLog.pagination.loadMore")}
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
