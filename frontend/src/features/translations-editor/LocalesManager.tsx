import { Check, ChevronDown, Globe } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";

import { addLocale, type ActiveLocalesResult, removeLocale } from "@entities/translations/api";
import { getErrorMessage } from "@shared/api/http";
import { localeLabel } from "@shared/i18n/locale-label";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { POPOVER_CLASS } from "@shared/ui/classes";

interface LocalesManagerProps {
  locales: ActiveLocalesResult;
  onChange: (locales: ActiveLocalesResult) => void;
}

/** The TranslatorHub's root locale -- the backend refuses to deactivate it. */
const DEFAULT_LOCALE = "en";

export function LocalesManager({ locales, onChange }: LocalesManagerProps) {
  const { t, i18n } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isOpen, setIsOpen] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  // Portalled and fixed: the editor panel clips its overflow, so a popover
  // positioned in place gets cut off at the panel's edge.
  // measured on open only -- reposition on scroll/resize if the page
  // ever scrolls out from under it.
  const [anchor, setAnchor] = useState<{ top: number; left: number; width: number } | null>(
    null,
  );

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const toggleOpen = () => {
    const trigger = triggerRef.current?.getBoundingClientRect();
    if (trigger) {
      setAnchor({ top: trigger.bottom + 8, left: trigger.left, width: trigger.width });
    }
    setIsOpen((open) => !open);
  };

  const byLabel = (a: string, b: string) => {
    if (a === DEFAULT_LOCALE || b === DEFAULT_LOCALE) return a === DEFAULT_LOCALE ? -1 : 1;
    return localeLabel(a, i18n.language).localeCompare(localeLabel(b, i18n.language));
  };
  const active = [...locales.active].sort(byLabel);
  const available = [...locales.available].sort(byLabel);

  const toggle = async (locale: string, isActive: boolean) => {
    setIsPending(true);
    try {
      onChange(isActive ? await removeLocale(locale) : await addLocale(locale));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsPending(false);
    }
  };

  const row = (locale: string, isActive: boolean) => (
    <button
      key={locale}
      type="button"
      role="option"
      aria-selected={isActive}
      disabled={locale === DEFAULT_LOCALE || isPending}
      onClick={() => void toggle(locale, isActive)}
      className="flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07] disabled:cursor-default disabled:opacity-60 disabled:hover:bg-transparent"
    >
      <span
        aria-hidden
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
  );

  return (
    <div ref={ref} onKeyDown={(e) => e.key === "Escape" && setIsOpen(false)}>
      <motion.button
        ref={triggerRef}
        type="button"
        onClick={toggleOpen}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        {...bounceTap(bounceStrength)}
        className="flex h-9 w-full cursor-pointer items-center gap-1.5 rounded-full border border-border px-4 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
      >
        <Globe className="size-3.5" />
        {t("dialogs.texts.languages", { total: active.length })}
        <ChevronDown
          className={`ml-auto size-3.5 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </motion.button>

      {/* body, not #dialog-root: that node sits inside the shell's
          backdrop-blur wrapper, which is a containing block for `fixed` and
          would offset these viewport coordinates. */}
      {createPortal(
        <AnimatePresence>
          {isOpen && anchor && (
            <motion.div
              ref={popoverRef}
              initial={{ opacity: 0, scale: 0.96, y: -4 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: -4 }}
              transition={{ duration: 0.15, ease: "easeOut" }}
              style={{ transformOrigin: "top", ...anchor }}
              role="listbox"
              aria-multiselectable
              onKeyDown={(e) => e.key === "Escape" && setIsOpen(false)}
              className={`${POPOVER_CLASS} fixed z-30 min-w-40 p-1.5`}
            >
              {/* the scroll lives inside the padding -- on the popover itself the
                  scrollbar column paints over the rounded right corners */}
              <div className="max-h-72 overflow-y-auto">
                {active.map((locale) => row(locale, true))}
                {active.length > 0 && available.length > 0 && (
                  <div aria-hidden className="my-1 h-px bg-white/[0.08]" />
                )}
                {available.map((locale) => row(locale, false))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </div>
  );
}
