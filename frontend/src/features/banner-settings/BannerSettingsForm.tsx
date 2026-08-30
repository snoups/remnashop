import { Image as ImageIcon, Plus, Upload, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState, type ChangeEvent, type MouseEvent } from "react";
import { useTranslation } from "react-i18next";

import { getErrorMessage } from "@shared/api/http";
import {
  type BannerMeta,
  deleteBanner,
  fetchBannerImageBlob,
  listBanners,
  uploadBanner,
} from "@entities/banners/api";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";

const BANNER_NAMES = [
  "default",
  "menu",
  "dashboard",
  "subscription",
  "referral",
  "promocode",
  "devices",
] as const;

const ACCEPTED_FILE_TYPES = "image/jpeg,image/png,image/gif,image/webp";

function bannerKey(name: string, locale: string): string {
  return `${name}:${locale}`;
}

interface LocaleTabProps {
  locale: string;
  isActive: boolean;
  onSelect: () => void;
}

function LocaleTab({ locale, isActive, onSelect }: LocaleTabProps) {
  const bounceStrength = useBounceStrength();

  return (
    <motion.button
      type="button"
      onClick={onSelect}
      className="group relative isolate block rounded-full text-sm font-medium"
      initial="rest"
      whileHover="hover"
      whileTap="tap"
    >
      <motion.span
        aria-hidden
        variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
        transition={{ type: "spring", stiffness: 500, damping: 15 }}
        className={`absolute inset-0 rounded-full transition-colors ${
          isActive ? "bg-accent" : "group-hover:bg-white/[0.06]"
        }`}
      />
      <span
        className={`relative z-10 block px-4 py-1.5 ${isActive ? "text-primary" : "text-foreground/80"}`}
      >
        {locale.toUpperCase()}
      </span>
    </motion.button>
  );
}

interface BannerCellProps {
  name: string;
  locale: string;
  meta: BannerMeta | undefined;
  onChanged: () => void;
}

function BannerCell({ name, locale, meta, onChanged }: BannerCellProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  useEffect(() => {
    if (!meta) {
      setPreviewUrl(null);
      return;
    }

    let cancelled = false;
    let objectUrl: string | null = null;

    fetchBannerImageBlob(name, locale)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPreviewUrl(objectUrl);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [name, locale, meta]);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;

    setIsBusy(true);
    try {
      await uploadBanner(name, locale, file);
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.banners.uploadError")));
    } finally {
      setIsBusy(false);
    }
  };

  const handleDelete = async (event: MouseEvent) => {
    event.stopPropagation();
    setIsBusy(true);
    try {
      await deleteBanner(name, locale);
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.banners.deleteError")));
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <motion.button
      type="button"
      onClick={() => fileInputRef.current?.click()}
      disabled={isBusy}
      {...bounceTap(bounceStrength, -0.02)}
      className="group relative aspect-video w-full overflow-hidden rounded-xl border border-border bg-input/60 text-left disabled:cursor-not-allowed disabled:opacity-60"
    >
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPTED_FILE_TYPES}
        className="hidden"
        onChange={(event) => void handleFileChange(event)}
      />

      {previewUrl ? (
        <>
          <img
            src={previewUrl}
            alt=""
            aria-hidden
            className="absolute inset-0 h-full w-full scale-110 object-cover blur-xl"
          />
          <div className="absolute inset-0 bg-black/25" />
          <img src={previewUrl} alt="" className="absolute inset-0 h-full w-full object-contain" />
          <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-black/60 to-transparent" />
        </>
      ) : (
        <div className="flex h-full w-full items-center justify-center border border-dashed border-border/80">
          <Plus className="size-5 text-muted-foreground transition-opacity group-hover:opacity-0" />
        </div>
      )}

      <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center gap-1.5 bg-black/55 opacity-0 transition-opacity group-hover:opacity-100">
        <Upload className="size-3.5 text-white" />
        <span className="text-[11px] font-semibold text-white">
          {meta ? t("settings.banners.replace") : t("settings.banners.upload")}
        </span>
      </div>

      {previewUrl && (
        <button
          type="button"
          onClick={(event) => void handleDelete(event)}
          aria-label={t("settings.banners.delete")}
          className="absolute right-1.5 top-1.5 z-20 flex size-5 items-center justify-center rounded-full bg-black/55 text-white transition-colors hover:bg-black/75"
        >
          <X className="size-3" />
        </button>
      )}

      <span
        className={`absolute bottom-1.5 left-2 z-20 text-[11px] font-semibold ${
          previewUrl ? "text-white [text-shadow:0_1px_2px_rgba(0,0,0,0.5)]" : "text-muted-foreground"
        }`}
      >
        {name.toUpperCase()}
      </span>
    </motion.button>
  );
}

export function BannerSettingsForm() {
  const { t } = useTranslation();
  const [state, reload] = useAsyncResource(listBanners);
  const [activeLocale, setActiveLocale] = useState<string | null>(null);

  const locales = state.kind === "ready" ? state.data.available_locales : [];
  const currentLocale = activeLocale && locales.includes(activeLocale) ? activeLocale : locales[0];

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <ImageIcon className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("settings.banners.title")}</h2>
          <p className="text-[12.5px] text-muted-foreground">{t("settings.banners.description")}</p>
        </div>
      </div>

      <div className="mt-4 flex flex-col gap-4">
        {state.kind === "loading" && (
          <p className="text-sm text-muted-foreground">{t("settings.banners.loading")}</p>
        )}
        {state.kind === "error" && (
          <p className="text-sm text-error">{t("settings.banners.loadError")}</p>
        )}
        {state.kind === "ready" && currentLocale && (
          <>
            <nav className="inline-flex w-fit gap-1 rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md">
              {locales.map((locale) => (
                <LocaleTab
                  key={locale}
                  locale={locale}
                  isActive={locale === currentLocale}
                  onSelect={() => setActiveLocale(locale)}
                />
              ))}
            </nav>

            <div className="grid grid-cols-4 gap-3">
              {BANNER_NAMES.map((name) => (
                <BannerCell
                  key={name}
                  name={name}
                  locale={currentLocale}
                  meta={state.data.banners.find(
                    (banner) =>
                      bannerKey(banner.name, banner.locale) === bannerKey(name, currentLocale),
                  )}
                  onChanged={reload}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
