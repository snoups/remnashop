import { Save, Send } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { previewBroadcastEmail, sendTestBroadcastEmail } from "@entities/broadcasts/api";
import type { BroadcastEmailPreview } from "@entities/broadcasts/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { GLASS_PLATE_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Input } from "@shared/ui/glass/Input";

const DEBOUNCE_MS = 600;
// before the letter loads and measures itself
const FRAME_MIN_HEIGHT = 160;

interface EmailPreviewProps {
  /** false: behind the Telegram tab, still loading the letter */
  visible: boolean;
  broadcastId: number | null;
  /** changes on every save, which is what refreshes the preview */
  savedAt: string | null;
  dirty: boolean;
  locale: string;
  canPreview: boolean;
  canTestSend: boolean;
}

export function EmailPreview({ visible, broadcastId, savedAt, dirty, locale, canPreview, canTestSend }: EmailPreviewProps) {
  const { t } = useTranslation();
  const [preview, setPreview] = useState<BroadcastEmailPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [to, setTo] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [frameHeight, setFrameHeight] = useState(FRAME_MIN_HEIGHT);
  const frameRef = useRef<HTMLIFrameElement>(null);

  // a hidden frame has no layout: measured once it shows, before that paint
  const measure = () => {
    const doc = frameRef.current?.contentDocument;
    if (doc && doc.documentElement.scrollHeight > 0) setFrameHeight(doc.documentElement.scrollHeight);
  };
  useLayoutEffect(() => {
    if (visible) measure();
  }, [visible]);

  // another locale's letter or error must not stay under the new label
  useEffect(() => {
    setPreview(null);
    setError(null);
  }, [locale]);

  useEffect(() => {
    if (broadcastId === null || dirty || !canPreview) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      previewBroadcastEmail(broadcastId, locale)
        .then((next) => {
          if (controller.signal.aborted) return;
          setPreview(next);
          setError(null);
        })
        .catch((err: unknown) => {
          if (controller.signal.aborted) return;
          setPreview(null);
          setError(getErrorMessage(err, t("broadcasts.editor.emailPreview.error")));
        });
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [broadcastId, savedAt, dirty, locale, canPreview, t]);

  const handleTest = async () => {
    if (broadcastId === null) return;
    setIsSending(true);
    try {
      await sendTestBroadcastEmail(broadcastId, locale, to.trim());
      toast.success(t("broadcasts.editor.emailPreview.testSent"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSending(false);
    }
  };

  const isSaved = broadcastId !== null && !dirty;

  return (
    // a body only: the page's preview card (one Section for Telegram and email) frames it
    <div className={`mt-4 flex-col gap-3 ${visible ? "flex" : "hidden"}`}>
      {!isSaved && (
        <EmptyState icon={Save} text={t("broadcasts.editor.emailPreview.saveFirst")} />
      )}
      {error && <ErrorState text={error} />}
      {preview && (
        // an inbox's view of it: the subject on a header strip, the letter under it
        <div className={`${GLASS_PLATE_CLASS} overflow-hidden`}>
          <div className="border-b border-white/[0.08] px-3.5 py-2.5">
            <p className="truncate text-sm">
              <span className="text-muted-foreground">{t("broadcasts.editor.emailPreview.subjectLabel")} </span>
              <span className={preview.subject ? "font-medium text-foreground" : "text-muted-foreground"}>
                {preview.subject || t("broadcasts.editor.emailPreview.noSubject")}
              </span>
            </p>
          </div>
          {/* as tall as the letter; same-origin only to measure it, scripts stay off */}
          <iframe
            sandbox="allow-same-origin"
            srcDoc={preview.html}
            ref={frameRef}
            onLoad={measure}
            style={{ height: frameHeight }}
            className="block w-full bg-[#f4f4f5]"
          />
        </div>
      )}
      {canTestSend && (
        // under a line across the card: the address on a line of its own, the button full width under it
        <div className="-mx-4 mt-1 border-t border-white/[0.08] px-4 pt-4 flex flex-col gap-2">
          <Input
            type="email"
            value={to}
            onChange={(event) => setTo(event.target.value)}
            placeholder={t("broadcasts.editor.emailPreview.toPlaceholder")}
            autoComplete="off"
          />
          <Button
            variant="glass"
            type="button"
            className="w-full"
            onClick={() => void handleTest()}
            disabled={!isSaved || !to.includes("@")}
            isLoading={isSending}
          >
            <Send className="size-4" />
            {t("broadcasts.editor.emailPreview.testButton")}
          </Button>
        </div>
      )}
    </div>
  );
}
