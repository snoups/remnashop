import type { ParseKeys } from "i18next";
import { Gift, Percent, Receipt, Repeat, Ticket, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getPromocodeStats } from "@entities/analytics/api";
import type { PromocodeRow, PromocodeStats } from "@entities/analytics/api";
import { PROMOCODE_STATUS_BADGE_TONE } from "@entities/promocodes/display";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Section } from "@shared/ui/glass/Section";
import { GLASS_LIST_HEAD_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { BarRows } from "@pages/analytics/charts";
import type { BarRow } from "@pages/analytics/charts";
import { useAnalyticsPeriod } from "@pages/analytics/period";
import { countTrend, ppTrend, previousPeriodHint, relativeTrend } from "@pages/analytics/trends";
import { ListRow } from "@shared/ui/ListRow";

const TABLE_GRID =
  "grid grid-cols-[32px_minmax(120px,1fr)_120px_120px_120px_104px_84px] items-center gap-3";

export function AnalyticsPromocodesPage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  const [state] = useAsyncResource(
    (signal) => getPromocodeStats(period, signal),
    { deps: [period], keepData: true },
  );

  return (
    <div className="flex flex-col gap-5">
      <LoadGateHold isLoading={state.kind === "loading"} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
      {state.kind === "ready" && <Overview data={state.data} />}
    </div>
  );
}

function Overview({ data }: { data: PromocodeStats }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const currency = data.report_currency;
  const { period } = useAnalyticsPeriod();
  const isAll = period.kind === "all";
  const vs = previousPeriodHint(period, t);
  const { openPromocode } = useOpenEntity();

  const withDiscount = Number(data.revenue_with_discount);
  const discountShare =
    withDiscount > 0
      ? (Number(data.discount_given) * data.revenue_share) / withDiscount
      : null;

  const rewardLabel = (row: PromocodeRow) => {
    if (row.reward_type === "DURATION")
      return `+${t("plans.daysShort", { count: row.reward ?? 0 })}`;
    if (
      row.reward_type === "PERSONAL_DISCOUNT" ||
      row.reward_type === "PURCHASE_DISCOUNT"
    )
      return `-${row.reward ?? 0}%`;
    if (row.reward_type === "SUBSCRIPTION" && row.reward_duration_days !== null)
      return `${t("promocodes.rewardTypeShort.SUBSCRIPTION")} · ${t("plans.daysShort", { count: row.reward_duration_days })}`;
    return t(`promocodes.rewardTypeShort.${row.reward_type}`);
  };

  const typeRows: BarRow[] = data.by_reward_type.map((item) => ({
    key: item.reward_type,
    label: t(`promocodes.rewardType.${item.reward_type}`),
    value: item.activations,
    cells: [item.activations.toLocaleString(language)],
  }));

  return (
    <>
      <div className="grid grid-cols-2 gap-5 xl:grid-cols-4">
        <KpiTile
          panel
          icon={Ticket}
          label={t("analytics.promocodes.activations")}
          value={data.activations.toLocaleString(language)}
          trend={isAll ? undefined : countTrend(data.activations, data.previous_activations, vs, language)}
          hint={t("analytics.promocodes.codesUsed", {
            count: data.codes_used,
            formatted: data.codes_used.toLocaleString(language),
          })}
        />
        <KpiTile
          panel
          icon={Percent}
          label={t("analytics.promocodes.discounts")}
          info={t("analytics.promocodes.discountsInfo")}
          value={formatMoney(data.discount_given, currency, language)}
          trend={isAll ? undefined : relativeTrend(Number(data.discount_given), Number(data.previous_discount_given), vs, language)}
          hint={
            discountShare === null
              ? undefined
              : t("analytics.promocodes.discountsCaption", {
                  share: formatPercent(discountShare, language),
                })
          }
        />
        <KpiTile
          panel
          icon={Wallet}
          label={t("analytics.promocodes.revenue")}
          value={formatMoney(data.revenue_with_discount, currency, language)}
          trend={
            isAll
              ? undefined
              : relativeTrend(Number(data.revenue_with_discount), Number(data.previous_revenue_with_discount), vs, language)
          }
          hint={t("analytics.promocodes.revenueCaption", {
            share: formatPercent(data.revenue_share, language),
          })}
        />
        <KpiTile
          panel
          icon={Repeat}
          label={t("analytics.promocodes.conversion")}
          value={data.free_rewards > 0 ? formatPercent(data.free_reward_conversion, language) : t("common.none")}
          trend={
            isAll || data.free_rewards === 0 || data.previous_free_reward_conversion === null
              ? undefined
              : ppTrend(data.free_reward_conversion, data.previous_free_reward_conversion, vs, t, language)
          }
          hint={t("analytics.promocodes.conversionCaption")}
        />
      </div>

      <Section
        icon={Gift}
        title={t("analytics.promocodes.byTypeTitle")}
        description={t("analytics.promocodes.byTypeDescription")}
      >
        <BarRows rows={typeRows} empty={t("analytics.promocodes.empty")} />
      </Section>

      <Section
        icon={Receipt}
        title={t("analytics.promocodes.codesTitle")}
        description={t("analytics.promocodes.codesDescription")}
      >
        {data.codes.length === 0 ? (
          <EmptyState text={t("analytics.promocodes.empty")} />
        ) : (
          <div className="overflow-x-auto pt-4">
            <div className="min-w-[780px]">
              <div className={`${TABLE_GRID} ${GLASS_LIST_HEAD_CLASS}`}>
                <span className="col-span-2">{t("analytics.promocodes.code")}</span>
                <span>{t("analytics.promocodes.reward")}</span>
                <span>{t("analytics.promocodes.activationsColumn")}</span>
                <span className="text-right">
                  {t("analytics.promocodes.revenueColumn")}
                </span>
                <span className="text-right">
                  {t("analytics.promocodes.toPayment")}
                </span>
                <span className="text-right">
                  {t("promocodes.columns.status")}
                </span>
              </div>
              {data.codes.map((row) => {
                return (
                  <ListRow
                    key={row.promocode_id}
                    type="button"
                    onClick={() => openPromocode(row.promocode_id)}
                    className={TABLE_GRID}
                  >
                    <IconCircle icon={Ticket} tone={row.status === "ACTIVE" ? "success" : "neutral"} />
                    <span className="truncate font-mono text-xs text-muted-foreground">
                      {row.code}
                    </span>
                    <span>
                      <Tag>{rewardLabel(row)}</Tag>
                    </span>
                    <span className="text-sm tabular-nums text-foreground">
                      {row.total_activations.toLocaleString(language)}
                      <span className="text-muted-foreground">
                        {" / "}
                        {row.max_activations?.toLocaleString(language) ?? "∞"}
                      </span>
                    </span>
                    <span className="text-right text-sm font-semibold tabular-nums">
                      {formatMoney(row.revenue_after, currency, language)}
                    </span>
                    <span className="text-right text-sm font-semibold tabular-nums">
                      {row.conversion_rate === null
                        ? t("common.none")
                        : formatPercent(row.conversion_rate, language)}
                    </span>
                    <span className="text-right">
                      <Badge tone={PROMOCODE_STATUS_BADGE_TONE[row.status]}>
                        {t(`promocodes.status.${row.status}` as ParseKeys)}
                      </Badge>
                    </span>
                  </ListRow>
                );
              })}
            </div>
          </div>
        )}
      </Section>

    </>
  );
}
