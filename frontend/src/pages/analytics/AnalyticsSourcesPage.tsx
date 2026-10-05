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
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import {
  EYEBROW_CLASS,
  LIST_HEAD_CLASS,
  LIST_ROW_CLASS,
} from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/EmptyState";
import { KpiTile } from "@shared/ui/KpiTile";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";
import { AnalyticsToolbar } from "@pages/analytics/AnalyticsToolbar";
import { CurrencyNote, Legend } from "@pages/analytics/charts";
import { useAnalyticsPeriod } from "@pages/analytics/period";

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
  "grid grid-cols-[36px_minmax(180px,1fr)_100px_90px_170px_120px_90px] items-center gap-3";

type ReferrerSort = "revenue" | "invited";

export function AnalyticsSourcesPage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  const [state] = useAsyncResource((signal) => getSources(period, signal), {
    deps: [period],
    keepData: true,
  });

  return (
    <div className="flex flex-col gap-4 pb-2">
      <AnalyticsToolbar
        currency={
          state.kind === "ready" ? state.data.report_currency : undefined
        }
      />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("analytics.loadError")} />}
      {state.kind === "ready" && <Overview data={state.data} />}
    </div>
  );
}

function Overview({ data }: { data: Sources }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const currency = data.report_currency;
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
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
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
              key={kind}
              icon={Link2}
              label={kindLabel(kind)}
              value={formatMoney(row?.revenue ?? "0", currency, language)}
              hint={parts.join(" · ")}
            />
          );
        })}
      </div>

      <Card>
        <CardHeader
          icon={Link2}
          title={t("analytics.sources.channelsTitle")}
          description={t("analytics.sources.channelsDescription")}
          aside={
            canAdLinks && (
              <Button
                variant="secondary"
                size="md"
                type="button"
                onClick={() => navigate("/dashboard/advertising")}
              >
                {t("analytics.sources.openAdvertising")}
                <ChevronRight className="size-3.5" />
              </Button>
            )
          }
        />
        <div className="flex flex-col gap-2 px-3 py-4">
          <div className="flex h-3 gap-[3px]">
            {KINDS.map((kind) => (
              <div
                key={kind}
                className={`rounded-full ${KIND_BG[kind]}`}
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
            <div className={`${TABLE_GRID} ${LIST_HEAD_CLASS}`}>
              <span />
              <span>{t("analytics.sources.channel")}</span>
              <span className="text-right">
                {t("analytics.sources.registrations")}
              </span>
              <span className="text-right">{t("analytics.sources.paid")}</span>
              <span>{t("analytics.sources.conversion")}</span>
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
                className={`${TABLE_GRID} ${LIST_ROW_CLASS} ${top ? "" : "!h-12"}`}
              >
                <span>
                  {top && (
                    <span
                      className={`flex size-9 items-center justify-center rounded-full text-[12px] font-bold ${KIND_IC[row.source]}`}
                    >
                      {kindLabel(row.source).charAt(0).toUpperCase()}
                    </span>
                  )}
                </span>
                <span
                  className={`min-w-0 ${top ? "" : "border-l-2 border-border pl-4"}`}
                >
                  <span className="block truncate text-[13.5px] font-medium text-foreground">
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
                <span className="flex items-center gap-2">
                  <span className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                    <span
                      className={`block h-full rounded-full ${KIND_BG[row.source]}`}
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
      </Card>

      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <Payback data={data} />
        <TopReferrers data={data} />
      </div>

      <CurrencyNote currency={currency} />
    </>
  );
}

function Payback({ data }: { data: Sources }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { referral } = data;

  return (
    <Card>
      <CardHeader
        icon={Share2}
        title={t("analytics.sources.paybackTitle")}
        description={t("analytics.sources.paybackDescription")}
      />
      <div className="flex flex-col gap-4 pt-4">
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
    </Card>
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
    <Card>
      <CardHeader
        icon={Trophy}
        title={t("analytics.sources.topTitle")}
        description={t("analytics.sources.topDescription")}
        aside={
          <SegmentedPills
            value={sort}
            onChange={setSort}
            options={(["revenue", "invited"] as const).map((value) => ({
              value,
              label: t(`analytics.sources.sort.${value}` as ParseKeys),
            }))}
          />
        }
      />
      {rows.length === 0 ? (
        <p className="py-6 text-center text-[13px] text-muted-foreground">
          {t("analytics.sources.empty")}
        </p>
      ) : (
        rows.map((row) => (
          <button
            key={row.user_id}
            type="button"
            onClick={() => openUser(row.user_id)}
            className={`grid w-full grid-cols-[36px_minmax(0,1fr)_auto_auto] items-center gap-3 ${LIST_ROW_CLASS} text-left hover:bg-white/[0.04]`}
          >
            <span className="flex size-9 items-center justify-center rounded-full bg-violet-400/10 text-[12px] font-bold text-violet-300">
              {initials(row.name)}
            </span>
            <span className="min-w-0">
              <span className="block truncate text-[13.5px] font-medium text-foreground">
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
          </button>
        ))
      )}
    </Card>
  );
}
