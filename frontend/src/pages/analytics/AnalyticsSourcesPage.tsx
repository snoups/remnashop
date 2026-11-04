import type { ParseKeys } from "i18next";
import { ChevronRight, Link2, Share2, Trophy } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { getSources } from "@entities/analytics/api";
import type { SourceKind, SourceRow, Sources } from "@entities/analytics/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatMoney, formatPercent } from "@shared/lib/format";
import { initials } from "@shared/lib/initials";
import { LoadGateHold } from "@shared/lib/load-gate";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Section } from "@shared/ui/glass/Section";
import {
  EYEBROW_CLASS,
  GLASS_LIST_HEAD_CLASS,
  GLASS_LIST_ROW_CLASS,
} from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { PillTabs } from "@shared/ui/PillTabs";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { Legend } from "@pages/analytics/charts";
import { useAnalyticsPeriod } from "@pages/analytics/period";
import { previousPeriodHint, relativeTrend } from "@pages/analytics/trends";
import { ListRow } from "@shared/ui/ListRow";

const KINDS: SourceKind[] = ["organic", "ad_link", "referral"];
const KIND_KEY = {
  organic: "organic",
  ad_link: "adLink",
  referral: "referral",
} as const;
const KIND_BG = {
  organic: "bg-success",
  ad_link: "bg-primary",
  referral: "bg-violet-400",
} as const;
const KIND_IC = {
  organic: "bg-success/10 text-success",
  ad_link: "bg-primary/10 text-primary",
  referral: "bg-violet-400/10 text-violet-300",
} as const;
const TABLE_GRID =
  "grid grid-cols-[32px_minmax(180px,1fr)_100px_90px_170px_120px_90px] items-center gap-3";

type ReferrerSort = "revenue" | "invited";

export function AnalyticsSourcesPage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  const [state] = useAsyncResource((signal) => getSources(period, signal), {
    deps: [period],
    keepData: true,
  });

  return (
    <div className="flex flex-col gap-5">
      <LoadGateHold isLoading={state.kind === "loading"} />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} size="page" />}
      {state.kind === "ready" && <Overview data={state.data} />}
    </div>
  );
}

function Overview({ data }: { data: Sources }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const currency = data.report_currency;
  const { period } = useAnalyticsPeriod();
  const vs = previousPeriodHint(period, t);
  const previousRevenue = (kind: SourceKind) =>
    Number(data.previous_channels.find((row) => row.source === kind)?.revenue ?? 0);
  const navigate = useNavigate();
  const canAdLinks = usePermissions().includes("AD_LINKS_VIEW");

  const channel = (kind: SourceKind) =>
    data.channels.find((row) => row.source === kind);
  const totalRevenue = data.channels.reduce(
    (sum, row) => sum + Number(row.revenue),
    0,
  );
  const share = (row: SourceRow | undefined) =>
    row && totalRevenue > 0 ? Number(row.revenue) / totalRevenue : 0;
  const kindLabel = (kind: SourceKind) =>
    t(`analytics.sources.${KIND_KEY[kind]}`);
  const maxConversion = Math.max(
    0,
    ...data.channels.concat(data.ad_links).map((row) => row.conversion_rate),
  );

  const tableRows: { row: SourceRow; top: boolean; key: string }[] = [];
  for (const kind of KINDS) {
    const row = channel(kind);
    if (!row) continue;
    tableRows.push({ row, top: true, key: kind });
    if (kind === "ad_link") {
      for (const link of data.ad_links)
        tableRows.push({
          row: link,
          top: false,
          key: `link:${link.ad_link_id}`,
        });
    }
  }

  return (
    <>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-3">
        {KINDS.map((kind) => {
          const row = channel(kind);
          const parts = [
            t("analytics.sources.tileCaption", {
              share: formatPercent(share(row), language),
              count: row?.registrations ?? 0,
              formatted: (row?.registrations ?? 0).toLocaleString(language),
            }),
          ];
          if (kind === "ad_link") {
            parts.push(
              t("analytics.sources.linksCount", {
                count: data.ad_links.length,
                formatted: data.ad_links.length.toLocaleString(language),
              }),
            );
          }
          return (
            <KpiTile
              panel
              key={kind}
              icon={Link2}
              label={kindLabel(kind)}
              value={formatMoney(row?.revenue ?? "0", currency, language)}
              trend={
                period.kind === "all" ? undefined : relativeTrend(Number(row?.revenue ?? 0), previousRevenue(kind), vs, language)
              }
              hint={parts.join(" · ")}
            />
          );
        })}
      </div>

      <Section
        icon={Link2}
        title={t("analytics.sources.channelsTitle")}
        description={t("analytics.sources.channelsDescription")}
        aside={
          canAdLinks && (
            <Button
              variant="glass"
              type="button"
              onClick={() => navigate("/dashboard/advertising")}
            >
              {t("analytics.sources.openAdvertising")}
              <ChevronRight className="size-4" />
            </Button>
          )
        }
      >
        <div className="flex flex-col gap-2 px-3.5 py-4">
          <div className="flex h-3 gap-[3px]">
            {KINDS.map((kind) => (
              <div
                key={kind}
                className={`rounded-full transition-[width] duration-200 ease-out ${KIND_BG[kind]}`}
                style={{ width: `${share(channel(kind)) * 100}%` }}
              />
            ))}
          </div>
          <Legend
            items={KINDS.map((kind) => ({
              className: KIND_BG[kind],
              label: `${kindLabel(kind)} · ${formatPercent(share(channel(kind)), language)}`,
            }))}
          />
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[820px]">
            <div className={`${TABLE_GRID} ${GLASS_LIST_HEAD_CLASS}`}>
              <span />
              <span>{t("analytics.sources.channel")}</span>
              <span className="text-right">
                {t("analytics.sources.registrations")}
              </span>
              <span className="text-right">{t("analytics.sources.paid")}</span>
              <span className="pl-6">{t("analytics.sources.conversion")}</span>
              <span className="text-right">
                {t("analytics.sources.revenue")}
              </span>
              <span className="text-right">
                {t("analytics.metrics.arppu")}
              </span>
            </div>
            {tableRows.map(({ row, top, key }) => (
              <div
                key={key}
                className={`${TABLE_GRID} ${GLASS_LIST_ROW_CLASS} ${top ? "" : "!h-12"}`}
              >
                <span>
                  {top && (
                    <span
                      className={`flex size-8 items-center justify-center rounded-full text-[11px] font-bold ${KIND_IC[row.source]}`}
                    >
                      {kindLabel(row.source).charAt(0).toUpperCase()}
                    </span>
                  )}
                </span>
                <span
                  className={`min-w-0 ${top ? "" : "border-l-2 border-border pl-4"}`}
                >
                  <span className="block truncate text-[13px] font-medium text-foreground">
                    {top
                      ? kindLabel(row.source)
                      : (row.name ?? `#${row.ad_link_id}`)}
                  </span>
                  {!top && row.name && (
                    <span className="block truncate font-mono text-[12px] text-muted-foreground">
                      #{row.ad_link_id}
                    </span>
                  )}
                </span>
                <span className="text-right text-[13px] font-semibold tabular-nums">
                  {row.registrations.toLocaleString(language)}
                </span>
                <span className="text-right text-[13px] font-semibold tabular-nums">
                  {row.payers.toLocaleString(language)}
                </span>
                <span className="flex items-center gap-2 pl-6">
                  <span className="h-2 flex-1 overflow-hidden rounded-full glass-track">
                    <span
                      className={`block h-full rounded-full transition-[width] duration-200 ease-out ${KIND_BG[row.source]}`}
                      style={{
                        width: `${maxConversion > 0 ? (row.conversion_rate / maxConversion) * 100 : 0}%`,
                      }}
                    />
                  </span>
                  <span className="w-11 text-right text-[12px] tabular-nums text-muted-foreground">
                    {formatPercent(row.conversion_rate, language)}
                  </span>
                </span>
                <span className="text-right text-[13px] font-semibold tabular-nums">
                  {formatMoney(row.revenue, currency, language)}
                </span>
                <span className="text-right text-[12px] tabular-nums text-muted-foreground">
                  {formatMoney(row.revenue_per_payer, currency, language)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Section>

      <Payback data={data} />
      <TopReferrers data={data} />

    </>
  );
}

function Payback({ data }: { data: Sources }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { referral } = data;

  return (
    <Section
      icon={Share2}
      title={t("analytics.sources.paybackTitle")}
      description={t("analytics.sources.paybackDescription")}
    >
      <div className="flex flex-col gap-4 px-3.5 pt-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between gap-3">
            <span className={EYEBROW_CLASS}>
              {t("analytics.sources.referredRevenue")}
            </span>
            <span className="text-[13px] font-semibold tabular-nums">
              {formatMoney(
                referral.referred_revenue,
                data.report_currency,
                language,
              )}
            </span>
          </div>
          <div className="h-3 rounded-full bg-violet-400" />
        </div>
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center justify-between gap-x-3">
            <span className={EYEBROW_CLASS}>
              {t("analytics.sources.rewards")}
            </span>
            <span className="text-[13px] font-semibold tabular-nums">
              {[
                t("analytics.sources.rewardsDays", {
                  count: referral.reward_days,
                  formatted: referral.reward_days.toLocaleString(language),
                }),
                t("analytics.sources.rewardsPoints", {
                  count: referral.reward_points,
                  formatted: referral.reward_points.toLocaleString(language),
                }),
              ].join(" · ")}
            </span>
          </div>
          <div className="h-3 rounded-full bg-warning" />
        </div>
        <div className="flex flex-wrap gap-2">
          <Tag>
            {t("analytics.sources.referrers", {
              count: referral.referrers,
              formatted: referral.referrers.toLocaleString(language),
            })}
          </Tag>
          <Tag>
            {t("analytics.sources.deepLevels", {
              share: formatPercent(
                referral.deep_levels_revenue_share,
                language,
              ),
            })}
          </Tag>
        </div>
      </div>
    </Section>
  );
}

function TopReferrers({ data }: { data: Sources }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { openUser } = useOpenEntity();
  const [sort, setSort] = useState<ReferrerSort>("revenue");

  const rows = [...data.top_referrers].sort((a, b) =>
    sort === "revenue"
      ? Number(b.revenue) - Number(a.revenue)
      : b.invited - a.invited,
  );

  return (
    <Section
      icon={Trophy}
      title={t("analytics.sources.topTitle")}
      description={t("analytics.sources.topDescription")}
      aside={
        <PillTabs
          activeKey={sort}
          onSelect={setSort}
          items={(["revenue", "invited"] as const).map((key) => ({
            key,
            label: t(`analytics.sources.sort.${key}` as ParseKeys),
          }))}
        />
      }
    >
      {rows.length === 0 ? (
        <EmptyState text={t("analytics.sources.empty")} />
      ) : (
        <div className="mt-4 flex flex-col">
        {rows.map((row) => (
          <ListRow
            glass
            key={row.user_id}
            type="button"
            onClick={() => openUser(row.user_id)}
            className={`grid grid-cols-[32px_minmax(0,1fr)_auto_auto] items-center gap-3`}
          >
            <span className="flex size-8 items-center justify-center rounded-full bg-violet-400/10 text-[11px] font-bold text-violet-300">
              {initials(row.name)}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-[13px] font-medium text-foreground">
                {row.name}
              </span>
              <span className="block truncate text-[12px] tabular-nums text-muted-foreground">
                {t("analytics.sources.invitedPaid", {
                  invited: row.invited.toLocaleString(language),
                  paid: row.paid.toLocaleString(language),
                })}
              </span>
            </span>
            <span className="text-right text-[13px] font-semibold tabular-nums">
              {formatMoney(row.revenue, data.report_currency, language)}
            </span>
            <span className="w-16 text-right text-[12px] tabular-nums text-muted-foreground">
              {t("plans.daysShort", { count: row.reward_days })}
            </span>
          </ListRow>
        ))}
        </div>
      )}
    </Section>
  );
}
