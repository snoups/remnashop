import { Globe2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { NodeCard, NodesOverview } from "@entities/overview/api";
import { formatBytes } from "@shared/lib/format";
import type { AsyncState } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";

type View = "nodes" | "countries";

const ROW_CLASS = "grid grid-cols-[28px_minmax(0,1fr)_minmax(40px,96px)_auto] items-center gap-3 py-2 sm:grid-cols-[28px_minmax(0,1fr)_minmax(60px,160px)_auto_72px]";

function statusDot(node: NodeCard): string {
  if (node.is_disabled) return "bg-muted-foreground";
  return node.is_connected ? "bg-success" : "bg-error";
}

function Track({ value, max }: { value: number; max: number }) {
  return (
    <div className="h-2 overflow-hidden rounded-full bg-white/[0.06]">
      <div className="h-full rounded-full bg-primary" style={{ width: `${max > 0 ? (value / max) * 100 : 0}%` }} />
    </div>
  );
}

function CountryChip({ code }: { code: string }) {
  return (
    <span className="flex h-6 items-center justify-center rounded-md bg-white/[0.06] font-mono text-[11px] font-semibold text-foreground">
      {code.slice(0, 2).toUpperCase()}
    </span>
  );
}

function NodeRows({ nodes }: { nodes: NodeCard[] }) {
  const { t, i18n } = useTranslation();
  const max = Math.max(0, ...nodes.map((node) => node.users_online));
  return nodes.map((node) => (
    <div key={node.name} className={ROW_CLASS}>
      <CountryChip code={node.country_code} />
      <span className="flex min-w-0 items-center gap-2 text-[13px] font-medium text-foreground">
        <span className={`size-2 shrink-0 rounded-full ${statusDot(node)}`} />
        <span className="truncate">{node.name}</span>
      </span>
      <Track value={node.users_online} max={max} />
      <span className="text-right text-[13px] font-semibold tabular-nums text-foreground">
        {node.is_disabled || !node.is_connected ? t("common.none") : node.users_online.toLocaleString(i18n.language)}
      </span>
      <span className="hidden text-right text-[12px] tabular-nums text-muted-foreground sm:block">
        {node.traffic_used_bytes === null ? t("common.none") : formatBytes(node.traffic_used_bytes, i18n.language)}
      </span>
    </div>
  ));
}

function CountryRows({ countries }: { countries: NodesOverview["countries"] }) {
  const { t, i18n } = useTranslation();
  const max = Math.max(0, ...countries.map((country) => country.users_online));
  return countries.map((country) => (
    <div key={country.country_code} className={ROW_CLASS}>
      <CountryChip code={country.country_code} />
      <span className="min-w-0 truncate text-[13px] text-muted-foreground">
        {t("dashboard.nodes.connected", {
          count: country.nodes,
          connected: country.connected.toLocaleString(i18n.language),
          nodes: country.nodes.toLocaleString(i18n.language),
        })}
      </span>
      <Track value={country.users_online} max={max} />
      <span className="text-right text-[13px] font-semibold tabular-nums text-foreground">
        {country.users_online.toLocaleString(i18n.language)}
      </span>
      <span className="hidden sm:block" />
    </div>
  ));
}

export function NodesCard({ state }: { state: AsyncState<NodesOverview | null> }) {
  const { t } = useTranslation();
  const [view, setView] = useState<View>("nodes");
  const data = state.kind === "ready" ? state.data : null;
  const rows = data?.available ? (view === "nodes" ? data.nodes : data.countries) : [];

  return (
    <Card>
      <CardHeader
        icon={Globe2}
        title={t("dashboard.nodes.title")}
        description={t("dashboard.nodes.description")}
        aside={
          <SegmentedPills
            value={view}
            onChange={setView}
            options={[
              { value: "nodes", label: t("dashboard.nodes.nodes") },
              { value: "countries", label: t("dashboard.nodes.countries") },
            ]}
          />
        }
      />
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("dashboard.loadError")} />}
      {data && !data.available && (
        <p className="py-6 text-center text-[13px] text-muted-foreground">{t("dashboard.remnawaveUnavailable")}</p>
      )}
      {data?.available && rows.length === 0 && (
        <p className="py-6 text-center text-[13px] text-muted-foreground">{t("dashboard.nodes.empty")}</p>
      )}
      {data?.available && rows.length > 0 && (
        <div className="pt-2">
          {view === "nodes" ? <NodeRows nodes={data.nodes} /> : <CountryRows countries={data.countries} />}
        </div>
      )}
    </Card>
  );
}
