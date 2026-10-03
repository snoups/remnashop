import { Image as ImageIcon, RotateCcw, Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import { deleteBanner, restoreDefaultBanner, uploadBanner } from "@entities/banners/api";
import type { BannerMode, DialogWindow } from "@entities/dialogs/api";
import { bannerMode, bannerNameForMode, resetWindow, updateWindow } from "@entities/dialogs/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { copyToClipboard } from "@shared/lib/clipboard";
import { toast } from "@shared/lib/toast";
import { PillTabs } from "@shared/ui/PillTabs";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { EDITOR_FIELD_CLASSNAME } from "@features/dialog-canvas-editor/field-classname";

const ACCEPTED_FILE_TYPES = "image/jpeg,image/png,image/gif,image/webp";

const MODES: BannerMode[] = ["none", "shared", "own"];

interface WindowInspectorProps {
  window: DialogWindow;
  /** What the tree calls this window: its key is a uuid for a custom one. */
  label: string;
  /** The locale the preview is showing: a banner file belongs to one. */
  activeLocale: string | null;
  bannerUrl: string | null;
  onWindowUpdated: (window: DialogWindow) => void;
  onBannerChanged: () => void;
}

export function WindowInspector({
  window,
  label,
  activeLocale,
  bannerUrl,
  onWindowUpdated,
  onBannerChanged,
}: WindowInspectorProps) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canUpdate = permissions.includes("DIALOGS_WINDOWS_UPDATE");
  const canUpload = permissions.includes("BANNERS_UPLOAD");
  const canDeleteBanner = permissions.includes("BANNERS_DELETE");
  const canRestoreDefault = permissions.includes("BANNERS_RESTORE_DEFAULT");
  const canReset = permissions.includes("DIALOGS_WINDOWS_RESET");
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [nameDraft, setNameDraft] = useState(window.name ?? "");

  useEffect(() => {
    setNameDraft(window.name ?? "");
  }, [window.key, window.name]);

  const mode = bannerMode(window.banner_name);

  const handleModeChange = async (next: BannerMode) => {
    if (next === mode) return;
    try {
      const updated = await updateWindow(window.key, {
        banner_name: bannerNameForMode(next, window.key),
      });
      onWindowUpdated(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const handleNameCommit = async () => {
    const next = nameDraft.trim();
    if (!next) {
      setNameDraft(window.name ?? "");
      return;
    }
    if (next === window.name) return;
    try {
      const updated = await updateWindow(window.key, { name: next });
      onWindowUpdated(updated);
      toast.success(t("common.saved"));
    } catch (err) {
      setNameDraft(window.name ?? "");
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const handleEnabledChange = async (value: boolean) => {
    try {
      const updated = await updateWindow(window.key, { is_enabled: value });
      onWindowUpdated(updated);
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
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
      toast.error(getErrorMessage(err, t("common.errors.generic")));
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
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  return (
    <div className="flex w-full flex-col gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-foreground">{label}</span>
          {window.kind === "seed" && (
            <span className="shrink-0 rounded-full border border-border bg-white/[0.04] px-1.5 py-px text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("dialogs.windowList.seedBadge")}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => {
            void copyToClipboard(window.key).then((copied) => {
              if (copied) toast.success(t("dialogs.inspector.keyCopied"));
            });
          }}
          className="block max-w-full truncate text-left font-mono text-[11.5px] text-muted-foreground transition-colors hover:text-foreground"
        >
          {window.key}
        </button>
      </div>

      {window.kind === "custom" && (
        <div className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium text-foreground/80">
            {t("dialogs.inspector.nameLabel")}
          </span>
          <input
            type="text"
            value={nameDraft}
            maxLength={128}
            disabled={!canUpdate}
            onChange={(event) => setNameDraft(event.target.value)}
            onBlur={() => void handleNameCommit()}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
            }}
            className={`${EDITOR_FIELD_CLASSNAME} border-glass-border`}
          />
        </div>
      )}

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] font-medium text-foreground/80">
            {t("dialogs.inspector.enabledLabel")}
          </span>
          <Switch
            checked={window.is_enabled}
            onChange={(value) => void handleEnabledChange(value)}
            disabled={!canUpdate || window.kind === "seed"}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-[13px] font-medium text-foreground/80">
          {t("dialogs.inspector.bannerLabel")}
        </span>
        <PillTabs
          items={MODES.map((item) => ({
            key: item,
            label: t(`dialogs.inspector.bannerMode.${item}`),
          }))}
          activeKey={mode}
          onSelect={(item) => void handleModeChange(item)}
          disabled={!canUpdate}
        />

        {mode !== "none" && (
          <div className="flex flex-col gap-2 rounded-xl border border-border bg-input/60 p-2">
            {/* With a banner the slot takes the picture's own ratio; empty, it
                holds 16:9 so the box does not sit there squashed. */}
            <div
              className={`relative flex items-center justify-center overflow-hidden rounded-lg ${
                bannerUrl ? "" : "aspect-video bg-white/[0.04]"
              }`}
            >
              {bannerUrl ? (
                <img src={bannerUrl} alt="" className="block w-full" />
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
                  {t(bannerUrl ? "dialogs.inspector.bannerReplace" : "dialogs.inspector.bannerUpload")}
                </button>
              )}
              {canDeleteBanner && bannerUrl && (
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => void handleBannerDelete()}
                  className="ml-auto flex size-6 cursor-pointer items-center justify-center rounded-full border border-error/20 bg-error/[0.08] text-error transition-colors hover:bg-error/15 disabled:opacity-40"
                >
                  <Trash2 className="size-3" />
                </button>
              )}
              {mode === "shared" && canRestoreDefault && (
                <button
                  type="button"
                  disabled={isBusy}
                  onClick={() => void handleRestoreDefault()}
                  className={`flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full border border-border text-foreground/70 transition-colors hover:bg-white/[0.06] disabled:opacity-40 ${
                    canDeleteBanner && bannerUrl ? "" : "ml-auto"
                  }`}
                >
                  <RotateCcw className="size-3" />
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      {canReset ? (
        <Button variant="outline" className="mt-auto" onClick={() => setIsResetConfirmOpen(true)}>
          <RotateCcw className="size-3.5" />
          {t("dialogs.inspector.resetWindow")}
        </Button>
      ) : null}

      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("dialogs.inspector.resetWindowTitle")}
          message={t("dialogs.inspector.resetWindowConfirm", { name: label })}
          confirmLabel={t("common.reset")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleResetWindow()}
          onCancel={() => setIsResetConfirmOpen(false)}
        />
      )}
    </div>
  );
}
