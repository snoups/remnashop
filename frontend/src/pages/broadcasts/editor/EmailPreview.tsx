import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { previewBroadcastEmail, sendTestBroadcastEmail } from "@entities/broadcasts/api";
import type { BroadcastEmailPreview } from "@entities/broadcasts/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { TextInput } from "@shared/ui/TextInput";

const DEBOUNCE_MS = 600;

interface EmailPreviewProps {
  broadcastId: number | null;
  /** changes on every save, which is what refreshes the preview */
  savedAt: string | null;
  dirty: boolean;
  locale: string;
  canPreview: boolean;
  canTestSend: boolean;
}

export function EmailPreview({ broadcastId, savedAt, dirty, locale, canPreview, canTestSend }: EmailPreviewProps) {
  const { t } = useTranslation();
  const [preview, setPreview] = useState<BroadcastEmailPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [to, setTo] = useState("");
  const [isSending, setIsSending] = useState(false);

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
    <Card className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className={EYEBROW_CLASS}>{t("broadcasts.editor.emailPreview.title")}</span>
        <span className="ml-auto text-[12px] text-muted-foreground">{locale.toUpperCase()}</span>
      </div>
      {!isSaved && (
        <p className="text-[12.5px] text-muted-foreground">{t("broadcasts.editor.emailPreview.saveFirst")}</p>
      )}
      {error && <p className="text-[12.5px] text-error">{error}</p>}
      {preview && (
        <>
          <div className="truncate text-[13px] font-semibold text-foreground">
            {preview.subject || t("broadcasts.editor.emailPreview.noSubject")}
          </div>
          <iframe
            sandbox=""
            srcDoc={preview.html}
            className="h-[480px] w-full rounded-xl bg-white"
          />
        </>
      )}
      {canTestSend && (
        <div className="flex items-center gap-2">
          <TextInput
            type="email"
            value={to}
            onChange={(event) => setTo(event.target.value)}
            placeholder={t("broadcasts.editor.emailPreview.toPlaceholder")}
            autoComplete="off"
            className="min-w-0 flex-1"
          />
          <Button
            variant="secondary"
            type="button"
            onClick={() => void handleTest()}
            disabled={isSending || !isSaved || !to.includes("@")}
          >
            {isSending ? t("broadcasts.editor.emailPreview.testSending") : t("broadcasts.editor.emailPreview.testButton")}
          </Button>
        </div>
      )}
    </Card>
  );
}
