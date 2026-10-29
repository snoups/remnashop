import { Image } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { BroadcastMediaType } from "@entities/broadcasts/api";
import { TelegramHtml } from "@features/dialog-canvas-editor/TelegramHtml";
import { DAY_MS } from "@shared/lib/period";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS } from "@shared/ui/classes";

import type { EditorForm } from "@pages/broadcasts/editor/form";

const SAMPLE_DAYS_LEFT = 4;

interface TelegramPreviewProps {
  form: EditorForm;
  locale: string;
  mediaType: BroadcastMediaType | null;
  mediaName: string | null;
  promocodeCode: string | null;
}

export function TelegramPreview({ form, locale, mediaType, mediaName, promocodeCode }: TelegramPreviewProps) {
  const { t, i18n } = useTranslation();
  const content = form.contents[locale] ?? form.contents[form.default_locale];
  const name = t("broadcasts.editor.preview.sampleName");
  const values: Record<string, string> = {
    name,
    username: "@anna",
    plan: "Pro",
    expire_date: new Date(Date.now() + SAMPLE_DAYS_LEFT * DAY_MS).toLocaleDateString(i18n.language),
    days_left: String(SAMPLE_DAYS_LEFT),
    bonus_days: "3",
    points: "120",
    promocode: promocodeCode ?? t("common.none"),
  };
  const text = content?.text ?? "";
  const labels = content?.button_labels ?? [];
  const buttons = [
    ...form.buttons.map((_, index) => labels[index] || t("broadcasts.editor.buttons.label")),
    ...(form.category === "MARKETING" ? [t("broadcasts.editor.preview.unsubscribe")] : []),
  ];

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className={EYEBROW_CLASS}>{t("broadcasts.editor.preview.title")}</span>
        <span className="ml-auto text-[12px] text-muted-foreground">
          {t("broadcasts.editor.preview.as", { name, locale: locale.toUpperCase() })}
        </span>
      </div>
      <div className="flex flex-col gap-1 rounded-2xl bg-[#0e1621] p-3.5">
        <div className="max-w-[300px] overflow-hidden rounded-[14px_14px_14px_4px] bg-[#182533]">
          {mediaType && (
            <div className="flex h-[150px] flex-col items-center justify-center gap-1.5 bg-white/[0.05] text-[12px] text-[#6f7aa3]">
              <Image className="size-5" />
              {[t(`broadcasts.media.${mediaType}`), mediaName].filter(Boolean).join(" · ")}
            </div>
          )}
          <div className="whitespace-pre-wrap break-words px-2.5 pb-1.5 pt-2 text-[13px] leading-[1.45] text-[#e8ecfb]">
            {text.trim() ? <TelegramHtml value={text} values={values} /> : <span className="text-[#6f7aa3]">{t("broadcasts.editor.preview.empty")}</span>}
          </div>
          <div className="px-2.5 pb-1.5 text-right text-[11px] text-[#6f7aa3]">
            {new Date().toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" })}
          </div>
        </div>
        {buttons.length > 0 && (
          <div className="flex max-w-[300px] flex-col gap-[3px]">
            {buttons.map((label, index) => (
              <span
                key={index}
                className="flex h-[34px] items-center justify-center truncate rounded-lg bg-[#182533]/85 px-2 text-[13px] text-[#e8ecfb]"
              >
                {label}
              </span>
            ))}
          </div>
        )}
      </div>
    </Card>
  );
}
