import { Bot, Globe, Scale } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  listLegalDocuments,
  updateLegalDocument,
  LEGAL_KINDS,
  type LegalChannel,
  type LegalDocument,
  type LegalKind,
} from "@entities/legal/api";
import { usePermissions } from "@entities/user/use-current-user";
import { LegalDocumentDialog } from "@features/legal-documents-editor/LegalDocumentDialog";
import { KIND_ICONS } from "@features/legal-documents-editor/legal-drafts";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { SETTINGS_ROWS_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/EmptyState";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { SettingsRow } from "@shared/ui/SettingsRow";
import { Spinner } from "@shared/ui/Spinner";

const CHANNELS = ["BOT", "CABINET"] as const;
const CHANNEL_ICONS = { BOT: Bot, CABINET: Globe } as const;
const FLAG_FIELDS = { BOT: "show_in_bot", CABINET: "show_in_cabinet" } as const;

type Flags = Record<LegalKind, { show_in_bot: boolean; show_in_cabinet: boolean }>;

export function LegalDocumentsEditor() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canUpdate = permissions.includes("LEGAL_DOCUMENTS_UPDATE");
  const canSet = permissions.includes("LEGAL_TEXT_SET");
  const canRemove = permissions.includes("LEGAL_TEXT_REMOVE");
  const [state, reload] = useAsyncResource(listLegalDocuments);
  const [flags, setFlags] = useState<Partial<Flags>>({});
  const [editing, setEditing] = useState<LegalKind | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (state.kind !== "ready") return;
    setFlags(
      Object.fromEntries(
        state.data.items.map((item) => [item.kind, { show_in_bot: item.show_in_bot, show_in_cabinet: item.show_in_cabinet }]),
      ),
    );
  }, [state]);

  const header = <CardHeader icon={Scale} title={t("settings.legal.title")} description={t("settings.legal.description")} />;
  if (state.kind !== "ready") {
    return (
      <Card>
        {header}
        {state.kind === "loading" ? <Spinner size="card" /> : <ErrorState text={t("common.loadError")} />}
      </Card>
    );
  }

  const { items, locales } = state.data;
  const changed = items.filter((item) => {
    const draft = flags[item.kind];
    return draft && (draft.show_in_bot !== item.show_in_bot || draft.show_in_cabinet !== item.show_in_cabinet);
  });
  const editingDocument = items.find((item) => item.kind === editing);

  const save = async () => {
    setSaving(true);
    try {
      for (const item of changed) {
        const draft = flags[item.kind];
        if (draft) await updateLegalDocument(item.kind, draft);
      }
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setSaving(false);
      reload();
    }
  };

  return (
    <Card>
      {header}
      <div className={`mt-4 ${SETTINGS_ROWS_CLASS}`}>
        {LEGAL_KINDS.map((kind) => {
          const document = items.find((item) => item.kind === kind);
          if (!document) return null;
          const draft = flags[kind] ?? { show_in_bot: document.show_in_bot, show_in_cabinet: document.show_in_cabinet };
          return (
            <SettingsRow
              key={kind}
              icon={KIND_ICONS[kind]}
              label={t(`settings.legal.kinds.${kind}`)}
            >
              {CHANNELS.map((channel) => {
                const Icon = CHANNEL_ICONS[channel];
                const field = FLAG_FIELDS[channel];
                const hasText = hasTextFor(document, channel);
                return (
                  <ChoiceChip
                    key={channel}
                    active={draft[field] && hasText}
                    disabled={!canUpdate || saving || !hasText}
                    onClick={() => setFlags((prev) => ({ ...prev, [kind]: { ...draft, [field]: !draft[field] } }))}
                  >
                    <Icon className="size-3.5" />
                    {t(`settings.legal.chips.${channel}`)}
                  </ChoiceChip>
                );
              })}
              <Button variant="secondary" onClick={() => setEditing(kind)}>
                {t("common.edit")}
              </Button>
            </SettingsRow>
          );
        })}
      </div>
      {canUpdate && <SaveFooter dirty={changed.length > 0} saving={saving} onSave={() => void save()} />}
      {editingDocument && (
        <LegalDocumentDialog
          document={editingDocument}
          locales={locales}
          canSet={canSet}
          canRemove={canRemove}
          onChanged={reload}
          onClose={() => setEditing(null)}
        />
      )}
    </Card>
  );
}

// shown only once some text exists for the channel, its own or the common one
function hasTextFor(document: LegalDocument, channel: LegalChannel): boolean {
  return document.texts.some((item) => item.channel === null || item.channel === channel);
}
