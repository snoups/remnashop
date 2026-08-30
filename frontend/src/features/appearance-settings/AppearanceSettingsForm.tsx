import { Palette, Upload, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  type AppearanceImageKind,
  appearanceImageUrl,
  deleteAppearanceImage,
  getAppearance,
  resetAppearanceSettings,
  updateAppearance,
  uploadAppearanceImage,
} from "@entities/appearance/api";
import { getErrorMessage } from "@shared/api/http";
import { useAppearancePreview, useReloadAppearance } from "@entities/appearance/use-appearance";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { DEFAULT_ACCENT_COLOR, DEFAULT_SHADER_PALETTE_HEX, hexToHueDegrees, hueRotateHex } from "@shared/lib/color";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useCurrentUser } from "@entities/user/use-current-user";
import { toast } from "@shared/lib/toast";
import { ColorPickerField } from "@shared/ui/ColorPickerField";
import { Switch } from "@shared/ui/Switch";

const ACCEPTED_FILE_TYPES = "image/jpeg,image/png,image/webp";
const HEX_COLOR_PATTERN = /^#[0-9a-f]{6}$/i;

// A handful of common, high-contrast accent choices -- a shortcut for admins
// who don't want to fiddle with the picker. The picker itself still covers
// anything else.
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

// The 4 cosine-gradient coefficients ShaderBackground's uColourPalette
// uniform expects, in order -- see app/shaderState.ts.
const SHADER_PALETTE_KEYS = ["base", "amplitude", "frequency", "phase"] as const;

interface ImageSlotProps {
  kind: AppearanceImageKind;
  hasImage: boolean;
  label: string;
  canUpload: boolean;
  canDelete: boolean;
  onChanged: () => void;
}

function ImageSlot({ kind, hasImage, label, canUpload, canDelete, onChanged }: ImageSlotProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isBusy, setIsBusy] = useState(false);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setIsBusy(true);
    try {
      await uploadAppearanceImage(kind, file);
      onChanged();
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
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.appearance.deleteError")));
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <span className="text-[12.5px] font-semibold text-muted-foreground">{label}</span>
      <div className="relative flex aspect-video w-40 items-center justify-center overflow-hidden rounded-xl border border-border bg-input/60">
        {hasImage ? (
          <img src={appearanceImageUrl(kind)} alt="" className="h-full w-full object-contain p-2" />
        ) : (
          <span className="text-[11px] text-muted-foreground">{t("settings.appearance.upload")}</span>
        )}
        {hasImage && canDelete && (
          <motion.button
            type="button"
            onClick={() => void handleDelete()}
            disabled={isBusy}
            aria-label={t("settings.appearance.delete")}
            {...bounceTap(bounceStrength)}
            className="absolute right-1.5 top-1.5 flex size-5 items-center justify-center rounded-full bg-black/55 text-white transition-colors hover:bg-black/75 disabled:opacity-60"
          >
            <X className="size-3" />
          </motion.button>
        )}
      </div>
      {canUpload && (
        <motion.label
          {...bounceTap(bounceStrength)}
          className="flex w-40 cursor-pointer items-center justify-center gap-1.5 rounded-full border border-border py-1.5 text-[12.5px] font-medium text-foreground transition-colors hover:bg-white/[0.06] aria-disabled:cursor-not-allowed aria-disabled:opacity-60"
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
  );
}

export function AppearanceSettingsForm() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, reload] = useAsyncResource(getAppearance);
  const reloadAppearance = useReloadAppearance();
  const { setPreviewColor, setPreviewPalette, setPreviewShaderEnabled } = useAppearancePreview();
  const userState = useCurrentUser();
  const permissions = userState.kind === "ready" ? userState.data.effective_permissions : [];
  const [brandName, setBrandName] = useState("");
  const [accentColor, setAccentColor] = useState(DEFAULT_ACCENT_COLOR);
  // The last custom (non-preset) color picked -- mirrors accentColor live
  // the moment it's a custom value, and stays put when a preset is picked
  // afterwards so you can jump back to it. Rendered as an extra swatch next
  // to the fixed presets.
  const [previousColor, setPreviousColor] = useState<string | null>(null);
  const [hexInput, setHexInput] = useState(DEFAULT_ACCENT_COLOR);
  const [colorTouched, setColorTouched] = useState(false);
  const [shaderPalette, setShaderPalette] = useState<string[]>([...DEFAULT_SHADER_PALETTE_HEX]);
  const [paletteTouched, setPaletteTouched] = useState(false);
  const [shaderEnabled, setShaderEnabled] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  useEffect(() => {
    if (state.kind !== "ready") return;
    const loadedColor = state.data.primary_color ?? DEFAULT_ACCENT_COLOR;
    setBrandName(state.data.brand_name ?? "");
    setAccentColor(loadedColor);
    setPreviousColor(ACCENT_COLOR_PRESETS.includes(loadedColor.toLowerCase()) ? null : loadedColor);
    setColorTouched(false);
    setShaderPalette(state.data.shader_palette ?? [...DEFAULT_SHADER_PALETTE_HEX]);
    setPaletteTouched(false);
    setShaderEnabled(state.data.shader_enabled);
  }, [state]);

  // Keeps the free-typed hex field in sync whenever accentColor changes for
  // any other reason (picker, a preset swatch, or a fresh load) -- and,
  // since it's the same setter, re-syncing after this field's own valid
  // commit is a harmless no-op, not a loop.
  useEffect(() => {
    setHexInput(accentColor);
  }, [accentColor]);

  // Previews the picked color across the whole dashboard (CSS tokens, shader
  // hue) without saving it -- clears back to the real, saved color once
  // colorTouched resets (a successful save or reset re-fetches and settles
  // colorTouched back to false, see the effect above).
  useEffect(() => {
    setPreviewColor(colorTouched ? accentColor : null);
  }, [accentColor, colorTouched, setPreviewColor]);

  // Same live-preview idea as accent color, for the shader's raw palette.
  useEffect(() => {
    setPreviewPalette(paletteTouched ? shaderPalette : null);
  }, [shaderPalette, paletteTouched, setPreviewPalette]);

  // Same idea, for the on/off toggle -- always mirrored (no "touched" gate)
  // since a boolean has no ambiguous "unset" state the way a color does.
  useEffect(() => {
    setPreviewShaderEnabled(shaderEnabled);
  }, [shaderEnabled, setPreviewShaderEnabled]);

  // Leaving the page without saving must not leave the rest of the dashboard
  // stuck showing an unsaved preview -- AppearanceProvider outlives this
  // component, so nothing else would ever clear it.
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

    // A manually-edited shader palette doesn't survive picking a new accent
    // color -- it resets to the defaults, live-previewed (and, if saved,
    // persisted) rotated to match the newly picked accent by the exact same
    // mechanism an untouched palette always goes through. Stays "touched" so
    // this reset actually overrides whatever custom palette might already be
    // saved on the backend, instead of silently falling back to it.
    if (paletteTouched) {
      setShaderPalette([...DEFAULT_SHADER_PALETTE_HEX]);
    }
  };

  const setPaletteColor = (index: number, value: string) => {
    setShaderPalette((current) => current.map((hex, i) => (i === index ? value : hex)));
    setPaletteTouched(true);
  };

  // How far the shader's rendered palette sits from these swatches' raw hex
  // right now -- the same rotation ShaderBackground applies at render time
  // (see app/shaderState.ts). Lets each swatch preview its actual on-canvas
  // color instead of always showing its unrotated stored value.
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
      reload();
      reloadAppearance();
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
      await resetAppearanceSettings();
      reload();
      reloadAppearance();
      toast.success(t("settings.appearance.resetSuccess"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.appearance.resetError")));
    } finally {
      setIsResetting(false);
    }
  };

  const handleImageChanged = () => {
    reload();
    reloadAppearance();
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Palette className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("settings.appearance.title")}</h2>
          {state.kind === "loading" && (
            <p className="text-[12.5px] text-muted-foreground">{t("settings.appearance.loading")}</p>
          )}
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("settings.appearance.description")}</p>
        </div>
      </div>

      {state.kind === "error" && (
        <p className="mt-4 text-sm text-error">{t("settings.appearance.loadError")}</p>
      )}

      {state.kind === "ready" && (
        <div className="mt-4 flex flex-col gap-6">
          {permissions.includes("APPEARANCE_SETTINGS_MANAGE") && (
            <form onSubmit={(event) => void handleSave(event)} className="flex flex-col gap-6">
              <div className="flex flex-col gap-2">
                <span className="text-[12.5px] font-semibold text-muted-foreground">
                  {t("settings.appearance.section.branding")}
                </span>
                <div className="flex flex-col gap-1">
                  <label htmlFor="appearance-brand-name" className="text-sm font-medium text-foreground/80">
                    {t("settings.appearance.brandNameLabel")}
                  </label>
                  <input
                    id="appearance-brand-name"
                    type="text"
                    value={brandName}
                    onChange={(event) => setBrandName(event.target.value)}
                    placeholder={t("settings.appearance.brandNamePlaceholder")}
                    maxLength={64}
                    className="w-56 rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                  />
                </div>
              </div>

              <span aria-hidden className="h-px bg-border" />

              <div className="flex flex-col gap-3 rounded-xl bg-white/[0.02] p-3">
                <span className="text-[12.5px] font-semibold text-muted-foreground">
                  {t("settings.appearance.section.accentColor")}
                </span>

                <div className="flex flex-col gap-1">
                  <label htmlFor="appearance-accent-hex" className="text-sm font-medium text-foreground/80">
                    {t("settings.appearance.accentColorLabel")}
                  </label>
                  <div className="flex items-center gap-2">
                    <ColorPickerField
                      value={accentColor}
                      onChange={setAccent}
                      ariaLabel={t("settings.appearance.accentColorLabel")}
                    />
                    <input
                      id="appearance-accent-hex"
                      type="text"
                      value={hexInput}
                      onChange={handleHexInputChange}
                      maxLength={7}
                      spellCheck={false}
                      className="w-24 rounded-xl border border-border bg-input/60 px-3 py-2 text-sm font-mono text-foreground outline-none focus:border-primary"
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-1.5">
                  <span className="text-[11px] font-semibold text-muted-foreground/70">
                    {t("settings.appearance.presetsLabel")}
                  </span>
                  <div className="flex flex-wrap items-center gap-2">
                    {ACCENT_COLOR_PRESETS.map((preset) => (
                      <motion.button
                        key={preset}
                        type="button"
                        onClick={() => setAccent(preset)}
                        aria-label={preset}
                        style={{ backgroundColor: preset }}
                        whileHover={{ scale: 1.15 }}
                        {...bounceTap(bounceStrength)}
                        className={`size-7 rounded-full border-2 ${
                          accentColor.toLowerCase() === preset ? "border-foreground" : "border-transparent"
                        }`}
                      />
                    ))}
                    {previousColor && (
                      <>
                        <span aria-hidden className="h-6 w-px bg-border" />
                        <motion.button
                          type="button"
                          onClick={() => setAccent(previousColor)}
                          aria-label={t("settings.appearance.previousColorLabel")}
                          title={t("settings.appearance.previousColorLabel")}
                          style={{ backgroundColor: previousColor }}
                          whileHover={{ scale: 1.15 }}
                          {...bounceTap(bounceStrength)}
                          className={`size-7 rounded-full border-2 ${
                            accentColor.toLowerCase() === previousColor.toLowerCase()
                              ? "border-foreground"
                              : "border-transparent"
                          }`}
                        />
                      </>
                    )}
                  </div>
                </div>

                <div className="flex flex-col gap-1.5 border-t border-white/[0.06] pt-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[11px] font-semibold text-muted-foreground/70">
                      {t("settings.appearance.shaderEnabledLabel")}
                    </span>
                    <Switch
                      checked={shaderEnabled}
                      onChange={setShaderEnabled}
                      ariaLabel={t("settings.appearance.shaderEnabledLabel")}
                    />
                  </div>
                  <span className="text-[11px] font-semibold text-muted-foreground/70">
                    {t("settings.appearance.shaderPaletteLabel")}
                  </span>
                  <div className="flex flex-wrap items-center gap-3">
                    {SHADER_PALETTE_KEYS.map((key, index) => {
                      const rawColor = shaderPalette[index] ?? DEFAULT_SHADER_PALETTE_HEX[index];
                      return (
                        <div key={key} className="flex flex-col items-center gap-1">
                          <ColorPickerField
                            value={rawColor}
                            onChange={(value) => setPaletteColor(index, value)}
                            displayValue={hueRotateHex(rawColor, shaderHueRadians)}
                            ariaLabel={t(`settings.appearance.shaderPalette.${key}`)}
                          />
                          <span className="text-[11px] text-muted-foreground">
                            {t(`settings.appearance.shaderPalette.${key}`)}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              <span aria-hidden className="h-px bg-border" />

              <div className="flex items-center gap-2">
                <motion.button
                  type="submit"
                  disabled={isSaving}
                  {...bounceTap(bounceStrength)}
                  className="w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t("settings.appearance.save")}
                </motion.button>
                {permissions.includes("APPEARANCE_SETTINGS_RESET") && (
                  <motion.button
                    type="button"
                    onClick={() => void handleReset()}
                    disabled={isResetting}
                    {...bounceTap(bounceStrength)}
                    className="w-fit rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {t("settings.appearance.reset")}
                  </motion.button>
                )}
              </div>
            </form>
          )}

          {(permissions.includes("APPEARANCE_LOGO_UPLOAD") ||
            permissions.includes("APPEARANCE_LOGO_DELETE") ||
            permissions.includes("APPEARANCE_FAVICON_UPLOAD") ||
            permissions.includes("APPEARANCE_FAVICON_DELETE")) && (
            <>
              {permissions.includes("APPEARANCE_SETTINGS_MANAGE") && (
                <span aria-hidden className="h-px bg-border" />
              )}
              <div className="flex flex-col gap-2">
                <span className="text-[12.5px] font-semibold text-muted-foreground">
                  {t("settings.appearance.section.images")}
                </span>
                <div className="flex flex-wrap gap-4">
                  {(permissions.includes("APPEARANCE_LOGO_UPLOAD") ||
                    permissions.includes("APPEARANCE_LOGO_DELETE")) && (
                    <ImageSlot
                      kind="logo"
                      hasImage={state.data.has_logo}
                      label={t("settings.appearance.logoLabel")}
                      canUpload={permissions.includes("APPEARANCE_LOGO_UPLOAD")}
                      canDelete={permissions.includes("APPEARANCE_LOGO_DELETE")}
                      onChanged={handleImageChanged}
                    />
                  )}
                  {(permissions.includes("APPEARANCE_FAVICON_UPLOAD") ||
                    permissions.includes("APPEARANCE_FAVICON_DELETE")) && (
                    <ImageSlot
                      kind="favicon"
                      hasImage={state.data.has_favicon}
                      label={t("settings.appearance.faviconLabel")}
                      canUpload={permissions.includes("APPEARANCE_FAVICON_UPLOAD")}
                      canDelete={permissions.includes("APPEARANCE_FAVICON_DELETE")}
                      onChanged={handleImageChanged}
                    />
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
