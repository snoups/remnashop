import { Scale, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listLegalDocuments, LEGAL_KINDS } from "@entities/legal/api";
import { usePermissions } from "@entities/user/use-current-user";
import { LegalDocumentCard } from "@features/legal-documents-editor/LegalDocumentCard";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";

export function LegalDocumentsEditor() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const [state, reload, setData] = useAsyncResource(listLegalDocuments);
  const [selectedLocale, setSelectedLocale] = useState<string | null>(null);

  if (state.kind === "loading") return <Spinner size="card" />;
  if (state.kind === "error") {
    return (
      <Card>
        <CardHeader icon={Scale} title={t("settings.legal.title")} description={t("settings.legal.description")} />
        <ErrorState text={t("common.loadError")} />
      </Card>
    );
  }

  const { locales } = state.data;
  const locale = selectedLocale && locales.includes(selectedLocale) ? selectedLocale : locales[0];
  const missing = state.data.offer_missing_in;

  return (
    <div className="flex flex-col gap-4">
      {missing.length > 0 && (
        <div className="flex items-start gap-2.5 rounded-2xl border border-warning/30 bg-warning/10 p-3.5 text-warning">
          <TriangleAlert className="mt-0.5 size-4 shrink-0" />
          <p className="text-[13px]">
            {t("settings.legal.offerMissing", {
              channels: missing.map((channel) => t(`settings.legal.channels.${channel}`)).join(", "),
            })}
          </p>
        </div>
      )}
      {LEGAL_KINDS.map((kind) => {
        const document = state.data.items.find((item) => item.kind === kind);
        return document ? (
          <LegalDocumentCard
            key={kind}
            document={document}
            locales={locales}
            locale={locale}
            onLocaleChange={setSelectedLocale}
            canUpdate={permissions.includes("LEGAL_DOCUMENTS_UPDATE")}
            canSet={permissions.includes("LEGAL_TEXT_SET")}
            canRemove={permissions.includes("LEGAL_TEXT_REMOVE")}
            onChanged={reload}
            onDocumentChanged={(updated) =>
              setData((prev) => ({
                ...prev,
                items: prev.items.map((item) => (item.kind === updated.kind ? { ...item, ...updated } : item)),
              }))
            }
          />
        ) : null;
      })}
    </div>
  );
}
