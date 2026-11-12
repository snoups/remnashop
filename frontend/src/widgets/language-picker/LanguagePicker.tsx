import { Check, Languages } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { SUPPORTED_LANGUAGES, type SupportedLanguage } from "@shared/i18n";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { Pressable } from "@shared/ui/Pressable";
import { MOBILE_NAV_ROW_CLASSNAME } from "@widgets/sidebar/nav-pill";

const POPOVER_MAX_HEIGHT = 120;

const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: "English",
  ru: "Русский",
};

/** capsule: an icon-only item of the header's glass capsule (36px, like the bell), no fill or edge;
 *  row: a row of the mobile menu */
export function LanguagePicker({ row = false, capsule = false }: { row?: boolean; capsule?: boolean }) {
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
        onClick={() => setIsOpen((open) => !open)}
        className={
          capsule
            ? "flex size-9 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
            : row
              ? MOBILE_NAV_ROW_CLASSNAME
              : "glass-panel flex h-9 shrink-0 items-center gap-1.5 rounded-full px-3.5 text-sm font-medium text-foreground transition-colors hover:bg-white/[0.06]"
        }
      >
        <Languages className="size-4 shrink-0" />
        {!capsule && LANGUAGE_LABELS[currentLanguage]}
      </Pressable>

      <PortalPopover
        open={isOpen}
        triggerRef={ref}
        popoverRef={popoverRef}
        align={row ? "left" : "right"}
        maxHeight={POPOVER_MAX_HEIGHT}
        // 12px off the trigger in the header capsule
        extraGap={capsule ? 4 : 0}
        initial={{ opacity: 0, scale: 0.85 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.85 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        glass={!row}
        className="min-w-44 p-1.5"
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <Pressable
            key={language}
            type="button"
            onClick={() => handleSelect(language)}
            className="flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-sm font-medium text-foreground transition-colors hover:bg-white/[0.07]"
          >
            <span className="flex-1">{LANGUAGE_LABELS[language]}</span>
            {language === currentLanguage && <Check className="size-[15px] text-primary" />}
          </Pressable>
        ))}
      </PortalPopover>
    </div>
  );
}
