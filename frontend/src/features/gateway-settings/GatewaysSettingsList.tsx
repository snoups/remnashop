import { CreditCard } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  getGatewayCatalog,
  listGateways,
  type Gateway,
  type GatewayCatalogEntry,
} from "@entities/gateways/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Spinner } from "@shared/ui/Spinner";
import { Card } from "@shared/ui/Card";

import { GatewaySettingsCard } from "./GatewaySettingsCard";

interface GatewaysData {
  gateways: Gateway[];
  catalog: GatewayCatalogEntry[];
}

async function loadGatewaysData(signal?: AbortSignal): Promise<GatewaysData> {
  const [gateways, catalog] = await Promise.all([listGateways(signal), getGatewayCatalog(signal)]);
  return { gateways, catalog };
}

export function GatewaysSettingsList() {
  const { t } = useTranslation();
  const [state, , setData] = useAsyncResource(loadGatewaysData);

  return (
    <Card>
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <CreditCard className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("settings.gateways.title")}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("settings.gateways.description")}</p>
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && (
        <p className="mt-4 text-sm text-error">{t("settings.gateways.loadError")}</p>
      )}
      {state.kind === "ready" && (
        <div className="mt-4 flex flex-col [&>:not(:last-child)>:first-child]:border-b [&>:not(:last-child)>:first-child]:border-border/50">
          {state.data.gateways.map((gateway) => {
            const entry = state.data.catalog.find((candidate) => candidate.type === gateway.type);
            return (
              <GatewaySettingsCard
                key={gateway.type}
                gateway={gateway}
                fields={entry?.fields ?? []}
                webhookUrl={entry?.webhook_url ?? null}
                onChanged={(updated) =>
                  setData({
                    ...state.data,
                    gateways: state.data.gateways.map((existing) =>
                      existing.type === updated.type ? updated : existing,
                    ),
                  })
                }
              />
            );
          })}
        </div>
      )}
    </Card>
  );
}
