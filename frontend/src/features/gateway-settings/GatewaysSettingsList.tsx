import { CreditCard } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  getGatewayCatalog,
  listGateways,
  type Gateway,
  type GatewayCatalogEntry,
} from "@entities/gateways/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";

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
      <CardHeader
        icon={CreditCard}
        title={t("settings.gateways.title")}
        description={t("settings.gateways.description")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && (
        <ErrorState text={t("common.loadError")} />
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
