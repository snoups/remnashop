import { Image as ImageIcon, RotateCcw, Trash2, Upload } from "lucide-react";
import { useRef, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import { deleteBanner, restoreDefaultBanner, uploadBanner } from "@entities/banners/api";
import type { BannerMode, DialogWindow } from "@entities/dialogs/api";
import { bannerMode, bannerNameForMode, resetWindow, updateWindow } from "@entities/dialogs/api";
import { useCurrentUser } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Switch } from "@shared/ui/Switch";

const ACCEPTED_FILE_TYPES = "image/jpeg,image/png,image/gif,image/webp";

const MODES: BannerMode[] = ["none", "shared", "own"];

interface WindowInspectorProps {
  window: DialogWindow;
  /** The locale the preview is showing: a banner file belongs to one. */
  activeLocale: string | null;
  bannerUrl: string | null;
  onWindowUpdated: (window: DialogWindow) => void;
  onBannerChanged: () => void;
}

export function WindowInspector({
  window,
  activeLocale,
  bannerUrl,
  onWindowUpdated,
  onBannerChanged,
}: WindowInspectorProps) {
  const { t } = useTranslation();
  const currentUserState = useCurrentUser();
  const permissions = currentUserState.kind === "ready" ? currentUserState.data.effective_permissions : [];
  const canUpdate = permissions.includes("DIALOGS_WINDOWS_UPDATE");
  const canUpload = permissions.includes("BANNERS_UPLOAD");
  const canDeleteBanner = permissions.includes("BANNERS_DELETE");
  const canRestoreDefault = permissions.includes("BANNERS_RESTORE_DEFAULT");
  const canReset = permissions.includes("DIALOGS_WINDOWS_RESET");
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const mode = bannerMode(window.banner_name);

  const handleModeChange = async (next: BannerMode) => {
    if (next === mode) return;
    try {
      const updated = await updateWindow(window.key, {
        banner_name: bannerNameForMode(next, window.key),
      });
      onWindowUpdated(updated);
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

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    // Cleared so picking the same file twice in a row still fires.
    event.target.value = "";
    if (!file || !window.banner_name || !activeLocale) return;
    setIsBusy(true);
    try {
      await uploadBanner(window.banner_name, activeLocale, file);
      onBannerChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.banners.uploadError")));
    } finally {
      setIsBusy(false);
    }
  };

  const handleBannerDelete = async () => {
    if (!window.banner_name || !activeLocale) return;
    setIsBusy(true);
    try {
      await deleteBanner(window.banner_name, activeLocale);
      onBannerChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.banners.deleteError")));
    } finally {
      setIsBusy(false);
    }
  };

  const handleRestoreDefault = async () => {
    setIsBusy(true);
    try {
      await restoreDefaultBanner();
      onBannerChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsBusy(false);
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

  return (
    <div className="flex w-full flex-col gap-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-medium text-foreground/80">
            {t("dialogs.inspector.enabledLabel")}
          </span>
          <Switch
            checked={window.is_enabled}
            onChange={(value) => void handleEnabledChange(value)}
            disabled={!canUpdate}
            ariaLabel={t("dialogs.inspector.enabledLabel")}
          />
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {t("dialogs.inspector.enabledHint")}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-[13px] font-medium text-foreground/80">
          {t("dialogs.inspector.bannerLabel")}
        </span>
        <div className="flex gap-0.5 rounded-full bg-white/[0.05] p-0.5">
          {MODES.map((item) => (
            <button
              key={item}
              type="button"
              disabled={!canUpdate}
              onClick={() => void handleModeChange(item)}
              className={`flex-1 cursor-pointer rounded-full px-1 py-1.5 text-[12.5px] transition-colors disabled:cursor-not-allowed ${
                item === mode
                  ? "bg-accent font-medium text-primary"
                  : "text-foreground/40 hover:text-foreground/70"
              }`}
            >
              {t(`dialogs.inspector.bannerMode.${item}`)}
            </button>
          ))}
        </div>

        {mode !== "none" && (
          <div className="flex flex-col gap-2 rounded-xl border border-border bg-input/60 p-2">
            <div className="relative flex h-[72px] items-center justify-center overflow-hidden rounded-lg bg-white/[0.04]">
              {bannerUrl ? (
                <img src={bannerUrl} alt="" className="size-full object-cover" />
              ) : (
                <ImageIcon className="size-5 text-muted-foreground" />
              )}
              {activeLocale && (
                <span className="absolute left-2 top-2 rounded-full bg-black/45 px-2 py-0.5 text-[10px] font-semibold uppercase text-foreground/85">
                  {activeLocale}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_FILE_TYPES}
                className="hidden"
                onChange={(event) => void handleFileChange(event)}
              />
              {canUpload && (
                <button
                  type="button"
                  disabled={isBusy || !activeLocale}
                  onClick={() => fileInputRef.current?.click()}
                  className="flex cursor-pointer items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[11.5px] text-foreground/80 transition-colors hover:bg-white/[0.06] disabled:opacity-40"
                >
                  <Upload className="size-3" />
                  {t("dialogs.inspector.bannerReplace")}
                </button>
              )}
              {canDeleteBanner && bannerUrl && (
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => void handleBannerDelete()}
                  aria-label={t("dialogs.inspector.bannerDelete")}
                  className="flex size-6 cursor-pointer items-center justify-center rounded-full border border-error/20 bg-error/[0.08] text-error transition-colors hover:bg-error/15 disabled:opacity-40"
                >
                  <Trash2 className="size-3" />
                </button>
              )}
            </div>
          </div>
        )}

        <p className="text-xs leading-relaxed text-muted-foreground">
          {t(`dialogs.inspector.bannerHint.${mode}`)}
        </p>

        {mode === "shared" && canRestoreDefault && (
          <button
            type="button"
            disabled={isBusy}
            onClick={() => void handleRestoreDefault()}
            className="cursor-pointer self-start text-xs text-muted-foreground underline underline-offset-[3px] transition-colors hover:text-foreground/80 disabled:opacity-40"
          >
            {t("dialogs.inspector.bannerRestoreDefault")}
          </button>
        )}
      </div>

      {canReset ? (
        <button
          type="button"
          onClick={() => setIsResetConfirmOpen(true)}
          className="mt-auto flex cursor-pointer items-center justify-center gap-1.5 rounded-full border border-border px-3 py-2 text-[13px] text-foreground/80 transition-colors hover:bg-white/[0.06]"
        >
          <RotateCcw className="size-3.5" />
          {t("dialogs.inspector.resetWindow")}
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
    </div>
  );
}
