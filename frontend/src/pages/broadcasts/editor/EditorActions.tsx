import { Send, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/Button";
import { IconButton } from "@shared/ui/IconButton";
import { DateTimePickerField } from "@shared/ui/DateTimePickerField";

interface EditorActionsProps {
  isDirty: boolean;
  isBusy: boolean;
  canSave: boolean;
  canSend: boolean;
  /** nobody to send to yet: no customers picked, half a date range */
  sendBlocked: boolean;
  /** datetime-local value, empty for "now" */
  scheduleAt: string;
  onScheduleChange: (value: string) => void;
  onSave: () => void;
  onSend: () => void;
  /** null: nothing saved yet, or no permission */
  onDelete: (() => void) | null;
}

/** The editor's actions, laid out in its title bar: delete, save, when, send. */
export function EditorActions({
  isDirty,
  isBusy,
  canSave,
  canSend,
  sendBlocked,
  scheduleAt,
  onScheduleChange,
  onSave,
  onSend,
  onDelete,
}: EditorActionsProps) {
  const { t } = useTranslation();

  return (
    <>
      {onDelete && (
        <IconButton size="9" tone="glass" disabled={isBusy} onClick={onDelete}>
          {/* a glassDanger button's look, square: the bin in the error tone */}
          <Trash2 className="size-4 text-error" />
        </IconButton>
      )}
      {canSave && (
        <Button variant="glassAccent" disabled={isBusy || !isDirty} onClick={onSave}>
          {isDirty && <span className="size-1.5 shrink-0 rounded-full bg-warning" />}
          {t("common.save")}
        </Button>
      )}
      {canSend && (
        <>
          <DateTimePickerField
            value={scheduleAt}
            onChange={onScheduleChange}
            placeholder={t("broadcasts.editor.footer.sendAt")}
            className="w-52 shrink-0"
          />
          <Button variant="glassSolid" disabled={isBusy || sendBlocked} onClick={onSend}>
            <Send className="size-4" />
            {/* both labels stacked, the other one invisible: the button keeps the wider one's width */}
            <span className="inline-grid">
              {(["sendNow", "schedule"] as const).map((key) => (
                <span
                  key={key}
                  className={`col-start-1 row-start-1 ${(key === "schedule") === Boolean(scheduleAt) ? "" : "invisible"}`}
                >
                  {t(`broadcasts.editor.footer.${key}`)}
                </span>
              ))}
            </span>
          </Button>
        </>
      )}
    </>
  );
}
