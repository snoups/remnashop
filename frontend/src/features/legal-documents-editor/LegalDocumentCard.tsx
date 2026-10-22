import { Bot, FileText, Globe, Layers } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { updateLegalDocument, type LegalChannel, type LegalDocument } from "@entities/legal/api";
import { LegalTextEditor } from "@features/legal-documents-editor/LegalTextEditor";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { DialogTabs } from "@shared/ui/DialogTabs";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Switch } from "@shared/ui/Switch";

const CHANNEL_ICONS = { BOT: Bot, CABINET: Globe } as const;
const COMMON_ICON = Layers;
const DOCUMENT_ICON = FileText;

interface Props {
  document: LegalDocument;
  locales: string[];
  locale: string;
  onLocaleChange: (locale: string) => void;
  canUpdate: boolean;
  canSet: boolean;
  canRemove: boolean;
  onChanged: () => void;
  onDocumentChanged: (document: Omit<LegalDocument, "texts">) => void;
}

type Tab = "common" | "BOT" | "CABINET";

export function LegalDocumentCard({
  document,
  locales,
  locale,
  onLocaleChange,
  canUpdate,
  canSet,
  canRemove,
  onChanged,
  onDocumentChanged,
}: Props) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("common");
  const [pending, setPending] = useState(false);

  const toggle = async (patch: { show_in_bot?: boolean; show_in_cabinet?: boolean }) => {
    setPending(true);
    try {
      onDocumentChanged(await updateLegalDocument(document.kind, patch));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setPending(false);
    }
  };

  const channel: LegalChannel | null = tab === "common" ? null : tab;
  const text = document.texts.find((item) => item.locale === locale && item.channel === channel);
  const hasOverride = channel !== null && !!text && text.body.trim() !== "";
  const common = document.texts.find((item) => item.locale === locale && item.channel === null);

  const rows = [
    { channel: "BOT" as const, checked: document.show_in_bot, patch: (v: boolean) => ({ show_in_bot: v }) },
    { channel: "CABINET" as const, checked: document.show_in_cabinet, patch: (v: boolean) => ({ show_in_cabinet: v }) },
  ];

  return (
    <Card>
      <CardHeader
        icon={DOCUMENT_ICON}
        title={t(`settings.legal.kinds.${document.kind}`)}
        description={t(`settings.legal.kindDescriptions.${document.kind}`)}
      />
      <div className="mt-4 flex flex-col gap-1">
        {rows.map(({ channel: rowChannel, checked, patch }) => {
          const Icon = CHANNEL_ICONS[rowChannel];
          return (
            <div
              key={rowChannel}
              className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
            >
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                <Icon className="size-4" />
              </div>
              <p className="min-w-0 flex-1 text-[13px] font-medium text-foreground">
                {t(`settings.legal.showIn.${rowChannel}`)}
              </p>
              <div className="mr-1 flex">
                <Switch checked={checked} onChange={(v) => void toggle(patch(v))} disabled={!canUpdate || pending} />
              </div>
            </div>
          );
        })}
      </div>

      {(canSet || canRemove || text) && (
        <div className="mt-4 flex flex-col gap-3 border-t border-white/[0.08] pt-4">
          {locales.length > 1 && (
            <SegmentedPills
              value={locale}
              onChange={onLocaleChange}
              options={locales.map((code) => ({ value: code, label: code.toUpperCase() }))}
            />
          )}
          <DialogTabs
            activeKey={tab}
            onSelect={setTab}
            items={[
              { key: "common", label: t("settings.legal.tabs.common"), icon: COMMON_ICON },
              { key: "BOT", label: t("settings.legal.tabs.BOT"), icon: CHANNEL_ICONS.BOT },
              { key: "CABINET", label: t("settings.legal.tabs.CABINET"), icon: CHANNEL_ICONS.CABINET },
            ]}
          />
          <LegalTextEditor
            key={`${document.kind}:${locale}:${tab}:${text?.revision_id ?? 0}`}
            kind={document.kind}
            locale={locale}
            channel={channel}
            current={text}
            hasOverride={hasOverride}
            fallback={common}
            canSet={canSet}
            canRemove={canRemove}
            onChanged={onChanged}
          />
        </div>
      )}
    </Card>
  );
}
