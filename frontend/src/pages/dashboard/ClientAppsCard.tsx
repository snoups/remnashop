import { Smartphone } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getClientApps } from "@entities/overview/api";
import type { ClientApps } from "@entities/overview/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { AsyncState } from "@shared/lib/use-async-resource";
import { Section } from "@shared/ui/glass/Section";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Spinner } from "@shared/ui/Spinner";

const TOP_APPS = 4;
const APP_TONES: string[] = ["bg-primary", "bg-accent-foreground", "bg-success", "bg-warning"];
const OTHER_TONE = "bg-muted-foreground";

function PlatformRow({ platform }: { platform: ClientApps["platforms"][number] }) {
  const { t, i18n } = useTranslation();
  const sorted = [...platform.apps].sort((a, b) => b.count - a.count);
  const segments = sorted.slice(0, TOP_APPS).map((app, index) => ({ label: app.app, count: app.count, tone: APP_TONES[index] }));
  const rest = sorted.slice(TOP_APPS).reduce((sum, app) => sum + app.count, 0);
  if (rest > 0) segments.push({ label: t("dashboard.clientApps.other"), count: rest, tone: OTHER_TONE });
  const sum = segments.reduce((acc, segment) => acc + segment.count, 0);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-semibold text-foreground">{platform.platform}</span>
        <span className="tabular-nums text-muted-foreground">{platform.total.toLocaleString(i18n.language)}</span>
      </div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full glass-track">
        {sum > 0 &&
          segments.map((segment) => (
            <div key={segment.label} className={segment.tone} style={{ width: `${(segment.count / sum) * 100}%` }} />
          ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {segments.map((segment) => (
          <span key={segment.label} className="flex items-center gap-1.5">
            <span className={`size-2 rounded-full ${segment.tone}`} />
            {segment.label} · {segment.count.toLocaleString(i18n.language)}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ClientAppsCard({ refreshKey }: { refreshKey: number }) {
  const [state] = useAsyncResource(getClientApps, { deps: [refreshKey], keepData: true });
  return <ClientAppsSection state={state} />;
}

export function ClientAppsSection({ state }: { state: AsyncState<ClientApps> }) {
  const { t } = useTranslation();
  const data = state.kind === "ready" ? state.data : null;

  return (
    <Section
      stretched
      className="min-h-0 flex-1 overflow-hidden"
      icon={Smartphone}
      title={t("dashboard.clientApps.title")}
      description={t("dashboard.clientApps.description")}
    >
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {data && !data.available && (
        <EmptyState text={t("dashboard.remnawaveUnavailable")} />
      )}
      {data?.available && data.platforms.length === 0 && (
        <EmptyState text={t("dashboard.clientApps.empty")} />
      )}
      {data?.available && data.platforms.length > 0 && (
        <div className="-mb-4 -mr-4 flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto overscroll-contain pb-4 pr-[calc(1rem-var(--scrollbar-size))] [scrollbar-gutter:stable] pt-4">
          {data.platforms.map((platform) => (
            <PlatformRow key={platform.platform} platform={platform} />
          ))}
        </div>
      )}
    </Section>
  );
}
