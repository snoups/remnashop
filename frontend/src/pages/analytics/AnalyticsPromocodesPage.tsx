import type { ParseKeys } from "i18next";
import { Gift, Percent, Receipt, Repeat, Ticket, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getPromocodeStats } from "@entities/analytics/api";
import type { PromocodeRow, PromocodeStats } from "@entities/analytics/api";
import { PROMOCODE_STATUS_BADGE_TONE } from "@entities/promocodes/display";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { LIST_HEAD_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { AnalyticsToolbar } from "@pages/analytics/AnalyticsToolbar";
import { BarRows, CurrencyNote } from "@pages/analytics/charts";
import type { BarRow } from "@pages/analytics/charts";
import { useAnalyticsPeriod } from "@pages/analytics/period";
import { ListRow } from "@shared/ui/ListRow";

const TABLE_GRID =
  "grid grid-cols-[minmax(120px,1fr)_120px_210px_100px_84px_84px] items-center gap-3";

export function AnalyticsPromocodesPage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  const [state] = useAsyncResource(
    (signal) => getPromocodeStats(period, signal),
    { deps: [period], keepData: true },
  );

  return (
    <div className="flex flex-col gap-4 pb-2">
      <AnalyticsToolbar
        currency={
          state.kind === "ready" ? state.data.report_currency : undefined
        }
      />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && <Overview data={state.data} />}
    </div>
  );
}

function Overview({ data }: { data: PromocodeStats }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const currency = data.report_currency;
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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KpiTile
          highlighted
          icon={Ticket}
          label={t("analytics.promocodes.activations")}
          value={data.activations.toLocaleString(language)}
          hint={t("analytics.promocodes.codesUsed", {
            count: data.codes_used,
            formatted: data.codes_used.toLocaleString(language),
          })}
        />
        <KpiTile
          icon={Percent}
          label={t("analytics.promocodes.discounts")}
          info={t("analytics.promocodes.discountsInfo")}
          value={formatMoney(data.discount_given, currency, language)}
          hint={
            discountShare === null
              ? undefined
              : t("analytics.promocodes.discountsCaption", {
                  share: formatPercent(discountShare, language),
                })
          }
        />
        <KpiTile
          icon={Wallet}
          label={t("analytics.promocodes.revenue")}
          value={formatMoney(data.revenue_with_discount, currency, language)}
          hint={t("analytics.promocodes.revenueCaption", {
            share: formatPercent(data.revenue_share, language),
          })}
        />
        <KpiTile
          icon={Repeat}
          label={t("analytics.promocodes.conversion")}
          value={formatPercent(data.free_reward_conversion, language)}
          hint={t("analytics.promocodes.conversionCaption")}
        />
      </div>

      <div className="grid grid-cols-1 items-start gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        <Card>
          <CardHeader
            icon={Gift}
            title={t("analytics.promocodes.byTypeTitle")}
            description={t("analytics.promocodes.byTypeDescription")}
          />
          <BarRows rows={typeRows} empty={t("analytics.promocodes.empty")} />
        </Card>

        <Card>
          <CardHeader
            icon={Receipt}
            title={t("analytics.promocodes.codesTitle")}
            description={t("analytics.promocodes.codesDescription")}
          />
          {data.codes.length === 0 ? (
            <p className="py-6 text-center text-[13px] text-muted-foreground">
              {t("analytics.promocodes.empty")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <div className="min-w-[740px]">
                <div className={`${TABLE_GRID} ${LIST_HEAD_CLASS} pt-3`}>
                  <span>{t("analytics.promocodes.code")}</span>
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
                  const max = row.max_activations;
                  return (
                    <ListRow
                      key={row.promocode_id}
                      type="button"
                      onClick={() => openPromocode(row.promocode_id)}
                      className={TABLE_GRID}
                    >
                      <span className="truncate font-mono text-[12px] text-muted-foreground">
                        {row.code}
                      </span>
                      <span>
                        <Tag>{rewardLabel(row)}</Tag>
                      </span>
                      <span className="flex items-center gap-2">
                        <span className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                          {max !== null && max > 0 && (
                            <span
                              className="block h-full rounded-full bg-primary"
                              style={{
                                width: `${Math.min(row.total_activations / max, 1) * 100}%`,
                              }}
                            />
                          )}
                        </span>
                        <span className="w-24 text-right text-[12px] tabular-nums text-muted-foreground">
                          {max === null
                            ? t("analytics.promocodes.activationsCaption", {
                                activations:
                                  row.activations.toLocaleString(language),
                                total:
                                  row.total_activations.toLocaleString(language),
                              })
                            : t("analytics.promocodes.activationsLimitCaption", {
                                activations:
                                  row.activations.toLocaleString(language),
                                total:
                                  row.total_activations.toLocaleString(language),
                                max: max.toLocaleString(language),
                              })}
                        </span>
                      </span>
                      <span className="text-right text-[13px] font-semibold tabular-nums">
                        {formatMoney(row.revenue_after, currency, language)}
                      </span>
                      <span className="text-right text-[13px] font-semibold tabular-nums">
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
        </Card>
      </div>

      <CurrencyNote currency={currency} />
    </>
  );
}
