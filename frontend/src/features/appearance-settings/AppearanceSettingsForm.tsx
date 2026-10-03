import { Palette, RotateCcw, Upload, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type ChangeEvent, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  type AppearanceImageKind,
  type AppearanceSettings,
  appearanceImageUrl,
  deleteAppearanceImage,
  getAppearance,
  resetAppearanceSettings,
  updateAppearance,
  uploadAppearanceImage,
} from "@entities/appearance/api";
import { getErrorMessage } from "@shared/api/http";
import { useAppearancePreview, useReloadAppearance } from "@entities/appearance/use-appearance";
import { bounceTap } from "@shared/lib/bounceState";
import { DEFAULT_ACCENT_COLOR, DEFAULT_SHADER_PALETTE_HEX, hexToHueDegrees, hueRotateHex } from "@shared/lib/color";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { usePermissions } from "@entities/user/use-current-user";
import { toast } from "@shared/lib/toast";
import { BrandLogo } from "@shared/ui/BrandLogo";
import { ColorPickerField } from "@shared/ui/ColorPickerField";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { CardHeader } from "@shared/ui/CardHeader";

const SVG_MIME_TYPE = "image/svg+xml";
const ACCEPTED_FILE_TYPES = `image/jpeg,image/png,image/webp,${SVG_MIME_TYPE}`;
const HEX_COLOR_PATTERN = /^#[0-9a-f]{6}$/i;

// mirrors the backend's per-kind limits (upload_appearance_image.py)
const IMAGE_LIMITS: Record<AppearanceImageKind, { minSide: number; maxSide: number; maxKb: number }> = {
  logo: { minSide: 128, maxSide: 1024, maxKb: 1024 },
  favicon: { minSide: 32, maxSide: 512, maxKb: 256 },
};

const ACCENT_COLOR_PRESETS: readonly string[] = [
  "#22d3ee",
  "#3b82f6",
  "#6366f1",
  "#a855f7",
  "#ec4899",
  "#ef4444",
  "#f97316",
  "#f59e0b",
  "#22c55e",
  "#14b8a6",
];

// uColourPalette's cosine-gradient coefficients, in uniform order
const SHADER_PALETTE_KEYS = ["base", "amplitude", "frequency", "phase"] as const;


interface ImageSlotProps {
  kind: AppearanceImageKind;
  hasImage: boolean;
  label: string;
  hint: string;
  canUpload: boolean;
  canDelete: boolean;
  className?: string;
  onChanged: (hasImage: boolean) => void;
}

function ImageSlot({ kind, hasImage, label, hint, canUpload, canDelete, className = "", onChanged }: ImageSlotProps) {
  const { t } = useTranslation();
  const [isBusy, setIsBusy] = useState(false);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    const limits = IMAGE_LIMITS[kind];
    if (file.size > limits.maxKb * 1024) {
      toast.error(t("settings.appearance.imageTooLarge", { maxKb: limits.maxKb }));
      return;
    }

    setIsBusy(true);
    try {
      // Vector: no pixel size to check here; the server validates markup and aspect ratio.
      const bitmap = file.type === SVG_MIME_TYPE ? undefined : await createImageBitmap(file).catch(() => null);
      if (bitmap === null) {
        toast.error(t("settings.appearance.imageUnreadable"));
        return;
      }
      if (bitmap) {
        const { width, height } = bitmap;
        bitmap.close();
        if (width !== height) {
          toast.error(t("settings.appearance.imageNotSquare"));
          return;
        }
        if (width < limits.minSide || width > limits.maxSide) {
          toast.error(t("settings.appearance.imageSideOutOfRange", { min: limits.minSide, max: limits.maxSide }));
          return;
        }
      }
      await uploadAppearanceImage(kind, file);
      onChanged(true);
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.appearance.uploadError")));
    } finally {
      setIsBusy(false);
    }
  };

  const handleDelete = async () => {
    setIsBusy(true);
    try {
      await deleteAppearanceImage(kind);
      onChanged(false);
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.appearance.deleteError")));
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <Field label={label} className={className}>
      <div
        // 27px = 1px border + 8px inset + 18px (half the h-9 upload pill): the pill's ends sit concentric in the corners
        className={`relative flex aspect-square items-center justify-center overflow-hidden rounded-[27px] bg-input/60 ${
          hasImage ? "border border-border" : "border border-dashed border-white/[0.16]"
        }`}
      >
        {hasImage ? (
          <img src={appearanceImageUrl(kind)} alt="" className="h-full w-full object-contain p-11" />
        ) : (
          <>
            <BrandLogo className="size-1/2 text-primary" />
            <span className="absolute top-2 left-1/2 -translate-x-1/2 rounded-full bg-black/40 px-2 py-0.5 text-[11px] text-muted-foreground">
              {t("settings.appearance.defaultImage")}
            </span>
          </>
        )}
        {hasImage && canDelete && (
          <motion.button
            type="button"
            onClick={() => void handleDelete()}
            disabled={isBusy}
            {...bounceTap()}
            className="absolute right-3.5 top-3.5 flex size-6 items-center justify-center rounded-full bg-black/55 text-white transition-colors hover:bg-black/75 disabled:opacity-60"
          >
            <X className="size-3" />
          </motion.button>
        )}
        {canUpload && (
          <motion.label
            {...bounceTap()}
            data-disabled={isBusy || undefined}
            className="absolute inset-x-2 bottom-2 flex h-9 cursor-pointer items-center justify-center gap-1.5 rounded-full border border-white/[0.08] text-sm font-medium text-foreground/60 transition-colors hover:bg-white/[0.06] data-disabled:cursor-not-allowed data-disabled:opacity-60"
          >
            <input
              type="file"
              accept={ACCEPTED_FILE_TYPES}
              className="hidden"
              disabled={isBusy}
              onChange={(event) => void handleFileChange(event)}
            />
            <Upload className="size-3.5" />
            {hasImage ? t("settings.appearance.replace") : t("settings.appearance.upload")}
          </motion.label>
        )}
      </div>
      <span className="text-[12px] text-muted-foreground">{hint}</span>
    </Field>
  );
}

function Section({ children }: { children: ReactNode }) {
  return <div className="flex flex-col gap-4 rounded-xl border border-white/[0.08] bg-white/[0.02] p-3">{children}</div>;
}

export function AppearanceSettingsForm() {
  const { t } = useTranslation();
  const reloadAppearance = useReloadAppearance();
  const { setPreviewColor, setPreviewPalette, setPreviewShaderEnabled } = useAppearancePreview();
  const permissions = usePermissions();
  const [brandName, setBrandName] = useState("");
  const [accentColor, setAccentColor] = useState(DEFAULT_ACCENT_COLOR);
  // last non-preset pick, kept as an extra swatch after a preset replaces it
  const [previousColor, setPreviousColor] = useState<string | null>(null);
  const [hexInput, setHexInput] = useState(DEFAULT_ACCENT_COLOR);
  const [colorTouched, setColorTouched] = useState(false);
  const [shaderPalette, setShaderPalette] = useState<string[]>([...DEFAULT_SHADER_PALETTE_HEX]);
  const [paletteTouched, setPaletteTouched] = useState(false);
  const [shaderEnabled, setShaderEnabled] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);

  // seeded per section, on load or that section's reset only; a save or image
  // change would wipe the other section's unsaved edits
  const seedBranding = (data: AppearanceSettings) => {
    setBrandName(data.brand_name ?? "");
  };

  const seedColors = (data: AppearanceSettings) => {
    const loadedColor = data.primary_color ?? DEFAULT_ACCENT_COLOR;
    setAccentColor(loadedColor);
    setPreviousColor(ACCENT_COLOR_PRESETS.includes(loadedColor.toLowerCase()) ? null : loadedColor);
    setColorTouched(false);
    setShaderPalette(data.shader_palette ?? [...DEFAULT_SHADER_PALETTE_HEX]);
    setPaletteTouched(false);
    setShaderEnabled(data.shader_enabled);
  };

  const [state, , setData] = useAsyncResource(getAppearance, {
    onSuccess: (data) => {
      seedBranding(data);
      seedColors(data);
    },
  });

  // picker, preset or load changed the color: the hex field follows
  useEffect(() => {
    setHexInput(accentColor);
  }, [accentColor]);

  // live preview across the dashboard until a save or reset clears colorTouched
  useEffect(() => {
    setPreviewColor(colorTouched ? accentColor : null);
  }, [accentColor, colorTouched, setPreviewColor]);

  useEffect(() => {
    setPreviewPalette(paletteTouched ? shaderPalette : null);
  }, [shaderPalette, paletteTouched, setPreviewPalette]);

  // a boolean has no "unset" state, so no touched gate
  useEffect(() => {
    setPreviewShaderEnabled(shaderEnabled);
  }, [shaderEnabled, setPreviewShaderEnabled]);

  // AppearanceProvider outlives this form: leaving unsaved must drop the preview
  useEffect(() => {
    return () => {
      setPreviewColor(null);
      setPreviewPalette(null);
      setPreviewShaderEnabled(null);
    };
  }, [setPreviewColor, setPreviewPalette, setPreviewShaderEnabled]);

  const setAccent = (value: string) => {
    if (!ACCENT_COLOR_PRESETS.includes(value.toLowerCase())) {
      setPreviousColor(value);
    }
    setAccentColor(value);
    setColorTouched(true);

    // a new accent resets a custom palette to the defaults; stays touched so the
    // reset overrides a palette already saved on the backend
    if (paletteTouched) {
      setShaderPalette([...DEFAULT_SHADER_PALETTE_HEX]);
    }
  };

  const setPaletteColor = (index: number, value: string) => {
    setShaderPalette((current) => current.map((hex, i) => (i === index ? value : hex)));
    setPaletteTouched(true);
  };

  // the hue rotation the shader renders with, so swatches show their on-canvas color
  const shaderHueRadians = ((hexToHueDegrees(accentColor) - hexToHueDegrees(DEFAULT_ACCENT_COLOR)) * Math.PI) / 180;

  const handleHexInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setHexInput(value);
    if (HEX_COLOR_PATTERN.test(value)) setAccent(value.toLowerCase());
  };

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      await updateAppearance({
        brand_name: brandName.trim() || undefined,
        primary_color: colorTouched ? accentColor : undefined,
        shader_palette: paletteTouched ? shaderPalette : undefined,
        shader_enabled: shaderEnabled,
      });
      reloadAppearance();
      setColorTouched(false);
      setPaletteTouched(false);
      toast.success(t("settings.appearance.saveSuccess"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.appearance.saveError")));
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    setIsResetting(true);
    try {
      // Each image goes through its own delete endpoint so its permission still applies.
      if (state.kind === "ready" && state.data.has_logo && permissions.includes("APPEARANCE_LOGO_DELETE")) {
        await deleteAppearanceImage("logo");
      }
      if (state.kind === "ready" && state.data.has_favicon && permissions.includes("APPEARANCE_FAVICON_DELETE")) {
        await deleteAppearanceImage("favicon");
      }
      const data = await resetAppearanceSettings();
      seedBranding(data);
      seedColors(data);
      setData(data);
      reloadAppearance();
      toast.success(t("settings.appearance.resetSuccess"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.appearance.resetError")));
    } finally {
      setIsResetting(false);
    }
  };

  const handleImageChanged = (kind: AppearanceImageKind, hasImage: boolean) => {
    if (state.kind !== "ready") return;
    setData({ ...state.data, [kind === "logo" ? "has_logo" : "has_favicon"]: hasImage });
    reloadAppearance();
  };

  const canManage = permissions.includes("APPEARANCE_SETTINGS_MANAGE");
  const canReset = permissions.includes("APPEARANCE_SETTINGS_RESET");
  const canLogo = permissions.includes("APPEARANCE_LOGO_UPLOAD") || permissions.includes("APPEARANCE_LOGO_DELETE");
  const canFavicon =
    permissions.includes("APPEARANCE_FAVICON_UPLOAD") || permissions.includes("APPEARANCE_FAVICON_DELETE");

  const swatchClass = (active: boolean) =>
    `size-8 rounded-full ${active ? "outline-2 outline-offset-2 outline-muted-foreground" : "ring-1 ring-white/10"}`;

  return (
    <Card>
      <CardHeader
        icon={Palette}
        title={t("settings.appearance.dashboardTitle")}
        description={t("settings.appearance.dashboardDescription")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <p className="mt-4 text-sm text-error">{t("settings.appearance.loadError")}</p>}

      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSave(event)} className="mt-4 flex flex-col gap-4">
          <div className="grid gap-3 lg:grid-cols-2">
            {(canManage || canLogo || canFavicon) && (
              <Section>
                {canManage && (
                  <Field label={t("settings.appearance.brandNameLabel")} htmlFor="appearance-brand-name">
                    <TextInput
                      id="appearance-brand-name"
                      type="text"
                      value={brandName}
                      onChange={(event) => setBrandName(event.target.value)}
                      placeholder={t("settings.appearance.brandNamePlaceholder")}
                      maxLength={64}
                      className="w-full"
                    />
                  </Field>
                )}
                {(canLogo || canFavicon) && (
                  <div className="flex flex-wrap gap-4">
                    {canLogo && (
                      <ImageSlot
                        kind="logo"
                        hasImage={state.data.has_logo}
                        label={t("settings.appearance.logoLabel")}
                        hint={t("settings.appearance.logoHint")}
                        canUpload={permissions.includes("APPEARANCE_LOGO_UPLOAD")}
                        canDelete={permissions.includes("APPEARANCE_LOGO_DELETE")}
                        className="min-w-0 flex-1"
                        onChanged={(hasImage) => handleImageChanged("logo", hasImage)}
                      />
                    )}
                    {canFavicon && (
                      <ImageSlot
                        kind="favicon"
                        hasImage={state.data.has_favicon}
                        label={t("settings.appearance.faviconLabel")}
                        hint={t("settings.appearance.faviconHint")}
                        canUpload={permissions.includes("APPEARANCE_FAVICON_UPLOAD")}
                        canDelete={permissions.includes("APPEARANCE_FAVICON_DELETE")}
                        className="min-w-0 flex-1"
                        onChanged={(hasImage) => handleImageChanged("favicon", hasImage)}
                      />
                    )}
                  </div>
                )}
              </Section>
            )}

            {canManage && (
              <Section>
                <Field label={t("settings.appearance.accentColorLabel")} htmlFor="appearance-accent-hex">
                  <div className="flex items-center gap-3.5 rounded-xl bg-white/[0.03] p-3">
                    <div className="flex items-center gap-2">
                      <ColorPickerField
                        value={accentColor}
                        onChange={setAccent}
                      />
                      <TextInput
                        id="appearance-accent-hex"
                        type="text"
                        value={hexInput}
                        onChange={handleHexInputChange}
                        maxLength={7}
                        spellCheck={false}
                        className="w-28 font-mono"
                      />
                    </div>
                    {previousColor && (
                      <motion.button
                        type="button"
                        onClick={() => setAccent(previousColor)}
                        style={{ backgroundColor: previousColor }}
                        whileHover={{ scale: 1.15 }}
                        {...bounceTap()}
                        className={`ml-auto ${swatchClass(accentColor.toLowerCase() === previousColor.toLowerCase())}`}
                      />
                    )}
                  </div>
                </Field>

                <div className="flex flex-col gap-2.5">
                  <span className={EYEBROW_CLASS}>{t("settings.appearance.presetsLabel")}</span>
                  <div className="flex flex-wrap items-center gap-2.5">
                    {ACCENT_COLOR_PRESETS.map((preset) => (
                      <motion.button
                        key={preset}
                        type="button"
                        onClick={() => setAccent(preset)}
                        style={{ backgroundColor: preset }}
                        whileHover={{ scale: 1.15 }}
                        {...bounceTap()}
                        className={swatchClass(accentColor.toLowerCase() === preset)}
                      />
                    ))}
                  </div>
                </div>

                <div className="flex flex-col gap-2.5 border-t border-white/[0.06] pt-4">
                  <div className="flex items-center justify-between gap-3">
                    <span className={EYEBROW_CLASS}>{t("settings.appearance.shaderEnabledLabel")}</span>
                    <Switch
                      checked={shaderEnabled}
                      onChange={setShaderEnabled}
                    />
                  </div>
                  <div
                    className={`grid grid-cols-2 gap-2 transition-opacity ${shaderEnabled ? "" : "opacity-40"}`}
                  >
                    {SHADER_PALETTE_KEYS.map((key, index) => {
                      const rawColor = shaderPalette[index] ?? DEFAULT_SHADER_PALETTE_HEX[index];
                      const shownColor = hueRotateHex(rawColor, shaderHueRadians);
                      const defaultColor = DEFAULT_SHADER_PALETTE_HEX[index];
                      return (
                        <div key={key} className="flex items-center gap-2 rounded-xl bg-white/[0.03] px-2.5 py-2">
                          <ColorPickerField
                            value={rawColor}
                            onChange={(value) => setPaletteColor(index, value)}
                            displayValue={shownColor}
                          />
                          <div className="flex min-w-0 flex-col">
                            <span className="truncate text-[12.5px] font-medium text-foreground">
                              {t(`settings.appearance.shaderPalette.${key}`)}
                            </span>
                            <span className="font-mono text-[11px] text-muted-foreground">{shownColor}</span>
                          </div>
                          <motion.button
                            type="button"
                            onClick={() => setPaletteColor(index, defaultColor)}
                            disabled={rawColor.toLowerCase() === defaultColor}
                            {...bounceTap()}
                            className="ml-auto flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-full border border-border text-foreground/70 transition-colors hover:bg-white/[0.06] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-30 disabled:hover:bg-transparent disabled:hover:text-foreground/70"
                          >
                            <RotateCcw className="size-3.5" />
                          </motion.button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </Section>
            )}
          </div>
          {(canManage || canReset) && (
            <div className="flex items-center gap-2">
              {canManage && (
                <Button
                  variant="accent"
                  type="submit"
                  disabled={isSaving}
                >
                  {t("common.save")}
                </Button>
              )}
              {canReset && (
                <Button
                  variant="outline"
                  className="whitespace-nowrap"
                  type="button"
                  onClick={() => setIsResetConfirmOpen(true)}
                  disabled={isResetting}
                >
                  {t("common.reset")}
                </Button>
              )}
            </div>
          )}
        </form>
      )}

      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("settings.appearance.resetConfirmTitle")}
          message={t("settings.appearance.resetConfirmMessage")}
          confirmLabel={t("common.reset")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            setIsResetConfirmOpen(false);
            void handleReset();
          }}
          onCancel={() => setIsResetConfirmOpen(false)}
        />
      )}
    </Card>
  );
}
