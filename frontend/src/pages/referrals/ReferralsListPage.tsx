import { AlertCircle, ChevronRight, Coins, CornerUpLeft, Gift, Layers, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useMemo, useState } from "react";
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
import { DAY_MS, previousWindow } from "@shared/lib/period";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePaginatedList } from "@shared/lib/use-paginated-list";
import { formatPercent } from "@shared/lib/format";
import { bounceTap } from "@shared/lib/bounceState";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { useUrlSearch } from "@shared/lib/use-url-search";
import { formatDayLabel, groupByDay } from "@shared/lib/day-groups";
import { useCollapsedSet } from "@shared/lib/use-collapsed-set";
import { initials } from "@shared/lib/initials";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { Collapse } from "@shared/ui/Collapse";
import { EmptyState } from "@shared/ui/EmptyState";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { PeriodPills, type PeriodDays } from "@shared/ui/PeriodPills";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { KpiTile, type KpiTrend } from "@shared/ui/KpiTile";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";

const FILTER_DEBOUNCE_MS = 200;
const LEVELS = [1, 2, 3];
const REWARD_TYPES: ReferralRewardType[] = ["EXTRA_DAYS", "POINTS"];

const ROW_GRID_CLASSNAME =
  "grid grid-cols-[36px_minmax(0,1fr)_minmax(0,220px)_84px_130px_64px_16px] items-center gap-3";

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

  const [summaryState] = useAsyncResource((signal) => getReferralSummary(baseFilters, signal), {
    deps: [baseFilters],
    keepData: true,
  });
  const [compareState] = useAsyncResource(
    (signal) => getReferralSummary({ ...baseFilters, ...previousWindow(period) }, signal),
    { deps: [baseFilters, period] },
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

  const userHandle = (user: ReferralUser): string =>
    [
      user.username ? `@${user.username}` : null,
      user.email,
      user.telegram_id !== null ? `ID ${user.telegram_id}` : null,
    ]
      .filter(Boolean)
      .join(" · ");

  const none = t("referrals.summary.none");
  const rewardAmount = (source: ReferralSummary, type: ReferralRewardType): number =>
    Math.trunc(Number(source.reward_amounts[type] ?? 0));
  const rewardTotal = (type: ReferralRewardType): string =>
    summary ? rewardAmount(summary, type).toLocaleString(i18n.language) : none;
  const trendHint = period ? t("referrals.summary.periodTrend", { days: period }) : t("referrals.summary.totalTrend");
  const trend = (pick: (s: ReferralSummary) => number): KpiTrend | undefined =>
    summary && compareSummary ? { delta: pick(summary) - pick(compareSummary), hint: trendHint } : undefined;

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <KpiTile
          label={t("referrals.summary.invited")}
          value={summary ? String(summary.total_count) : none}
          trend={trend((s) => s.total_count)}
          hint={summary ? t("referrals.summary.referrers", { count: summary.referrers_count }) : undefined}
        />
        <KpiTile
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
          label={t("referrals.summary.days")}
          value={rewardTotal("EXTRA_DAYS")}
          trend={trend((s) => rewardAmount(s, "EXTRA_DAYS"))}
        />
        <KpiTile
          label={t("referrals.summary.points")}
          value={rewardTotal("POINTS")}
          trend={trend((s) => rewardAmount(s, "POINTS"))}
        />
      </div>

      <Card>
        <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-[repeat(3,minmax(0,1fr))_auto]">
          <div className="flex flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("referrals.list.levelFilter")}</label>
            <SelectDropdown
              id="referrals-level"
              value={level}
              onChange={setLevel}
              icon={Layers}
              placeholder={t("referrals.list.levelAll")}
              options={[
                { value: "", label: t("referrals.list.levelAll") },
                ...LEVELS.map((value) => ({
                  value: String(value),
                  label: t("referrals.list.level", { level: value }),
                })),
              ]}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("referrals.list.rewardStatusFilter")}</label>
            <SelectDropdown
              id="referrals-reward-status"
              value={rewardStatus}
              onChange={setRewardStatus}
              icon={Gift}
              placeholder={t("referrals.list.rewardStatusAll")}
              options={[
                { value: "", label: t("referrals.list.rewardStatusAll") },
                { value: "true", label: t("referrals.list.rewardStatusWith") },
                { value: "false", label: t("referrals.list.rewardStatusWithout") },
              ]}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className={EYEBROW_CLASS}>{t("referrals.list.rewardTypeFilter")}</label>
            <SelectDropdown
              id="referrals-reward-type"
              value={rewardType}
              onChange={setRewardType}
              icon={Coins}
              placeholder={t("referrals.list.rewardTypeAll")}
              options={[
                { value: "", label: t("referrals.list.rewardTypeAll") },
                ...REWARD_TYPES.map((type) => ({ value: type, label: t(`referrals.settings.rewardType.${type}`) })),
              ]}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <span className={EYEBROW_CLASS}>{t("referrals.list.periodFilter")}</span>
            <PeriodPills value={period} onChange={setPeriod} />
          </div>
          <div className="sm:col-span-2">
            <SearchField
              id="referrals-search"
              label={t("referrals.list.search")}
              placeholder={t("referrals.list.searchPlaceholder")}
              value={searchInput}
              onChange={setSearchInput}
            />
          </div>
        </div>
      </Card>

      <Card className="relative">
        {state.kind === "ready" && isFetching && (
          <Loader2 className="absolute right-4 top-4 size-3.5 animate-spin text-muted-foreground" />
        )}
        {state.kind === "loading" && <Spinner size="page" />}
        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-2 py-12 text-error">
            <AlertCircle className="size-5" />
            <p className="text-sm">
              {permissions.includes("REFERRALS_LIST") ? t("referrals.list.loadError") : t("referrals.list.noPermission")}
            </p>
          </div>
        )}
        {state.kind === "ready" && state.items.length === 0 && (
          <EmptyState text={t("referrals.list.empty")} size="page" />
        )}
        {state.kind === "ready" && state.items.length > 0 && (
          <>
            <div
              className={`${ROW_GRID_CLASSNAME} ${LIST_HEAD_CLASS}`}
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
                        <motion.button
                          key={item.id}
                          type="button"
                          disabled={!canOpen}
                          onClick={() => setStatsUser(referred)}
                          {...(canOpen && bounceTap(0.03))}
                          className={`${ROW_GRID_CLASSNAME} w-full ${LIST_ROW_CLASS} text-left enabled:hover:bg-white/[0.04] disabled:cursor-default`}
                        >
                          <span
                            className="flex size-9 items-center justify-center rounded-full bg-white/[0.06] text-[13px] font-semibold text-foreground"
                          >
                            {initials(referred?.name)}
                          </span>
                          <span className="min-w-0">
                            <span className="block truncate text-[13.5px] font-medium text-foreground">
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
                              className="flex size-6 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-[10.5px] font-semibold text-foreground"
                            >
                              {initials(item.referrer?.name)}
                            </span>
                            <span className="truncate text-[13px] text-foreground">
                              {item.referrer?.name || t("users.deleted.name")}
                            </span>
                          </span>
                          <span>
                            <Badge tone={LEVEL_BADGE_TONE[item.level] ?? "neutral"}>
                              {t("referrals.list.levelBadge", { level: item.level })}
                            </Badge>
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
      </Card>

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
