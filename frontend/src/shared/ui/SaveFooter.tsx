import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/Button";

interface SaveFooterProps {
  dirty: boolean;
  saving: boolean;
  /** blocks saving on top of "nothing changed" (an invalid draft) */
  disabled?: boolean;
  /** the save does something with no edit made (the first push keys); no unsaved mark */
  hasWork?: boolean;
  /** omit inside a form: the button submits it */
  onSave?: () => void;
  /** buttons right after Save */
  beside?: ReactNode;
  /** no margin of its own: in a Row's fold-out, whose gap spaces it */
  flush?: boolean;
}

/** A settings card's one Save button, with the unsaved-changes mark beside it. */
export function SaveFooter({ dirty, saving, disabled = false, hasWork = false, onSave, beside, flush = false }: SaveFooterProps) {
  const { t } = useTranslation();
  return (
    <div className={`${flush ? "" : "mt-4"} flex flex-wrap items-center gap-3`}>
      <Button
        variant="glassAccent"
        className="w-fit"
        type={onSave ? "button" : "submit"}
        disabled={!(dirty || hasWork) || disabled}
        isLoading={saving}
        onClick={onSave}
      >
        {t("common.save")}
      </Button>
      {beside}
      {dirty && (
        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="size-1.5 shrink-0 rounded-full bg-warning" />
          {t("common.unsavedChanges")}
        </span>
      )}
    </div>
  );
}
