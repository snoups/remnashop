import { Check, Languages } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "@shared/i18n";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { PortalPopover } from "@shared/ui/PortalPopover";

const POPOVER_MAX_HEIGHT = 120;

const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: "English",
  ru: "Русский",
};

export function LanguagePicker() {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const currentLanguage = (i18n.resolvedLanguage ?? "en") as SupportedLanguage;
  const currentLanguageLabel = currentLanguage.toUpperCase();

  const handleSelect = (language: SupportedLanguage) => {
    void i18n.changeLanguage(language);
    setIsOpen(false);
  };

  return (
    <div ref={ref} className="relative shrink-0">
      {/* Straight from the Motion for React gestures guide: whileHover/whileTap
          scale directly on the interactive element, will-change for a GPU
          layer. One deviation: the border lives on a static sibling instead
          of the button itself -- a rounded border stretched via `transform`
          rasterizes and visibly thickens at the curved ends in Chrome, with
          no combination of transform/will-change tricks avoiding it (see git
          log for what was tried). `inset-0` tracks the button's layout box,
          which `scale` never changes (it only repaints, doesn't reflow), so
          this stays put regardless of the button's hover/tap scale. */}
      <motion.button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        style={{ willChange: "transform" }}
        className="flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-white/[0.05] px-3 text-[12.5px] font-semibold text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
      >
        <Languages className="size-4 shrink-0" />
        {currentLanguageLabel}
      </motion.button>
      <span className="pointer-events-none absolute inset-0 rounded-full border border-glass-border" />

      <PortalPopover
        open={isOpen}
        triggerRef={ref}
        popoverRef={popoverRef}
        align="right"
        maxHeight={POPOVER_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.85 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="min-w-44 p-1.5"
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <button
            key={language}
            type="button"
            onClick={() => handleSelect(language)}
            className="flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]"
          >
            <span className="flex-1">{LANGUAGE_LABELS[language]}</span>
            {language === currentLanguage && <Check className="size-[15px] text-primary" />}
          </button>
        ))}
      </PortalPopover>
    </div>
  );
}
