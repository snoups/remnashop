import { BarChart3, Link2, Package, Trophy, Users, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getLtvBreakdown, getLtvDistribution } from "@entities/analytics/api";
import type { LtvBreakdown, LtvDistribution, LtvGroup } from "@entities/analytics/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { formatDate } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { LIST_BODY_CLASS, LIST_HEAD_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { AnalyticsToolbar } from "@pages/analytics/AnalyticsToolbar";
import { BarRows, ColumnChart, CurrencyNote } from "@pages/analytics/charts";
import type { BarRow, Column } from "@pages/analytics/charts";

const RANK_CLASS = ["bg-warning/15 text-warning", "bg-white/[0.08] text-foreground", "bg-orange-400/15 text-orange-300"];
const TOP_GRID = "grid grid-cols-[36px_minmax(0,1.4fr)_minmax(0,1fr)_80px_110px_110px] items-center gap-3";

export function AnalyticsLtvPage() {
  const { t } = useTranslation();
  const canBreakdown = usePermissions().includes("ANALYTICS_LTV_BREAKDOWN_VIEW");
  const [state] = useAsyncResource((signal) => getLtvDistribution(signal));
  const [breakdown] = useAsyncResource((signal) => (canBreakdown ? getLtvBreakdown(signal) : Promise.resolve(null)), {
    deps: [canBreakdown],
  });

  return (
    <div className="flex flex-col gap-4 pb-2">
      <AnalyticsToolbar
        periodIndependent
        tag={
          state.kind === "ready" ? (
            <Tag>{t("analytics.ltv.allTime", { currency: state.data.report_currency })}</Tag>
          ) : (
            <span />
          )
        }
      />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("analytics.loadError")} />}
      {state.kind === "ready" && (
        <>
          <Distribution data={state.data} />
          {breakdown.kind === "error" && <ErrorState text={t("analytics.loadError")} />}
          {breakdown.kind === "ready" && breakdown.data && <Breakdown data={breakdown.data} />}
          <CurrencyNote currency={state.data.report_currency} />
        </>
      )}
    </div>
  );
}

function Distribution({ data }: { data: LtvDistribution }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const currency = data.report_currency;
  const total = data.buckets.reduce((sum, bucket) => sum + bucket.users, 0);
  const share = (users: number) => (total > 0 ? users / total : 0);

  const columns: Column[] = data.buckets.map((bucket) => ({
    key: bucket.label,
    label: bucket.label,
    segments: [{ value: bucket.users, className: "bg-primary" }],
    caption: bucket.users.toLocaleString(language),
  }));

  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiTile
          highlighted
          icon={Wallet}
          label={t("analytics.ltv.mean")}
          value={formatMoney(data.mean, currency, language)}
          hint={t("analytics.ltv.meanCaption")}
        />
        <KpiTile
          icon={BarChart3}
          label={t("analytics.ltv.median")}
          value={formatMoney(data.median, currency, language)}
          hint={t("analytics.ltv.medianCaption")}
        />
        <KpiTile
          icon={Users}
          label={t("analytics.ltv.payers")}
          value={data.payers.toLocaleString(language)}
          hint={t("analytics.ltv.payersCaption")}
        />
      </div>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Card>
          <CardHeader icon={BarChart3} title={t("analytics.ltv.title")} description={t("analytics.ltv.titleHint")} />
          <div className="pt-4">
            <ColumnChart columns={total > 0 ? columns : []} empty={t("analytics.empty")} height={240} />
          </div>
        </Card>

        <Card variant="list">
          <div className={`${LIST_HEAD_CLASS} grid grid-cols-[minmax(0,1fr)_72px_48px] gap-3 pt-2.5`}>
            <span>{t("analytics.ltv.rangeColumn")}</span>
            <span className="text-right">{t("analytics.ltv.usersColumn")}</span>
            <span className="text-right">{t("analytics.ltv.shareColumn")}</span>
          </div>
          {data.buckets.map((bucket) => (
            <div key={bucket.label} className="grid grid-cols-[minmax(0,1fr)_72px_48px] items-center gap-3 px-3 py-2.5">
              <span className="flex min-w-0 flex-col gap-1.5">
                <span className="truncate text-[13px] font-medium tabular-nums text-foreground">
                  {bucket.upper_bound === null
                    ? `≥ ${formatMoney(bucket.lower_bound, currency, language)}`
                    : `${formatMoney(bucket.lower_bound, currency, language)} – ${formatMoney(bucket.upper_bound, currency, language)}`}
                </span>
                <span className="h-1 overflow-hidden rounded-full bg-white/[0.06]">
                  <span className="block h-full rounded-full bg-primary" style={{ width: `${share(bucket.users) * 100}%` }} />
                </span>
              </span>
              <span className="text-right text-[13px] font-semibold tabular-nums text-foreground">
                {bucket.users.toLocaleString(language)}
              </span>
              <span className="text-right text-[12px] tabular-nums text-muted-foreground">
                {formatPercent(share(bucket.users), language)}
              </span>
            </div>
          ))}
        </Card>
      </div>
    </>
  );
}

function Breakdown({ data }: { data: LtvBreakdown }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const currency = data.report_currency;
  const { openUser } = useOpenEntity();

  const sourceLabel = (group: LtvGroup) =>
    group.source === "organic"
      ? t("analytics.sources.organic")
      : group.source === "referral"
        ? t("analytics.sources.referral")
        : group.key;
  const rows = (groups: LtvGroup[], label: (group: LtvGroup) => string): BarRow[] =>
    groups.map((group, index) => ({
      key: `${group.key}:${index}`,
      label: label(group),
      value: Number(group.avg_ltv),
      cells: [
        formatMoney(group.avg_ltv, currency, language),
        <span key="customers" className="text-[12px] text-muted-foreground">
          {t("analytics.ltv.customers", { count: group.customers })}
        </span>,
      ],
    }));

  return (
    <>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader
            icon={Package}
            title={t("analytics.ltv.byPlanTitle")}
            description={t("analytics.ltv.byPlanDescription")}
          />
          <BarRows rows={rows(data.by_first_plan, (group) => group.key)} empty={t("analytics.empty")} />
        </Card>
        <Card>
          <CardHeader
            icon={Link2}
            title={t("analytics.ltv.bySourceTitle")}
            description={t("analytics.ltv.bySourceDescription")}
          />
          <BarRows rows={rows(data.by_source, sourceLabel)} empty={t("analytics.empty")} />
        </Card>
      </div>

      <Card>
        <CardHeader icon={Trophy} title={t("analytics.ltv.topTitle")} description={t("analytics.ltv.topDescription")} />
        {data.top_payers.length === 0 ? (
          <p className="py-6 text-center text-[13px] text-muted-foreground">{t("analytics.empty")}</p>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[720px]">
              <div className={`${TOP_GRID} ${LIST_HEAD_CLASS}`}>
                <span>#</span>
                <span>{t("analytics.ltv.customer")}</span>
                <span>{t("analytics.ltv.currentPlan")}</span>
                <span className="text-right">{t("analytics.ltv.payments")}</span>
                <span className="text-right">{t("analytics.totalPaid")}</span>
                <span className="text-right">{t("analytics.ltv.lastPayment")}</span>
              </div>
              <div className={LIST_BODY_CLASS}>
                {data.top_payers.map((payer, index) => (
                  <button
                    key={payer.user_id}
                    type="button"
                    onClick={() => openUser(payer.user_id)}
                    className={`${TOP_GRID} w-full ${LIST_ROW_CLASS} text-left hover:bg-white/[0.04]`}
                  >
                    <span
                      className={`flex size-9 items-center justify-center rounded-full text-[12px] font-bold ${
                        RANK_CLASS[index] ?? "bg-white/[0.04] text-muted-foreground"
                      }`}
                    >
                      {index + 1}
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate text-[13.5px] font-medium text-foreground">{payer.name}</span>
                      {payer.username && (
                        <span className="block truncate font-mono text-[12px] text-muted-foreground">@{payer.username}</span>
                      )}
                    </span>
                    <span className="truncate text-[13px] text-foreground">{payer.current_plan ?? t("common.none")}</span>
                    <span className="text-right text-[12.5px] tabular-nums text-muted-foreground">
                      {payer.payments.toLocaleString(language)}
                    </span>
                    <span className="text-right text-[13px] font-semibold tabular-nums text-foreground">
                      {formatMoney(payer.spent, currency, language)}
                    </span>
                    <span className="text-right text-[12.5px] tabular-nums text-muted-foreground">
                      {formatDate(payer.last_paid_at, language)}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </Card>
    </>
  );
}
