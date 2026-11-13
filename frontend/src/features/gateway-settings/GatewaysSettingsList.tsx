import { CreditCard } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  getGatewayCatalog,
  listGateways,
  type Gateway,
  type GatewayCatalogEntry,
} from "@entities/gateways/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { Spinner } from "@shared/ui/Spinner";

import { GatewaySettingsCard } from "./GatewaySettingsCard";
import { PaymentEmailField } from "./PaymentEmailField";

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
  const canViewShop = usePermissions().includes("SHOP_SETTINGS_VIEW");

  return (
    <Section icon={CreditCard} title={t("settings.gateways.title")} description={t("settings.gateways.description")}>
      {canViewShop && <PaymentEmailField />}
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && (
        <ErrorState text={t("common.loadError")} />
      )}
      {state.kind === "ready" && (
        <SectionRows>
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
        </SectionRows>
      )}
    </Section>
  );
}
