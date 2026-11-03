import { Check, Languages } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "@shared/i18n";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { Pressable } from "@shared/ui/Pressable";

const POPOVER_MAX_HEIGHT = 120;

const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: "English",
  ru: "Русский",
};

/** capsule: an icon-only item of the header's glass capsule (36px, like the bell), no fill or edge */
export function LanguagePicker({ iconOnly = false, capsule = false }: { iconOnly?: boolean; capsule?: boolean }) {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const currentLanguage = (i18n.resolvedLanguage ?? "en") as SupportedLanguage;

  const handleSelect = (language: SupportedLanguage) => {
    void i18n.changeLanguage(language);
    setIsOpen(false);
  };

  return (
    <div ref={ref} className="relative shrink-0">
      <Pressable
        type="button"
        aria-label={LANGUAGE_LABELS[currentLanguage]}
        onClick={() => setIsOpen((open) => !open)}
        className={
          capsule
            ? "flex size-9 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
            : iconOnly
              ? "flex size-11 shrink-0 items-center justify-center rounded-full bg-white/[0.05] text-muted-foreground transition-colors hover:bg-white/[0.07] hover:text-foreground"
              : "glass-panel flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.06]"
        }
      >
        <Languages className={`${iconOnly ? "size-5" : "size-4"} shrink-0`} />
        {!iconOnly && !capsule && LANGUAGE_LABELS[currentLanguage]}
      </Pressable>
      {iconOnly && <span className="pointer-events-none absolute inset-0 rounded-full border border-glass-border" />}

      <PortalPopover
        open={isOpen}
        triggerRef={ref}
        popoverRef={popoverRef}
        align="right"
        maxHeight={POPOVER_MAX_HEIGHT}
        // 12px off the trigger: the mobile menu's big icon and the header capsule's
        extraGap={iconOnly || capsule ? 4 : 0}
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.85 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        glass={!iconOnly}
        className="min-w-44 p-1.5"
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <Pressable
            key={language}
            type="button"
            onClick={() => handleSelect(language)}
            className="flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]"
          >
            <span className="flex-1">{LANGUAGE_LABELS[language]}</span>
            {language === currentLanguage && <Check className="size-[15px] text-primary" />}
          </Pressable>
        ))}
      </PortalPopover>
    </div>
  );
}
