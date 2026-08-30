import { useEffect, useState } from "react";
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

import { GatewaySettingsCard } from "./GatewaySettingsCard";

export function GatewaysSettingsList() {
  const { t } = useTranslation();
  const [gateways, setGateways] = useState<Gateway[] | null>(null);
  const [catalog, setCatalog] = useState<GatewayCatalogEntry[] | null>(null);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([listGateways(), getGatewayCatalog()])
      .then(([gatewaysResult, catalogResult]) => {
        if (cancelled) return;
        setGateways(gatewaysResult);
        setCatalog(catalogResult);
      })
      .catch(() => {
        if (!cancelled) setHasError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const fieldsByType = new Map((catalog ?? []).map((entry) => [entry.type, entry.fields]));

  const moveGateway = async (index: number, direction: -1 | 1) => {
    if (!gateways) return;
    const target = index + direction;
    if (target < 0 || target >= gateways.length) return;

    const previous = gateways;
    const reordered = [...gateways];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    setGateways(reordered);

    try {
      const updated = await reorderGateways(reordered.map((gateway) => gateway.type));
      setGateways(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
      setGateways(previous);
    }
  };

  if (hasError) {
    return <p className="text-sm text-error">{t("settings.gateways.loadError")}</p>;
  }

  if (!gateways || !catalog) {
    return <p className="text-sm text-muted-foreground">{t("settings.gateways.loading")}</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {gateways.map((gateway, index) => (
        <GatewaySettingsCard
          key={gateway.type}
          gateway={gateway}
          fields={fieldsByType.get(gateway.type) ?? []}
          onChanged={(updated) =>
            setGateways((prev) =>
              (prev ?? []).map((existing) =>
                existing.type === updated.type ? updated : existing,
              ),
            )
          }
          onMoveUp={index > 0 ? () => void moveGateway(index, -1) : undefined}
          onMoveDown={index < gateways.length - 1 ? () => void moveGateway(index, 1) : undefined}
        />
      ))}
    </div>
  );
}
