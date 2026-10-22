import { FileText } from "lucide-react";
import { useTranslation } from "react-i18next";

import { listUserLegalAcceptances } from "@entities/legal/api";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatDateTime } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { InfoRow } from "@shared/ui/InfoRow";
import { Tag } from "@shared/ui/Tag";

export function LegalAcceptancesCard({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const { openOrder } = useOpenEntity();
  const [state] = useAsyncResource((signal) => listUserLegalAcceptances(userId, signal), { deps: [userId] });
  if (state.kind === "loading") return null;
  return (
    <Card variant="list" title={t("users.legalAcceptances.title")} icon={FileText}>
      {state.kind === "error" && (
        <p className="px-3 py-2 text-[13px] text-muted-foreground">{t("users.legalAcceptances.loadError")}</p>
      )}
      {state.kind === "ready" && state.data.items.length === 0 && (
        <p className="px-3 py-2 text-[13px] text-muted-foreground">{t("users.legalAcceptances.none")}</p>
      )}
      {state.kind === "ready" &&
        state.data.items.map((item) => (
          <InfoRow key={item.id} icon={FileText} label={t(`settings.legal.kinds.${item.kind}`)}>
            <span className="flex min-w-0 flex-wrap items-center justify-end gap-1.5">
              <Tag>{t(`settings.legal.channels.${item.channel}`)}</Tag>
              <span className="font-normal">{t(`users.legalAcceptances.triggers.${item.trigger}`)}</span>
              {item.transaction_id !== null && (
                <button
                  type="button"
                  className="text-primary hover:underline"
                  onClick={() => openOrder(item.transaction_id as number)}
                >
                  {t("users.legalAcceptances.order", { id: item.transaction_id })}
                </button>
              )}
              <span className="font-mono">{formatDateTime(item.accepted_at, i18n.language)}</span>
            </span>
          </InfoRow>
        ))}
    </Card>
  );
}
