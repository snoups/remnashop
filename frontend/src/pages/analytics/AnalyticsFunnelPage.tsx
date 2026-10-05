import type { ParseKeys } from "i18next";
import { ArrowDown, Filter, Link2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getFunnel } from "@entities/analytics/api";
import type { Funnel, FunnelSourceRow, FunnelStep } from "@entities/analytics/api";
import { formatPercent } from "@shared/lib/format";
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
import { useAnalyticsPeriod } from "@pages/analytics/period";

const SOURCE_GRID = "grid grid-cols-[minmax(0,1.4fr)_repeat(4,minmax(0,1fr))] gap-3";

export function AnalyticsFunnelPage() {
  const { t } = useTranslation();
  const { period } = useAnalyticsPeriod();
  const [state] = useAsyncResource((signal) => getFunnel(period, signal), { deps: [period], keepData: true });

  return (
    <div className="flex flex-col gap-4 pb-2">
      <AnalyticsToolbar />
      {state.kind === "loading" && <Spinner size="page" />}
      {state.kind === "error" && <ErrorState text={t("analytics.loadError")} />}
      {state.kind === "ready" && <Overview data={state.data} />}
    </div>
  );
}

function Overview({ data }: { data: Funnel }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const { steps } = data;
  const registered = steps.find((step) => step.key === "registered");
  const connected = steps.find((step) => step.key === "connected");
  const firstPaid = steps.find((step) => step.key === "first_paid");

  const biggestDrop =
    (steps[0]?.count ?? 0) > 0
      ? steps.slice(1).reduce<FunnelStep | null>((worst, step) => (!worst || step.pct_of_prev < worst.pct_of_prev ? step : worst), null)
      : null;

  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
      <Card>
        <CardHeader icon={Filter} title={t("analytics.funnel.title")} description={t("analytics.funnel.description")} />
        <div className="mt-2 flex flex-col">
          {steps.map((step, index) => (
            <FunnelStepRow
              key={step.key}
              step={step}
              index={index}
              paidViaTrial={step.key === "first_paid" ? data.paid_via_trial : undefined}
              isBiggestDrop={step === biggestDrop}
            />
          ))}
        </div>
      </Card>

      <div className="flex flex-col gap-3">
        {registered && connected && firstPaid && (
          <>
            <KpiTile
              highlighted
              label={t("analytics.funnel.conversion")}
              value={formatPercent(firstPaid.pct_of_start, language)}
            />
            <KpiTile
              label={t("analytics.funnel.neverConnected")}
              value={(registered.count - connected.count).toLocaleString(language)}
              hint={t("analytics.funnel.neverConnectedHint")}
            />
            <KpiTile label={t("analytics.funnel.connectedUnpaid")} value={(connected.count - firstPaid.count).toLocaleString(language)} />
          </>
        )}
      </div>

      <Card className="xl:col-span-2">
        <CardHeader
          icon={Link2}
          title={t("analytics.funnel.bySource")}
          description={t("analytics.funnel.bySourceDescription")}
        />
        <SourceTable rows={data.by_source} />
      </Card>
    </div>
  );
}

function FunnelStepRow({
  step,
  index,
  paidViaTrial,
  isBiggestDrop,
}: {
  step: FunnelStep;
  index: number;
  paidViaTrial?: number;
  isBiggestDrop: boolean;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  const startShare = Math.min(100, step.pct_of_start * 100);
  const viaShare = paidViaTrial !== undefined && step.count > 0 ? Math.min(1, paidViaTrial / step.count) : 0;

  return (
    <div className="flex flex-col">
      {index > 0 && (
        <div className="flex flex-wrap items-center gap-2 py-0.5 pl-[26px] text-[11.5px] text-muted-foreground">
          <ArrowDown className="size-3" />
          <span className="tabular-nums text-foreground">{formatPercent(step.pct_of_prev, language)}</span>
          {t("analytics.funnel.ofPrevious")}
          {isBiggestDrop && <Badge tone="warning">{t("analytics.funnel.biggestDrop")}</Badge>}
        </div>
      )}
      <div className="grid grid-cols-[32px_minmax(0,1fr)_auto_auto] items-center gap-x-3 gap-y-1 rounded-3xl px-3 py-2.5 sm:grid-cols-[32px_minmax(0,160px)_minmax(0,1fr)_72px_56px]">
        <span className="flex size-8 items-center justify-center rounded-full bg-white/[0.06] text-[13px] font-bold text-foreground">
          {index + 1}
        </span>
        <span className="truncate text-[13.5px] font-medium text-foreground">
          {t(`analytics.funnel.steps.${step.key}` as ParseKeys)}
        </span>
        <span className="order-last col-span-4 flex h-2.5 overflow-hidden rounded-full bg-white/[0.06] sm:order-none sm:col-span-1">
          <span className="h-full bg-primary transition-all" style={{ width: `${startShare * (paidViaTrial === undefined ? 1 : viaShare)}%` }} />
          {paidViaTrial !== undefined && (
            <span className="h-full bg-primary/50 transition-all" style={{ width: `${startShare * (1 - viaShare)}%` }} />
          )}
        </span>
        <span className="text-right text-[15px] font-bold tabular-nums text-foreground">
          {step.count.toLocaleString(language)}
        </span>
        <span className="text-right text-[12.5px] tabular-nums text-muted-foreground">
          {formatPercent(step.pct_of_start, language)}
        </span>
      </div>
      {paidViaTrial !== undefined && (
        <div className="flex flex-wrap gap-2 pb-1 pl-[56px]">
          <Tag>{t("analytics.funnel.viaTrial", { value: paidViaTrial.toLocaleString(language) })}</Tag>
          <Tag>{t("analytics.funnel.direct", { value: (step.count - paidViaTrial).toLocaleString(language) })}</Tag>
        </div>
      )}
    </div>
  );
}

function SourceTable({ rows }: { rows: FunnelSourceRow[] }) {
  const { t, i18n } = useTranslation();
  const language = i18n.language;
  if (rows.length === 0) {
    return <p className="py-6 text-center text-[13px] text-muted-foreground">{t("analytics.funnel.sourcesEmpty")}</p>;
  }

  const label = (row: FunnelSourceRow) =>
    row.source === "organic"
      ? t("analytics.sources.organic")
      : row.source === "referral"
        ? t("analytics.sources.referral")
        : (row.name ?? `#${row.ad_link_id}`);
  const cell = (count: number, registered: number) => (
    <span className="text-right tabular-nums text-foreground">
      {count.toLocaleString(language)}
      <span className="ml-1.5 text-[12px] text-muted-foreground">
        {registered > 0 ? formatPercent(count / registered, language) : t("common.none")}
      </span>
    </span>
  );

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[560px]">
        <div className={`${SOURCE_GRID} ${LIST_HEAD_CLASS}`}>
          <span>{t("analytics.funnel.source")}</span>
          <span className="text-right">{t("analytics.funnel.registrations")}</span>
          <span className="text-right">{t("analytics.funnel.connectedShort")}</span>
          <span className="text-right">{t("analytics.funnel.paidShort")}</span>
          <span className="text-right">{t("analytics.funnel.repeatShort")}</span>
        </div>
        {rows.map((row) => (
          <div key={`${row.source}:${row.ad_link_id ?? ""}`} className={`${SOURCE_GRID} items-center px-3 py-2 text-[13px]`}>
            <span className="truncate text-foreground">{label(row)}</span>
            <span className="text-right tabular-nums text-foreground">{row.registered.toLocaleString(language)}</span>
            {cell(row.connected, row.registered)}
            {cell(row.paid, row.registered)}
            {cell(row.repeat_paid, row.registered)}
          </div>
        ))}
      </div>
    </div>
  );
}
