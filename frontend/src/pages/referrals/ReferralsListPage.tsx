import { AlertCircle, ChevronDown, ChevronRight, CornerUpLeft, Inbox, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  REFERRALS_PAGE_SIZE,
  listReferrals,
  type ReferralListFilters,
  type ReferralListItem,
  type ReferralRewardType,
  type ReferralUser,
} from "@entities/referrals/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { UserReferralsDialog } from "@features/user-referrals/UserReferralsDialog";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { PeriodPills } from "@shared/ui/PeriodPills";
import type { PeriodDays } from "@shared/ui/PeriodToggle";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";

type LoadState =
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "ready"; items: ReferralListItem[]; total: number };

const FETCH_INDICATOR_DELAY_MS = 150;
const LEVEL_FILTERS = [0, 1, 2, 3];
const REWARD_TYPES: ReferralRewardType[] = ["EXTRA_DAYS", "POINTS"];

const ROW_GRID_CLASSNAME =
  "grid grid-cols-[36px_minmax(0,1fr)_minmax(0,220px)_84px_130px_64px_16px] items-center gap-3";

const LEVEL_BADGE_CLASSNAME: Record<number, string> = {
  1: "border-primary/30 bg-primary/10 text-primary",
  2: "border-white/15 bg-white/[0.05] text-foreground",
  3: "border-border bg-white/[0.03] text-muted-foreground",
};

interface DayGroup {
  key: string;
  date: Date;
  items: ReferralListItem[];
}

// Items arrive sorted by created_at desc, so consecutive grouping is enough.
function groupByDay(items: ReferralListItem[]): DayGroup[] {
  const groups: DayGroup[] = [];
  for (const item of items) {
    const date = new Date(item.created_at);
    const key = date.toDateString();
    const last = groups[groups.length - 1];
    if (last?.key === key) last.items.push(item);
    else groups.push({ key, date, items: [item] });
  }
  return groups;
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

export function ReferralsListPage() {
  const { t, i18n } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [isFetching, setIsFetching] = useState(false);
  const [level, setLevel] = useState(0);
  const [period, setPeriod] = useState<PeriodDays>(0);
  const [page, setPage] = useState(1);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [collapsedDays, setCollapsedDays] = useState<ReadonlySet<string>>(new Set());
  const [statsUser, setStatsUser] = useState<ReferralUser | null>(null);
  // Bumped on every primary load; a load-more from before a filter change
  // discards its result instead of appending to an already-replaced list.
  const loadGenRef = useRef(0);

  const currentUserState = useCurrentUser();
  const permissions =
    currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canViewStats = permissions.includes("REFERRALS_VIEW");

  const toggleDay = (key: string) =>
    setCollapsedDays((prev) => {
      const next = new Set(prev);
      if (!next.delete(key)) next.add(key);
      return next;
    });

  const baseFilters = useMemo<ReferralListFilters>(
    () => ({
      level: level || undefined,
      createdFrom: period ? new Date(Date.now() - period * 86_400_000).toISOString() : undefined,
    }),
    [level, period],
  );

  useEffect(() => {
    const controller = new AbortController();
    const showFetchingTimeout = setTimeout(() => {
      if (!controller.signal.aborted) setIsFetching(true);
    }, FETCH_INDICATOR_DELAY_MS);
    loadGenRef.current += 1;
    setPage(1);
    listReferrals({ ...baseFilters, page: 1, pageSize: REFERRALS_PAGE_SIZE }, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) {
          setState({ kind: "ready", items: result.items, total: result.total });
        }
      })
      .catch(() => {
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
      const result = await listReferrals({ ...baseFilters, page: nextPage, pageSize: REFERRALS_PAGE_SIZE });
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
  const groups = useMemo(() => (state.kind === "ready" ? groupByDay(state.items) : []), [state]);

  const formatDay = (date: Date): string => {
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(today.getDate() - 1);
    if (date.toDateString() === today.toDateString()) return t("payments.today");
    if (date.toDateString() === yesterday.toDateString()) return t("payments.yesterday");
    return date.toLocaleDateString(i18n.language, {
      day: "numeric",
      month: "long",
      year: date.getFullYear() === today.getFullYear() ? undefined : "numeric",
    });
  };

  const formatRewards = (item: ReferralListItem): string | null => {
    const parts = REWARD_TYPES.flatMap((type) => {
      const amount = item.reward_amounts[type];
      if (amount === undefined) return [];
      return [`+${amount} ${t(`referrals.units.${type}`, { count: Number(amount) })}`];
    });
    return parts.length ? parts.join(" · ") : null;
  };

  const userHandle = (user: ReferralUser): string =>
    [user.username ? `@${user.username}` : null, user.telegram_id !== null ? `ID ${user.telegram_id}` : null]
      .filter(Boolean)
      .join(" · ");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedPills
          value={level}
          onChange={setLevel}
          ariaLabel={t("referrals.list.levelFilter")}
          options={LEVEL_FILTERS.map((value) => ({
            value,
            label: value === 0 ? t("referrals.list.levelAll") : t("referrals.list.level", { level: value }),
          }))}
        />
        <PeriodPills value={period} onChange={setPeriod} ariaLabel={t("referrals.list.periodFilter")} />
      </div>

      <div className="relative rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && <Spinner className="py-12" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">
              {permissions.includes("REFERRALS_LIST") ? t("referrals.list.loadError") : t("referrals.list.noPermission")}
            </p>
          </div>
        )}
        {state.kind === "ready" && state.items.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-12 text-muted-foreground">
            <Inbox className="size-5" />
            <p className="text-sm">{t("referrals.list.empty")}</p>
          </div>
        )}
        {state.kind === "ready" && state.items.length > 0 && (
          <>
            <div
              className={`${ROW_GRID_CLASSNAME} mb-1 border-b border-border px-3 pb-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground`}
            >
              <span className="col-span-2">{t("referrals.list.columns.referred")}</span>
              <span>{t("referrals.list.columns.referrer")}</span>
              <span>{t("referrals.list.columns.level")}</span>
              <span>{t("referrals.list.columns.rewards")}</span>
              <span>{t("referrals.list.columns.time")}</span>
              <span />
            </div>
            <div className="flex flex-col gap-3">
              {groups.map((group) => (
                <section key={group.key} className="flex flex-col">
                  <h3>
                    <button
                      type="button"
                      aria-expanded={!collapsedDays.has(group.key)}
                      onClick={() => toggleDay(group.key)}
                      className="group flex w-full items-center gap-2.5 rounded-full px-3 py-1.5 text-left"
                    >
                      <ChevronDown
                        className={`size-3.5 text-muted-foreground transition-transform group-hover:text-foreground ${
                          collapsedDays.has(group.key) ? "-rotate-90" : ""
                        }`}
                      />
                      <span className="-ml-1 text-[12px] font-semibold text-foreground">{formatDay(group.date)}</span>
                      <span className="-ml-1 text-[11.5px] tabular-nums text-muted-foreground">
                        {group.items.length}
                      </span>
                    </button>
                  </h3>
                  <div
                    className={`flex flex-col divide-y divide-border/50 ${collapsedDays.has(group.key) ? "hidden" : ""}`}
                  >
                    {group.items.map((item) => {
                      const referred = item.referred;
                      const canOpen = canViewStats && referred !== null;
                      const rewards = formatRewards(item);
                      return (
                        <motion.button
                          key={item.id}
                          type="button"
                          disabled={!canOpen}
                          onClick={() => setStatsUser(referred)}
                          {...(canOpen && bounceTap(bounceStrength, 0.03))}
                          className={`${ROW_GRID_CLASSNAME} w-full rounded-full px-3 py-2.5 text-left [transition-property:background-color] duration-150 enabled:hover:bg-white/[0.04] disabled:cursor-default`}
                        >
                          <span
                            aria-hidden
                            className="flex size-9 items-center justify-center rounded-full bg-white/[0.06] text-[13px] font-semibold text-foreground"
                          >
                            {referred ? initials(referred.name) : "?"}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-[13.5px] font-medium text-foreground">
                              {referred?.name ?? t("referrals.list.deletedUser")}
                            </span>
                            {referred && (
                              <span className="block truncate font-mono text-[12px] text-muted-foreground">
                                {userHandle(referred)}
                              </span>
                            )}
                          </span>
                          <span className="flex min-w-0 items-center gap-2">
                            <CornerUpLeft className="size-3.5 shrink-0 text-muted-foreground" />
                            <span
                              aria-hidden
                              className="flex size-6 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[10.5px] font-semibold text-foreground"
                            >
                              {item.referrer ? initials(item.referrer.name) : "?"}
                            </span>
                            <span className="truncate text-[13px] text-foreground">
                              {item.referrer?.name ?? t("referrals.list.deletedUser")}
                            </span>
                          </span>
                          <span>
                            <span
                              className={`rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${
                                LEVEL_BADGE_CLASSNAME[item.level] ?? LEVEL_BADGE_CLASSNAME[3]
                              }`}
                            >
                              {t("referrals.list.levelBadge", { level: item.level })}
                            </span>
                          </span>
                          <span className="min-w-0 tabular-nums">
                            <span
                              className={`block truncate text-[14px] ${
                                rewards ? "font-semibold text-foreground" : "font-medium text-muted-foreground"
                              }`}
                            >
                              {rewards ?? "—"}
                            </span>
                            <span className="block truncate text-[11.5px] text-muted-foreground">
                              {item.reward_count
                                ? t("referrals.list.rewardCount", { count: item.reward_count })
                                : t("referrals.list.noRewards")}
                            </span>
                          </span>
                          <span className="text-[13px] tabular-nums text-foreground">
                            {new Date(item.created_at).toLocaleTimeString(i18n.language, {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                          {canOpen ? <ChevronRight className="size-4 text-muted-foreground" /> : <span />}
                        </motion.button>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
            {hasMore && (
              <div className="mt-4 flex justify-center">
                <motion.button
                  type="button"
                  onClick={() => void handleLoadMore()}
                  disabled={isLoadingMore}
                  aria-label={isLoadingMore ? t("payments.pagination.loadingMore") : undefined}
                  {...bounceTap(bounceStrength)}
                  className="flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isLoadingMore ? <Loader2 className="size-3.5 animate-spin" /> : <ChevronDown className="size-3.5" />}
                  {!isLoadingMore && t("payments.pagination.loadMore")}
                </motion.button>
              </div>
            )}
          </>
        )}
      </div>

      {statsUser && (
        <UserReferralsDialog
          userId={statsUser.id}
          userName={statsUser.name}
          canAdjustPoints={permissions.includes("REFERRALS_POINTS_MANAGE")}
          onClose={() => setStatsUser(null)}
        />
      )}
    </div>
  );
}
