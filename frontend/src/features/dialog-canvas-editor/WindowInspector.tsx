import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { DialogWindow } from "@entities/dialogs/api";
import { BANNER_OPTIONS, resetAll, resetWindow, updateWindow } from "@entities/dialogs/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

interface WindowInspectorProps {
  window: DialogWindow;
  onWindowUpdated: (window: DialogWindow) => void;
  onResetAll: () => void;
}

export function WindowInspector({ window, onWindowUpdated, onResetAll }: WindowInspectorProps) {
  const { t } = useTranslation();
  const currentUserState = useCurrentUser();
  const permissions = currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canUpdate = permissions.includes("DIALOGS_WINDOWS_UPDATE");
  const canReset = permissions.includes("DIALOGS_WINDOWS_RESET");
  const canResetAll = permissions.includes("DIALOGS_WINDOWS_RESET_ALL");
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isResetAllConfirmOpen, setIsResetAllConfirmOpen] = useState(false);

  const handleBannerChange = async (value: string) => {
    try {
      const updated = await updateWindow(window.key, { banner_name: value || null });
      onWindowUpdated(updated);
      toast.success(t("dialogs.inspector.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleEnabledChange = async (value: boolean) => {
    try {
      const updated = await updateWindow(window.key, { is_enabled: value });
      onWindowUpdated(updated);
      toast.success(t("dialogs.inspector.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleResetWindow = async () => {
    setIsResetConfirmOpen(false);
    try {
      const updated = await resetWindow(window.key);
      onWindowUpdated(updated);
      toast.success(t("dialogs.inspector.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  const handleResetAll = async () => {
    setIsResetAllConfirmOpen(false);
    try {
      await resetAll();
      onResetAll();
      toast.success(t("dialogs.inspector.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    }
  };

  return (
    <div className="flex w-full shrink-0 flex-col gap-4 lg:w-64">
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
        <h3 className="mb-3 text-[13px] font-semibold text-foreground">
          {t("dialogs.inspector.windowTitle")}
        </h3>
        <label className="mb-3 block">
          <span className="mb-1 block text-[12px] text-muted-foreground">
            {t("dialogs.inspector.bannerLabel")}
          </span>
          <select
            className="w-full rounded-lg border border-white/[0.12] bg-white/[0.04] px-2.5 py-1.5 text-[13px] text-foreground disabled:opacity-50"
            value={window.banner_name ?? ""}
            disabled={!canUpdate}
            onChange={(event) => void handleBannerChange(event.target.value)}
          >
            {/* PUT /dialogs/windows/{key} treats banner_name:null as "no change", not "clear" -- so "None"
                is a display-only state for a window that has no banner, never a selectable target. */}
            <option value="" disabled>
              {t("dialogs.inspector.bannerNone")}
            </option>
            {BANNER_OPTIONS.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={window.is_enabled}
            disabled={!canUpdate}
            onChange={(event) => void handleEnabledChange(event.target.checked)}
          />
          <span className="text-[13px] text-foreground">{t("dialogs.inspector.enabledLabel")}</span>
        </label>
        <p className="mt-1 text-[11.5px] text-muted-foreground">{t("dialogs.inspector.enabledHint")}</p>
      </div>
      {canReset ? (
        <button
          type="button"
          onClick={() => setIsResetConfirmOpen(true)}
          className="rounded-full border border-white/[0.12] px-3 py-2 text-[12.5px] text-foreground/80 hover:bg-white/[0.06]"
        >
          {t("dialogs.inspector.resetWindow")}
        </button>
      ) : null}
      {canResetAll ? (
        <button
          type="button"
          onClick={() => setIsResetAllConfirmOpen(true)}
          className="rounded-full border border-white/[0.12] px-3 py-2 text-[12.5px] text-error hover:bg-white/[0.06]"
        >
          {t("dialogs.inspector.resetAll")}
        </button>
      ) : null}
      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("dialogs.inspector.resetWindow")}
          message={t("dialogs.inspector.resetWindowConfirm", { key: window.key })}
          confirmLabel={t("dialogs.inspector.resetWindowConfirmButton")}
          cancelLabel={t("dialogs.inspector.resetWindowCancelButton")}
          danger
          onConfirm={() => void handleResetWindow()}
          onCancel={() => setIsResetConfirmOpen(false)}
        />
      )}
      {isResetAllConfirmOpen && (
        <ConfirmDialog
          title={t("dialogs.inspector.resetAll")}
          message={t("dialogs.inspector.resetAllConfirm")}
          confirmLabel={t("dialogs.inspector.resetAllConfirmButton")}
          cancelLabel={t("dialogs.inspector.resetAllCancelButton")}
          danger
          onConfirm={() => void handleResetAll()}
          onCancel={() => setIsResetAllConfirmOpen(false)}
        />
      )}
    </div>
  );
}
