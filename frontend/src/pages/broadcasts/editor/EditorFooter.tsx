import { Send } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/Button";
import { TextInput } from "@shared/ui/TextInput";

interface EditorFooterProps {
  isDirty: boolean;
  savedAt: string | null;
  isBusy: boolean;
  canTest: boolean;
  canSave: boolean;
  canSend: boolean;
  /** nobody to send to yet: no customers picked, half a date range */
  sendBlocked: boolean;
  /** datetime-local value, empty for "now" */
  scheduleAt: string;
  onScheduleChange: (value: string) => void;
  onTest: () => void;
  onSave: () => void;
  onSend: () => void;
  /** null: nothing saved yet, or no permission */
  onDelete: (() => void) | null;
}

export function EditorFooter({
  isDirty,
  savedAt,
  isBusy,
  canTest,
  canSave,
  canSend,
  sendBlocked,
  scheduleAt,
  onScheduleChange,
  onTest,
  onSave,
  onSend,
  onDelete,
}: EditorFooterProps) {
  const { t, i18n } = useTranslation();
  const status = isDirty
    ? t("broadcasts.editor.footer.unsaved")
    : savedAt
      ? t("broadcasts.editor.footer.savedAt", {
          time: new Date(savedAt).toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" }),
        })
      : "";

  return (
    <div className="sticky bottom-0 z-10 rounded-2xl border border-glass-border bg-canvas/90 px-4 py-3 backdrop-blur-md">
      <div className="flex flex-wrap items-center gap-2.5">
        <span className={`text-[12.5px] ${isDirty ? "text-warning" : "text-muted-foreground"}`}>{status}</span>
        <div className="ml-auto flex flex-wrap items-center gap-2.5">
          {onDelete && (
            <Button variant="danger" disabled={isBusy} onClick={onDelete}>
              {t("common.delete")}
            </Button>
          )}
          {canTest && (
            <Button variant="outline" disabled={isBusy} onClick={onTest}>
              {t("broadcasts.editor.footer.test")}
            </Button>
          )}
          {canSave && (
            <Button variant="accent" disabled={isBusy || !isDirty} onClick={onSave}>
              {t("common.save")}
            </Button>
          )}
          {canSend && (
            <>
              <label className="flex items-center gap-2 text-[13px] text-muted-foreground">
                {t("broadcasts.editor.footer.when")}
                <TextInput
                  type="datetime-local"
                  value={scheduleAt}
                  onChange={(event) => onScheduleChange(event.target.value)}
                />
              </label>
              <Button variant="solid" disabled={isBusy || sendBlocked} onClick={onSend}>
                <Send className="size-3.5" />
                {t(scheduleAt ? "broadcasts.editor.footer.schedule" : "broadcasts.editor.footer.sendNow")}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
