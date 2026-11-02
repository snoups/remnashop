import { Scale } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listLegalDocuments, LEGAL_KINDS, type LegalDocument, type LegalKind } from "@entities/legal/api";
import { usePermissions } from "@entities/user/use-current-user";
import { LegalDocumentDialog } from "@features/legal-documents-editor/LegalDocumentDialog";
import { KIND_ICONS } from "@features/legal-documents-editor/legal-drafts";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { Spinner } from "@shared/ui/Spinner";

// Documents with where they're shown; visibility and texts are edited together in the dialog.
export function LegalDocumentsEditor() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canUpdate = permissions.includes("LEGAL_DOCUMENTS_UPDATE");
  const canSet = permissions.includes("LEGAL_TEXT_SET");
  const canRemove = permissions.includes("LEGAL_TEXT_REMOVE");
  const [state, reload] = useAsyncResource(listLegalDocuments);
  const [editing, setEditing] = useState<LegalKind | null>(null);

  const status = (document: LegalDocument) =>
    [document.show_in_bot && t("settings.legal.tabs.BOT"), document.show_in_cabinet && t("settings.legal.tabs.CABINET")]
      .filter(Boolean)
      .join(" · ") || t("settings.legal.hidden");
  const editingDocument = state.kind === "ready" ? state.data.items.find((item) => item.kind === editing) : undefined;

  return (
    <Section icon={Scale} title={t("settings.legal.title")} description={t("settings.legal.description")}>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <SectionRows>
          {LEGAL_KINDS.map((kind) => {
            const document = state.data.items.find((item) => item.kind === kind);
            if (!document) return null;
            return (
              <Row key={kind} icon={KIND_ICONS[kind]} label={t(`settings.legal.kinds.${kind}`)} description={status(document)}>
                <Button variant="glass" size="sm" onClick={() => setEditing(kind)}>
                  {t("common.edit")}
                </Button>
              </Row>
            );
          })}
        </SectionRows>
      )}
      {state.kind === "ready" && editingDocument && (
        <LegalDocumentDialog
          document={editingDocument}
          locales={state.data.locales}
          canUpdate={canUpdate}
          canSet={canSet}
          canRemove={canRemove}
          onChanged={reload}
          onClose={() => setEditing(null)}
        />
      )}
    </Section>
  );
}
