import { Check, ChevronDown, Globe, Star } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { addLocale, type ActiveLocalesResult, removeLocale, setDefaultLocale } from "@entities/translations/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { localeLabel } from "@shared/i18n/locale-label";
import { bounceTap } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { PortalPopover } from "@shared/ui/PortalPopover";

// the list's max-h-72, same as SelectDropdown
const POPOVER_MAX_HEIGHT = 288;

interface LocalesManagerProps {
  locales: ActiveLocalesResult;
  onChange: (locales: ActiveLocalesResult) => void;
}

export function LocalesManager({ locales, onChange }: LocalesManagerProps) {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const [isOpen, setIsOpen] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const toggleOpen = () => setIsOpen((open) => !open);

  // the TranslatorHub's root locale; the backend refuses to deactivate it
  const defaultLocale = locales.default;
  const byLabel = (a: string, b: string) => {
    if (a === defaultLocale || b === defaultLocale) return a === defaultLocale ? -1 : 1;
    return localeLabel(a, i18n.language).localeCompare(localeLabel(b, i18n.language));
  };
  const active = [...locales.active].sort(byLabel);
  const available = [...locales.available].sort(byLabel);

  const run = async (action: () => Promise<ActiveLocalesResult>) => {
    setIsPending(true);
    try {
      onChange(await action());
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsPending(false);
    }
  };
  const canSetDefault = permissions.includes("LOCALES_DEFAULT_SET");

  const row = (locale: string, isActive: boolean) => (
    <div key={locale} className="flex items-center">
      <button
        type="button"
        disabled={
          locale === defaultLocale || isPending || !permissions.includes(isActive ? "LOCALES_REMOVE" : "LOCALES_ADD")
        }
        onClick={() => void run(() => (isActive ? removeLocale(locale) : addLocale(locale)))}
        className="flex h-9 min-w-0 flex-1 items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07] disabled:cursor-default disabled:opacity-60 disabled:hover:bg-transparent"
      >
        <span
          className={`flex size-4 shrink-0 items-center justify-center rounded-[5px] border transition-colors ${
            isActive ? "border-primary bg-primary/20 text-primary" : "border-white/[0.18]"
          }`}
        >
          {isActive && <Check className="size-3" />}
        </span>
        <span className="truncate">{localeLabel(locale, i18n.language)}</span>
        <span className="ml-auto shrink-0 text-[11px] uppercase tabular-nums opacity-60">
          {locale}
        </span>
      </button>
      {isActive && (
        <button
          type="button"
          disabled={locale === defaultLocale || isPending || !canSetDefault}
          onClick={() => void run(() => setDefaultLocale(locale))}
          className={`flex size-9 shrink-0 items-center justify-center rounded-popover-item transition-colors hover:bg-white/[0.07] disabled:cursor-default disabled:hover:bg-transparent ${
            locale === defaultLocale ? "text-primary" : "text-muted-foreground disabled:opacity-60"
          }`}
        >
          <Star className={`size-3.5 ${locale === defaultLocale ? "fill-current" : ""}`} />
        </button>
      )}
    </div>
  );

  return (
    <div ref={ref} onKeyDown={(e) => e.key === "Escape" && setIsOpen(false)}>
      <motion.button
        ref={triggerRef}
        type="button"
        onClick={toggleOpen}
        {...bounceTap()}
        // the PillTabs capsule next to it: same border, fill, text and hover
        className="flex h-9 w-full cursor-pointer items-center gap-1.5 rounded-full border border-glass-border bg-white/[0.03] px-4 text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.06]"
      >
        <Globe className="size-3.5" />
        {t("dialogs.texts.languages", { total: active.length })}
        <ChevronDown
          className={`ml-auto size-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </motion.button>

      <PortalPopover
        open={isOpen}
        triggerRef={triggerRef}
        popoverRef={popoverRef}
        align="stretch"
        maxHeight={POPOVER_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        onKeyDown={(e) => e.key === "Escape" && setIsOpen(false)}
        className="min-w-40 p-1.5"
>
        {/* the scroll lives inside the padding: on the popover itself the
            scrollbar column paints over the rounded right corners */}
        <div className="max-h-72 overflow-y-auto">
          {active.map((locale) => row(locale, true))}
          {active.length > 0 && available.length > 0 && (
            <div className="my-1 h-px bg-white/[0.08]" />
          )}
          {available.map((locale) => row(locale, false))}
        </div>
        <p className="mt-1 border-t border-white/[0.08] px-2.5 pt-2 pb-1 text-[11px] text-muted-foreground">
          {t("dialogs.texts.defaultLanguageHint")}
        </p>
      </PortalPopover>
    </div>
  );
}
