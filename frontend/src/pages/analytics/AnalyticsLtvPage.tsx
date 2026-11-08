import { BarChart3, Link2, Package, Trophy, User, Users, Wallet } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getLtvBreakdown, getLtvDistribution } from "@entities/analytics/api";
import type { LtvBreakdown, LtvDistribution, LtvGroup } from "@entities/analytics/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { initials } from "@shared/lib/initials";
import { formatDate } from "@shared/lib/relative-time";
import { LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Section } from "@shared/ui/glass/Section";
import { LIST_BODY_CLASS, GLASS_LIST_HEAD_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { Spinner } from "@shared/ui/Spinner";
import { BarRows, ColumnChart } from "@pages/analytics/charts";
import type { BarRow, Column } from "@pages/analytics/charts";
import { ListRow } from "@shared/ui/ListRow";
import { Tag } from "@shared/ui/Tag";

const TOP_GRID = "grid grid-cols-[32px_minmax(0,1.4fr)_minmax(0,1fr)_80px_120px_140px] items-center gap-3";

export function AnalyticsLtvPage() {
  const { t } = useTranslation();
  const canBreakdown = usePermissions().includes("ANALYTICS_LTV_BREAKDOWN_VIEW");
  const [state] = useAsyncResource((signal) => getLtvDistribution(signal));
  const [breakdown] = useAsyncResource((signal) => (canBreakdown ? getLtvBreakdown(signal) : Promise.resolve(null)), {
    deps: [canBreakdown],
  });

  return (
    <div className="flex flex-col gap-5">
      <LoadGateHold isLoading={state.kind === "loading" || breakdown.kind === "loading"} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
      {state.kind === "ready" && (
        <>
          <Distribution data={state.data} />
          {breakdown.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
          {breakdown.kind === "ready" && breakdown.data && <Breakdown data={breakdown.data} />}
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
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        <KpiTile
          panel
          icon={Wallet}
          label={t("analytics.ltv.mean")}
          value={data.payers > 0 ? formatMoney(data.mean, currency, language) : t("common.none")}
          hint={t("analytics.ltv.meanCaption")}
        />
        <KpiTile
          panel
          icon={BarChart3}
          label={t("analytics.ltv.median")}
          value={data.payers > 0 ? formatMoney(data.median, currency, language) : t("common.none")}
          hint={t("analytics.ltv.medianCaption")}
        />
        <KpiTile
          panel
          icon={Users}
          label={t("analytics.ltv.payers")}
          value={data.payers.toLocaleString(language)}
          hint={t("analytics.ltv.payersCaption")}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Section stretched icon={BarChart3} title={t("analytics.ltv.title")} description={t("analytics.ltv.titleHint")}>
          <div className="px-3.5 pt-4">
          <ColumnChart columns={total > 0 ? columns : []} empty={t("analytics.empty")} height={240} />
          </div>
        </Section>

        <div className="glass-panel rounded-3xl p-4">
          <div className={`${GLASS_LIST_HEAD_CLASS} grid grid-cols-[minmax(0,1fr)_72px_48px] gap-3`}>
          <span>{t("analytics.ltv.rangeColumn")}</span>
          <span className="text-right">{t("analytics.ltv.usersColumn")}</span>
          <span className="text-right">{t("analytics.ltv.shareColumn")}</span>
          </div>
          {data.buckets.map((bucket) => (
          <div key={bucket.label} className="grid grid-cols-[minmax(0,1fr)_72px_48px] items-center gap-3 px-3.5 py-2.5">
            <span className="flex min-w-0 flex-col gap-1.5">
              <span className="truncate text-[13px] font-medium tabular-nums text-foreground">
                {bucket.upper_bound === null
                  ? `≥ ${formatMoney(bucket.lower_bound, currency, language)}`
                  : `${formatMoney(bucket.lower_bound, currency, language)} – ${formatMoney(bucket.upper_bound, currency, language)}`}
              </span>
              <span className="h-1 overflow-hidden rounded-full glass-track">
                <span className="block h-full rounded-full bg-primary transition-[width] duration-200 ease-out" style={{ width: `${share(bucket.users) * 100}%` }} />
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
        </div>
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
        // a narrow card keeps the number, the word goes
        <span key="customers" className="text-[12px] text-muted-foreground">
          <span className="@[26rem]:hidden">{group.customers.toLocaleString(language)}</span>
          <span className="hidden @[26rem]:inline">{t("analytics.ltv.customers", { count: group.customers })}</span>
        </span>,
      ],
    }));

  return (
    <>
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Section
          stretched
          icon={Package}
          title={t("analytics.ltv.byPlanTitle")}
          description={t("analytics.ltv.byPlanDescription")}
        >
          <BarRows compact rows={rows(data.by_first_plan, (group) => group.key)} empty={t("analytics.empty")} />
        </Section>
        <Section
          stretched
          icon={Link2}
          title={t("analytics.ltv.bySourceTitle")}
          description={t("analytics.ltv.bySourceDescription")}
        >
          <BarRows compact rows={rows(data.by_source, sourceLabel)} empty={t("analytics.empty")} />
        </Section>
      </div>

      <Section icon={Trophy} title={t("analytics.ltv.topTitle")} description={t("analytics.ltv.topDescription")}>
        {data.top_payers.length === 0 ? (
          <EmptyState text={t("analytics.empty")} />
        ) : (
          <div className="overflow-x-auto pt-4">
            <div className="min-w-[720px]">
              <div className={`${TOP_GRID} ${GLASS_LIST_HEAD_CLASS}`}>
                <span className="col-span-2">{t("analytics.ltv.customer")}</span>
                <span>{t("analytics.ltv.subscriptionsColumn")}</span>
                <span className="text-right">{t("analytics.ltv.payments")}</span>
                <span className="text-right">{t("analytics.totalPaid")}</span>
                <span className="text-right">{t("analytics.ltv.lastPayment")}</span>
              </div>
              <div className={LIST_BODY_CLASS}>
                {data.top_payers.map((payer) => (
                  <ListRow
                    glass
                    key={payer.user_id}
                    type="button"
                    onClick={() => openUser(payer.user_id)}
                    className={TOP_GRID}
                  >
                    <span className="flex size-8 items-center justify-center rounded-full bg-white/[0.06] text-[11px] font-bold text-foreground">
                      {payer.name ? initials(payer.name) : <User className="size-4" />}
                    </span>
                    <span className="min-w-0">
                      <span className="flex min-w-0 items-center gap-2">
                        <span className="truncate text-[13px] font-medium text-foreground">
                          {payer.name || t("users.unnamed")}
                        </span>
                        <span className="shrink-0 font-mono text-[12px] text-muted-foreground">#{payer.user_id}</span>
                      </span>
                      {payer.username && (
                        <span className="block truncate font-mono text-[12px] text-muted-foreground">@{payer.username}</span>
                      )}
                    </span>
                    <span className="flex min-w-0 items-center gap-1.5 text-[13px] text-foreground">
                      <span className="truncate">{payer.current_plans[0] ?? t("common.none")}</span>
                      {payer.current_plans.length > 1 && <Tag>+{payer.current_plans.length - 1}</Tag>}
                    </span>
                    <span className="text-right text-[12px] tabular-nums text-muted-foreground">
                      {payer.payments.toLocaleString(language)}
                    </span>
                    <span className="text-right text-[13px] font-semibold tabular-nums text-foreground">
                      {formatMoney(payer.spent, currency, language)}
                    </span>
                    <span className="text-right text-[12px] tabular-nums text-muted-foreground">
                      {formatDate(payer.last_paid_at, language)}
                    </span>
                  </ListRow>
                ))}
              </div>
            </div>
          </div>
        )}
      </Section>
    </>
  );
}
