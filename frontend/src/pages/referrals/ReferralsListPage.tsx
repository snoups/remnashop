import { CalendarPlus, CalendarRange, ChevronRight, Coins, CornerUpLeft, Gift, ListOrdered, UserPlus } from "lucide-react";
import { useMemo, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import {
  REFERRALS_PAGE_SIZE,
  getReferralSummary,
  listReferrals,
  type ReferralListFilters,
  type ReferralListItem,
  type ReferralRewardType,
  type ReferralSummary,
  type ReferralUser,
} from "@entities/referrals/api";
import { usePermissions } from "@entities/user/use-current-user";
import { UserReferralsDialog } from "@features/user-referrals/UserReferralsDialog";
import { userHandle } from "@features/user-referrals/format";
import { DAY_MS, previousWindow } from "@shared/lib/period";
import { LoadGate, LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { formatPercent } from "@shared/lib/format";
import { formatTime } from "@shared/lib/relative-time";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { formatDayLabel, groupByDay } from "@shared/lib/day-groups";
import { useCollapsedSet } from "@shared/lib/use-collapsed-set";
import { initials } from "@shared/lib/initials";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { Collapse } from "@shared/ui/Collapse";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import type { PeriodDays } from "@shared/ui/PeriodPills";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { RefetchSpinner, Spinner } from "@shared/ui/Spinner";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { KpiTile, type KpiTrend } from "@shared/ui/KpiTile";
import { GLASS_LIST_HEAD_CLASS, LIST_BODY_CLASS } from "@shared/ui/classes";
import { ListRow } from "@shared/ui/ListRow";

const FILTER_DEBOUNCE_MS = 200;
const LEVELS = [1, 2, 3];
const REWARD_TYPES: ReferralRewardType[] = ["EXTRA_DAYS", "POINTS"];
const REWARD_TYPE_ICONS: Record<ReferralRewardType, ComponentType<{ className?: string }>> = {
  EXTRA_DAYS: CalendarPlus,
  POINTS: Coins,
};
const PERIODS: PeriodDays[] = [0, 7, 30, 90];

const ROW_GRID_CLASSNAME =
  "grid grid-cols-[32px_minmax(0,1fr)_minmax(0,220px)_84px_130px_64px_16px] items-center gap-3";

const LEVEL_BADGE_TONE: Record<number, BadgeTone> = {
  1: "accent",
  2: "neutral",
  3: "neutral",
};

export function ReferralsListPage() {
  const { t, i18n } = useTranslation();
  const [level, setLevel] = useState("");
  const [rewardStatus, setRewardStatus] = useState("");
  const [rewardType, setRewardType] = useState("");
  const [searchInput, setSearchInput] = useUrlSearch();
  const debouncedSearch = useDebouncedValue(searchInput, FILTER_DEBOUNCE_MS);
  const [period, setPeriod] = useState<PeriodDays>(0);
  const [statsUser, setStatsUser] = useState<ReferralUser | null>(null);

  const permissions = usePermissions();
  const canViewStats = permissions.includes("REFERRALS_VIEW");
  const canViewSummary = permissions.includes("REFERRALS_SUMMARY_VIEW");

  const baseFilters = useMemo<ReferralListFilters>(
    () => ({
      level: level ? Number(level) : undefined,
      createdFrom: period ? new Date(Date.now() - period * DAY_MS).toISOString() : undefined,
      search: debouncedSearch || undefined,
      hasRewards: rewardStatus ? rewardStatus === "true" : undefined,
      rewardType: (rewardType || undefined) as ReferralRewardType | undefined,
    }),
    [level, period, debouncedSearch, rewardStatus, rewardType],
  );

  const { state, isFetching, isLoadingMore, hasMore, loadMore: handleLoadMore } = usePaginatedList(
    (filters, page, signal) => listReferrals({ ...filters, page, pageSize: REFERRALS_PAGE_SIZE }, signal),
    baseFilters,
  );

  const [summaryState] = useAsyncResource(
    (signal) => (canViewSummary ? getReferralSummary(baseFilters, signal) : Promise.resolve(null)),
    { deps: [canViewSummary, baseFilters], keepData: true },
  );
  const [compareState] = useAsyncResource(
    (signal) =>
      canViewSummary
        ? getReferralSummary({ ...baseFilters, ...previousWindow(period) }, signal)
        : Promise.resolve(null),
    { deps: [canViewSummary, baseFilters, period] },
  );
  const summary = summaryState.kind === "ready" ? summaryState.data : null;
  const compareSummary = compareState.kind === "ready" ? compareState.data : null;

  const groups = useMemo(
    () => (state.kind === "ready" ? groupByDay(state.items, (item) => item.created_at) : []),
    [state],
  );
  const [collapsedDays, toggleDay] = useCollapsedSet();

  const formatRewards = (item: ReferralListItem): string | null => {
    const parts = REWARD_TYPES.flatMap((type) => {
      const amount = item.reward_amounts[type];
      if (amount === undefined) return [];
      return [`+${amount} ${t(`referrals.units.${type}`, { count: Number(amount) })}`];
    });
    return parts.length ? parts.join(" · ") : null;
  };

  const none = t("common.none");
  const rewardAmount = (source: ReferralSummary, type: ReferralRewardType): number =>
    Math.trunc(Number(source.reward_amounts[type] ?? 0));
  const rewardTotal = (type: ReferralRewardType): string =>
    summary ? rewardAmount(summary, type).toLocaleString(i18n.language) : none;
  const trendHint = period ? t("referrals.summary.periodTrend", { days: period }) : t("referrals.summary.totalTrend");
  const trend = (pick: (s: ReferralSummary) => number): KpiTrend | undefined =>
    summary && compareSummary ? { delta: pick(summary) - pick(compareSummary), hint: trendHint } : undefined;

  return (
    // as the transactions page: the filter bar floats over a scroller of its own, whose fade clears the bar
    <div data-fills-main className="relative flex flex-1 flex-col md:min-h-0 md:pr-[var(--scrollbar-size)] md:-mb-5">
      <div className="glass-panel flex shrink-0 flex-wrap items-center gap-2 rounded-3xl p-1.5 md:absolute md:left-0 md:right-[var(--scrollbar-size)] md:top-0 md:z-10 md:flex-nowrap">
        <SearchField
          id="referrals-search"
          label={t("referrals.list.search")}
          hideLabel
          compact
          placeholder={t("referrals.list.searchPlaceholder")}
          value={searchInput}
          onChange={setSearchInput}
        />
        <div className="w-40 min-w-0">
          <SelectDropdown
            id="referrals-level"
            value={level}
            onChange={setLevel}
            icon={ListOrdered}
            size="compact"
            glassPopover
            placeholder={t("referrals.list.levelAll")}
            options={[
              { value: "", label: t("referrals.list.levelAll"), icon: ListOrdered },
              ...LEVELS.map((value) => ({
                value: String(value),
                label: t("referrals.list.level", { level: value }),
                icon: ListOrdered,
              })),
            ]}
          />
        </div>
        <div className="w-40 min-w-0">
          <SelectDropdown
            id="referrals-reward-status"
            value={rewardStatus}
            onChange={setRewardStatus}
            icon={Gift}
            size="compact"
            glassPopover
            placeholder={t("referrals.list.rewardStatusAll")}
            options={[
              { value: "", label: t("referrals.list.rewardStatusAll"), icon: Gift },
              { value: "true", label: t("referrals.list.rewardStatusWith"), icon: Gift },
              { value: "false", label: t("referrals.list.rewardStatusWithout"), icon: Gift },
            ]}
          />
        </div>
        <div className="w-40 min-w-0">
          <SelectDropdown
            id="referrals-reward-type"
            value={rewardType}
            onChange={setRewardType}
            icon={Coins}
            size="compact"
            glassPopover
            placeholder={t("referrals.list.rewardTypeAll")}
            options={[
              { value: "", label: t("referrals.list.rewardTypeAll"), icon: Coins },
              ...REWARD_TYPES.map((type) => ({
                value: type,
                label: t(`referrals.settings.rewardType.${type}`),
                icon: REWARD_TYPE_ICONS[type],
              })),
            ]}
          />
        </div>
        <div className="w-40 min-w-0">
          <SelectDropdown
            id="referrals-period"
            value={String(period)}
            onChange={(value) => setPeriod(Number(value) as PeriodDays)}
            icon={CalendarRange}
            size="compact"
            glassPopover
            placeholder={t("dashboard.periodAll")}
            options={PERIODS.map((days) => ({
              value: String(days),
              label: days === 0 ? t("dashboard.periodAll") : t("dashboard.periodDays", { count: days }),
              icon: CalendarRange,
            }))}
          />
        </div>
      </div>

      <div className="scroll-fade-y scroll-fade-gap page-scroll mt-1 flex flex-col gap-5 pt-2 md:mt-0 md:min-h-0 md:flex-1 md:overflow-y-auto md:pt-[68px] md:scroll-pt-[68px] [--fade-rest-start:48px] [--fade-bottom-size:0px] [scrollbar-gutter:stable] max-md:[scrollbar-gutter:auto] max-md:[scrollbar-width:none] max-md:[&::-webkit-scrollbar]:hidden md:-mr-5 md:pb-5 md:pr-[calc(1.25rem-var(--scrollbar-size))]">
      <LoadGate>
      <LoadGateHold isLoading={state.kind === "loading" || summaryState.kind === "loading"} />
      <div className="flex flex-col gap-5">
      {canViewSummary && (
      <div className="grid shrink-0 grid-cols-2 gap-5 lg:grid-cols-4">
        <KpiTile
          panel
          icon={UserPlus}
          label={t("referrals.summary.invited")}
          value={summary ? String(summary.total_count) : none}
          trend={trend((s) => s.total_count)}
          hint={summary ? t("referrals.summary.referrers", { count: summary.referrers_count }) : undefined}
        />
        <KpiTile
          panel
          icon={Gift}
          label={t("referrals.summary.rewarded")}
          value={summary ? String(summary.rewarded_count) : none}
          trend={trend((s) => s.rewarded_count)}
          hint={
            summary
              ? `${t("referrals.summary.conversionRate")} ${formatPercent(summary.conversion_rate, i18n.language)}`
              : undefined
          }
        />
        <KpiTile
          panel
          icon={CalendarPlus}
          label={t("referrals.summary.days")}
          value={rewardTotal("EXTRA_DAYS")}
          trend={trend((s) => rewardAmount(s, "EXTRA_DAYS"))}
        />
        <KpiTile
          panel
          icon={Coins}
          label={t("referrals.summary.points")}
          value={rewardTotal("POINTS")}
          trend={trend((s) => rewardAmount(s, "POINTS"))}
        />
      </div>
      )}

      <div className="glass-panel relative shrink-0 rounded-3xl p-4">
        {state.kind === "ready" && isFetching && <RefetchSpinner />}
        <AnimatedHeight>
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <ErrorState text={permissions.includes("REFERRALS_LIST") ? t("common.loadError") : t("referrals.list.noPermission")} size="page" />
        )}
        {state.kind === "ready" && state.items.length === 0 && (
          <EmptyState text={t("referrals.list.empty")} size="page" />
        )}
        {state.kind === "ready" && state.items.length > 0 && (
          <>
            <div
              className={`${ROW_GRID_CLASSNAME} ${GLASS_LIST_HEAD_CLASS}`}
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
                    <GroupToggle
                      glass
                      open={!collapsedDays.has(group.key)}
                      onToggle={() => toggleDay(group.key)}
                      label={formatDayLabel(group.date, t, i18n.language)}
                      count={group.items.length}
                    />
                  </h3>
                  <Collapse open={!collapsedDays.has(group.key)} className={`${LIST_BODY_CLASS}`}>
                    {group.items.map((item) => {
                      const referred = item.referred;
                      const canOpen = canViewStats && referred !== null;
                      const rewards = formatRewards(item);
                      return (
                        <ListRow
                          glass
                          key={item.id}
                          type="button"
                          disabled={!canOpen}
                          onClick={() => setStatsUser(referred)}
                          className={ROW_GRID_CLASSNAME}
                        >
                          <span
                            className="flex size-8 items-center justify-center rounded-full bg-white/[0.06] text-[11px] font-bold text-foreground"
                          >
                            {initials(referred?.name)}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-[13px] font-medium text-foreground">
                              {referred?.name || t("users.deleted.name")}
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
                              className="flex size-6 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[11px] font-bold text-foreground"
                            >
                              {initials(item.referrer?.name)}
                            </span>
                            <span className="truncate text-[13px] text-foreground">
                              {item.referrer?.name || t("users.deleted.name")}
                            </span>
                          </span>
                          <span>
                            <Badge borderless tone={LEVEL_BADGE_TONE[item.level] ?? "neutral"}>
                              {t("referrals.list.levelBadge", { level: item.level })}
                            </Badge>
                          </span>
                          <span className="min-w-0 tabular-nums">
                            <span
                              className={`block truncate text-[13px] ${
                                rewards ? "font-semibold text-foreground" : "font-medium text-muted-foreground"
                              }`}
                            >
                              {rewards ?? "—"}
                            </span>
                            <span className="block truncate text-[12px] text-muted-foreground">
                              {item.reward_count
                                ? t("referrals.list.rewardCount", { count: item.reward_count })
                                : t("referrals.list.noRewards")}
                            </span>
                          </span>
                          <span className="text-[13px] tabular-nums text-foreground">
                            {formatTime(item.created_at, i18n.language)}
                          </span>
                          {canOpen ? <ChevronRight className="size-4 text-muted-foreground" /> : <span />}
                        </ListRow>
                      );
                    })}
                  </Collapse>
                </section>
              ))}
            </div>
            {state.kind === "ready" && hasMore && (
              <div className="mx-3 mt-4">
                <LoadMoreButton
                  onClick={() => void handleLoadMore()}
                  isLoading={isLoadingMore}
                  shown={state.items.length}
                  total={state.total}
                />
              </div>
            )}
          </>
        )}
        </AnimatedHeight>
      </div>
      </div>
      </LoadGate>
      </div>

      {statsUser && (
        <UserReferralsDialog
          userId={statsUser.id}
          userName={statsUser.name}
          username={statsUser.username}
          onClose={() => setStatsUser(null)}
        />
      )}
    </div>
  );
}
