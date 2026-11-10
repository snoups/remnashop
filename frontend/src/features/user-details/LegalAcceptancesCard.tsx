import { Check, Scale } from "lucide-react";
import { useState } from "react";
import type { ComponentType, ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { listUserLegalAcceptances } from "@entities/legal/api";
import { KIND_ICONS } from "@features/legal-documents-editor/legal-drafts";
import { copyToClipboard } from "@shared/lib/clipboard";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { formatDateTime } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { Pressable } from "@shared/ui/Pressable";

export function LegalAcceptancesCard({ userId }: { userId: number }) {
  const { t, i18n } = useTranslation();
  const { openOrder } = useOpenEntity();
  const [state] = useAsyncResource((signal) => listUserLegalAcceptances(userId, signal), { deps: [userId] });
  // nothing accepted yet: no card at all
  if (state.kind === "loading" || (state.kind === "ready" && state.data.items.length === 0)) return null;
  return (
    <DialogCard collapsible title={t("users.legalAcceptances.title")} icon={Scale}>
      {state.kind === "error" && (
        <p className="px-3 py-2 text-sm text-muted-foreground">{t("common.loadError")}</p>
      )}
      {state.kind === "ready" &&
        state.data.items.map((item) => (
          <AcceptanceRow
            key={item.id}
            icon={KIND_ICONS[item.kind]}
            title={t(`settings.legal.kinds.${item.kind}`)}
            date={formatDateTime(item.accepted_at, i18n.language)}
          >
            {t(`settings.legal.channels.${item.channel}`)}
            {" · "}
            {t(`users.legalAcceptances.triggers.${item.trigger}`)}
            {item.transaction_id !== null && (
              <>
                {" · "}
                <button
                  type="button"
                  className="pointer-events-auto text-primary hover:underline"
                  onClick={() => openOrder(item.transaction_id as number)}
                >
                  {t("users.legalAcceptances.order", { id: item.transaction_id })}
                </button>
              </>
            )}
          </AcceptanceRow>
        ))}
    </DialogCard>
  );
}

/** Two lines, the document then where and why, the date beside both; a click anywhere copies the
 *  date, as an InfoRow does with its value. */
function AcceptanceRow({
  icon: Icon,
  title,
  date,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  date: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [isCopied, setIsCopied] = useState(false);
  const copy = () =>
    void copyToClipboard(date).then((copied) => {
      if (!copied) return;
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1500);
    });
  return (
    <div className="relative flex items-center gap-2.5 rounded-full px-2.5 py-1.5 transition-colors hover:bg-white/[0.04]">
      {/* a sibling under the content, not a parent: the order link stays its own button */}
      <Pressable type="button" onClick={copy} className="absolute inset-0 rounded-full" />
      <div className="pointer-events-none relative flex min-w-0 flex-1 items-center gap-2.5">
        <Icon className="size-[15px] shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium text-foreground">{title}</div>
          <div className="truncate text-xs text-muted-foreground">{children}</div>
        </div>
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{date}</span>
      </div>
      {isCopied && (
        <span className="absolute inset-0 flex items-center justify-center gap-1.5 rounded-full bg-black/35 text-xs font-medium text-primary">
          <Check className="size-3.5" />
          {t("app.copied")}
        </span>
      )}
    </div>
  );
}
