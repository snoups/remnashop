import { useTranslation } from "react-i18next";

import {
  getGatewayCatalog,
  listGateways,
  reorderGateways,
  type Gateway,
  type GatewayCatalogEntry,
} from "@entities/gateways/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";

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

  if (state.kind === "error") {
    return <p className="text-sm text-error">{t("settings.gateways.loadError")}</p>;
  }

  if (state.kind === "loading") {
    return <p className="text-sm text-muted-foreground">{t("settings.gateways.loading")}</p>;
  }

  const { gateways, catalog } = state.data;
  const fieldsByType = new Map(catalog.map((entry) => [entry.type, entry.fields]));

  const moveGateway = async (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= gateways.length) return;

    const reordered = [...gateways];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    setData({ gateways: reordered, catalog });

    try {
      const updated = await reorderGateways(reordered.map((gateway) => gateway.type));
      setData({ gateways: updated, catalog });
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
      setData({ gateways, catalog });
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {gateways.map((gateway, index) => (
        <GatewaySettingsCard
          key={gateway.type}
          gateway={gateway}
          fields={fieldsByType.get(gateway.type) ?? []}
          onChanged={(updated) =>
            setData({
              gateways: gateways.map((existing) => (existing.type === updated.type ? updated : existing)),
              catalog,
            })
          }
          onMoveUp={index > 0 ? () => void moveGateway(index, -1) : undefined}
          onMoveDown={index < gateways.length - 1 ? () => void moveGateway(index, 1) : undefined}
        />
      ))}
    </div>
  );
}
