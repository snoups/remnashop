import { Image, Save, Send } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { BroadcastMediaType } from "@entities/broadcasts/api";
import { EmojiThumbnail } from "@features/dialog-canvas-editor/EmojiThumbnail";
import { TelegramHtml } from "@features/dialog-canvas-editor/TelegramHtml";
import { DAY_MS } from "@shared/lib/period";
import { Button } from "@shared/ui/Button";
import { GLASS_PLATE_CLASS } from "@shared/ui/classes";
import { EmptyState } from "@shared/ui/glass/EmptyState";

import type { EditorForm } from "@pages/broadcasts/editor/form";

const SAMPLE_DAYS_LEFT = 4;
const SAMPLE_PROMOCODE = "PROMO";

interface TelegramPreviewProps {
  form: EditorForm;
  locale: string;
  mediaType: BroadcastMediaType | null;
  mediaName: string | null;
  promocodeCode: string | null;
  /** a test of the saved broadcast to the actor's own Telegram; omitted without the right */
  onTest?: () => void;
  isTesting?: boolean;
  /** false until the broadcast is first saved: no text can be saved empty, so nothing to preview yet */
  isSaved: boolean;
}

export function TelegramPreview({ form, locale, mediaType, mediaName, promocodeCode, onTest, isTesting = false, isSaved }: TelegramPreviewProps) {
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
    // the email preview renders the same sample: PROMO stands in until a promocode is picked
    promocode: promocodeCode ?? SAMPLE_PROMOCODE,
  };
  const text = content?.text ?? "";
  const labels = content?.button_labels ?? [];
  // no unsubscribe button: the backend sends none in Telegram for now
  const buttons = form.buttons.map((_, index) => labels[index] || t("broadcasts.editor.buttons.label"));

  return (
    // a body only: the page's preview card (one Section for Telegram and email) frames it.
    // The dialog editor's canvas: the message, a line, the buttons
    <div className="mt-4 flex flex-col gap-3">
      {/* unsaved: the empty state, as the email preview's; the test button stays under it */}
      {!isSaved ? (
        <EmptyState icon={Save} text={t("broadcasts.editor.preview.saveFirst")} />
      ) : (
      <div className={`${GLASS_PLATE_CLASS} p-2.5`}>
        <div className="flex flex-col gap-1.5">
          {mediaType && (
            <div className="flex aspect-video w-full flex-col items-center justify-center gap-1.5 rounded-md border border-dashed border-white/[0.12] bg-white/[0.02] text-xs text-muted-foreground">
              <Image className="size-5" />
              {[t(`broadcasts.media.${mediaType}`), mediaName].filter(Boolean).join(" · ")}
            </div>
          )}
          <div className="whitespace-pre-wrap break-words px-2.5 py-2 text-sm leading-relaxed text-foreground">
            {text.trim() ? (
              <TelegramHtml value={text} values={values} />
            ) : (
              <span className="text-muted-foreground">{t("broadcasts.editor.preview.empty")}</span>
            )}
          </div>
        </div>
        {buttons.length > 0 && (
          <>
            <div className="my-2.5 h-px bg-white/[0.08]" />
            <div className="flex flex-col gap-1.5">
              {buttons.map((label, index) => (
                <span
                  key={index}
                  className="truncate rounded-lg border border-white/[0.12] px-3 py-2 text-center text-sm text-foreground"
                >
                  {form.buttons[index].icon_custom_emoji_id && (
                    <>
                      <EmojiThumbnail glyph="" customEmojiId={form.buttons[index].icon_custom_emoji_id} />{" "}
                    </>
                  )}
                  {label}
                </span>
              ))}
            </div>
          </>
        )}
      </div>
      )}
      {onTest && (
        // the test send under a line across the card, apart from the preview
        <div className="-mx-4 mt-1 border-t border-white/[0.08] px-4 pt-4">
          <Button
            variant="glass"
            type="button"
            className="w-full"
            onClick={onTest}
            disabled={!isSaved}
            isLoading={isTesting}
          >
            <Send className="size-4" />
            {t("broadcasts.editor.preview.testButton")}
          </Button>
        </div>
      )}
    </div>
  );
}
