import { Check, Languages } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "@shared/i18n";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";

const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: "English",
  ru: "Русский",
};

export function LanguagePicker() {
  const { t, i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useClickOutside(ref, isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, ref, () => setIsOpen(false));

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
        aria-label={t("language.label")}
        aria-haspopup="menu"
        aria-expanded={isOpen}
        onClick={() => setIsOpen((open) => !open)}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        style={{ willChange: "transform" }}
        className="flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-white/[0.05] px-3 text-[12.5px] font-semibold text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
      >
        <Languages className="size-4 shrink-0" />
        {currentLanguageLabel}
      </motion.button>
      <span aria-hidden className="pointer-events-none absolute inset-0 rounded-full border border-glass-border" />

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, scale: 0.85 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.85 }}
            transition={{ duration: 0.15, ease: "easeOut" }}
            style={{ transformOrigin: "top right" }}
            className="absolute right-0 z-20 mt-2 min-w-44 rounded-popover border border-white/[0.14] bg-popover/60 p-1.5 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            {SUPPORTED_LANGUAGES.map((language) => (
              <button
                key={language}
                type="button"
                role="menuitemradio"
                aria-checked={language === currentLanguage}
                onClick={() => handleSelect(language)}
                className="flex w-full items-center gap-2.5 rounded-full px-2.5 py-2 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]"
              >
                <span className="flex-1">{LANGUAGE_LABELS[language]}</span>
                {language === currentLanguage && <Check className="size-[15px] text-primary" />}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
