import { Smartphone } from "lucide-react";
import { useTranslation } from "react-i18next";

import { getClientApps } from "@entities/overview/api";
import type { ClientApps } from "@entities/overview/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";

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
      <div className="flex items-baseline justify-between gap-3 text-[13px]">
        <span className="font-semibold text-foreground">{platform.platform}</span>
        <span className="tabular-nums text-muted-foreground">{platform.total.toLocaleString(i18n.language)}</span>
      </div>
      <div className="flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-white/[0.06]">
        {sum > 0 &&
          segments.map((segment) => (
            <div key={segment.label} className={segment.tone} style={{ width: `${(segment.count / sum) * 100}%` }} />
          ))}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[12px] text-muted-foreground">
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
  const { t, i18n } = useTranslation();
  const [state] = useAsyncResource(getClientApps, { deps: [refreshKey], keepData: true });
  const data = state.kind === "ready" ? state.data : null;

  return (
    <Card>
      <CardHeader
        icon={Smartphone}
        title={t("dashboard.clientApps.title")}
        description={t("dashboard.clientApps.description")}
        aside={
          data?.available &&
          data.total_devices > 0 && (
            <Tag>
              {t("dashboard.clientApps.devices", {
                count: data.total_devices,
                formatted: data.total_devices.toLocaleString(i18n.language),
                avg: data.average_per_user.toLocaleString(i18n.language, {
                  minimumFractionDigits: 1,
                  maximumFractionDigits: 1,
                }),
              })}
            </Tag>
          )
        }
      />
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {data && !data.available && (
        <p className="py-6 text-center text-[13px] text-muted-foreground">{t("dashboard.remnawaveUnavailable")}</p>
      )}
      {data?.available && data.platforms.length === 0 && (
        <p className="py-6 text-center text-[13px] text-muted-foreground">{t("dashboard.clientApps.empty")}</p>
      )}
      {data?.available && data.platforms.length > 0 && (
        <div className="flex flex-col gap-4 pt-4">
          {data.platforms.map((platform) => (
            <PlatformRow key={platform.platform} platform={platform} />
          ))}
        </div>
      )}
    </Card>
  );
}
