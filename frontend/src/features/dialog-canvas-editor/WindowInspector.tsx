import { EyeOff, Image as ImageIcon, RotateCcw, Trash2, Unlink, Upload } from "lucide-react";
import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { useTranslation } from "react-i18next";

import { deleteBanner, restoreDefaultBanner, uploadBanner } from "@entities/banners/api";
import type { BannerMode, DialogWindow } from "@entities/dialogs/api";
import { bannerMode, bannerNameForMode, resetWindow, updateWindow } from "@entities/dialogs/api";
import { usePermissions } from "@entities/user/use-current-user";
import { InspectorDivider, InspectorHeader, InspectorNote, SwitchRow } from "@features/dialog-canvas-editor/InspectorParts";
import { getErrorMessage } from "@shared/api/http";
import { localeLabel } from "@shared/i18n/locale-label";
import { copyToClipboard } from "@shared/lib/clipboard";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { IconButton } from "@shared/ui/IconButton";
import { Pressable } from "@shared/ui/Pressable";
import { SegmentedPills } from "@shared/ui/SegmentedPills";

const ACCEPTED_FILE_TYPES = "image/jpeg,image/png,image/gif,image/webp";

const MODES: BannerMode[] = ["none", "shared", "own"];

/** The banner file the bot sends for this window in the preview's language: its own, or one it fell back to. */
export interface ShownBanner {
  url: string;
  name: string;
  locale: string;
}

interface WindowInspectorProps {
  window: DialogWindow;
  /** What the tree calls this window: its key is a uuid for a custom one. */
  label: string;
  /** The locale the preview is showing: a banner file belongs to one. */
  activeLocale: string | null;
  banner: ShownBanner | null;
  /** a custom window no button leads to: unreachable in the bot */
  isUnreachable: boolean;
  onWindowUpdated: (window: DialogWindow) => void;
  onBannerChanged: () => void;
  onDelete: () => void;
}

export function WindowInspector({
  window,
  label,
  activeLocale,
  banner,
  isUnreachable,
  onWindowUpdated,
  onBannerChanged,
  onDelete,
}: WindowInspectorProps) {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const canUpdate = permissions.includes("DIALOGS_WINDOWS_UPDATE");
  const canUpload = permissions.includes("BANNERS_UPLOAD");
  const canDeleteBanner = permissions.includes("BANNERS_DELETE");
  const canRestoreDefault = permissions.includes("BANNERS_RESTORE_DEFAULT");
  const canReset = permissions.includes("DIALOGS_WINDOWS_RESET");
  const canDelete = window.kind === "custom" && permissions.includes("DIALOGS_WINDOWS_DELETE");
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [isDeleteConfirmOpen, setIsDeleteConfirmOpen] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [nameDraft, setNameDraft] = useState(window.name ?? "");

  useEffect(() => {
    setNameDraft(window.name ?? "");
  }, [window.key, window.name]);

  const mode = bannerMode(window.banner_name);
  // a file for exactly this banner and language: the one an upload replaces and a delete removes
  const isOwnFile = banner !== null && banner.name === window.banner_name && banner.locale === activeLocale;
  const bannerHint = (): string | undefined => {
    if (mode === "none" || !activeLocale) return undefined;
    const locale = localeLabel(activeLocale, i18n.language);
    if (isOwnFile) {
      return t(mode === "shared" ? "dialogs.inspector.bannerHintShared" : "dialogs.inspector.bannerHintOwn", { locale });
    }
    if (banner === null) return t("dialogs.inspector.bannerMissing", { locale });
    const source = localeLabel(banner.locale, i18n.language);
    return bannerMode(banner.name) === "shared"
      ? t("dialogs.inspector.bannerFallbackShared", { locale, source })
      : t("dialogs.inspector.bannerFallbackLocale", { locale, source });
  };

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

  const copyKey = () =>
    void copyToClipboard(window.key).then((copied) => {
      if (copied) toast.success(t("dialogs.inspector.keyCopied"));
    });

  return (
    <>
      <InspectorHeader
        title={label}
        subtitle={
          <Pressable as="div" onClick={copyKey} className="w-fit cursor-pointer font-mono transition-colors hover:text-foreground">
            {window.key}
          </Pressable>
        }
      />
      {(!window.is_enabled || isUnreachable) && (
        <div className="flex flex-col gap-1.5">
          {!window.is_enabled && <InspectorNote icon={EyeOff} text={t("dialogs.inspector.disabledNote")} />}
          {isUnreachable && <InspectorNote icon={Unlink} warning text={t("dialogs.inspector.unlinkedNote")} />}
        </div>
      )}
      <InspectorDivider />

      <SwitchRow
        label={t("dialogs.inspector.enabledLabel")}
        checked={window.is_enabled}
        onChange={(value) => void handleEnabledChange(value)}
        disabled={!canUpdate || window.kind === "seed"}
      />

      {window.kind === "custom" && (
        <Field label={t("dialogs.inspector.nameLabel")} hint={t("dialogs.windowList.addWindowNameHint")}>
          <Input
            value={nameDraft}
            maxLength={128}
            disabled={!canUpdate}
            onChange={(event) => setNameDraft(event.target.value)}
            onBlur={() => void handleNameCommit()}
            onKeyDown={(event) => {
              if (event.key === "Enter") event.currentTarget.blur();
            }}
          />
        </Field>
      )}

      <Field
        label={t("dialogs.inspector.bannerLabel")}
        hint={bannerHint()}
      >
        <SegmentedPills
          stretch
          compact
          disabled={!canUpdate}
          value={mode}
          onChange={(item) => void handleModeChange(item)}
          options={MODES.map((item) => ({ value: item, label: t(`dialogs.inspector.bannerMode.${item}`) }))}
        />
        {mode !== "none" && (
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              className="hidden"
              onChange={(event) => void handleFileChange(event)}
            />
            {/* the picture itself shows on the preview; here only enough to tell it is there */}
            <div className="flex h-9 w-16 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-white/[0.04]">
              {banner ? (
                <img src={banner.url} alt="" className={`size-full object-cover ${isOwnFile ? "" : "opacity-50"}`} />
              ) : (
                <ImageIcon className="size-4 text-muted-foreground" />
              )}
            </div>
            {canUpload && (
              <Button
                variant="glass"
                icon={Upload}
                className="flex-1"
                disabled={!activeLocale}
                isLoading={isBusy}
                onClick={() => fileInputRef.current?.click()}
              >
                {t(isOwnFile ? "dialogs.inspector.bannerReplace" : "dialogs.inspector.bannerUpload")}
              </Button>
            )}
            {mode === "shared" && canRestoreDefault && (
              <IconButton size="9" disabled={isBusy} onClick={() => void handleRestoreDefault()}>
                <RotateCcw className="size-4" />
              </IconButton>
            )}
            {canDeleteBanner && isOwnFile && (
              <IconButton size="9" tone="danger" disabled={isBusy} onClick={() => void handleBannerDelete()}>
                <Trash2 className="size-4" />
              </IconButton>
            )}
          </div>
        )}
      </Field>

      {(canReset || canDelete) && (
        <>
          <InspectorDivider />
          <div className="flex flex-wrap gap-2">
            {canReset && (
              <Button variant="glassDanger" icon={RotateCcw} onClick={() => setIsResetConfirmOpen(true)}>
                {t("dialogs.inspector.resetWindow")}
              </Button>
            )}
            {canDelete && (
              <Button variant="glassDanger" icon={Trash2} onClick={() => setIsDeleteConfirmOpen(true)}>
                {t("dialogs.windowList.deleteWindow")}
              </Button>
            )}
          </div>
        </>
      )}

      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("dialogs.inspector.resetWindowTitle")}
          message={t("dialogs.inspector.resetWindowConfirm", { key: label })}
          confirmLabel={t("common.reset")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleResetWindow()}
          onCancel={() => setIsResetConfirmOpen(false)}
        />
      )}
      {isDeleteConfirmOpen && (
        <ConfirmDialog
          title={t("dialogs.windowList.deleteWindowTitle")}
          message={t("dialogs.windowList.deleteWindowConfirm", { key: label })}
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            setIsDeleteConfirmOpen(false);
            onDelete();
          }}
          onCancel={() => setIsDeleteConfirmOpen(false)}
        />
      )}
    </>
  );
}
