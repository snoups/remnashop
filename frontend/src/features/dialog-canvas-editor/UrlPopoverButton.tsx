import { useRef, useState } from "react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { Button } from "@shared/ui/Button";
import { IconButton } from "@shared/ui/IconButton";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { TextInput } from "@shared/ui/TextInput";

interface UrlPopoverButtonProps {
  icon: ComponentType<{ className?: string }>;
  /** an address the target format accepts */
  pattern: RegExp;
  disabled: boolean;
  onInsert: (url: string) => void;
}

export function UrlPopoverButton({ icon: Icon, pattern, disabled, onInsert }: UrlPopoverButtonProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [url, setUrl] = useState("https://");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  useClickOutside<HTMLElement>([triggerRef, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll<HTMLElement>(isOpen, popoverRef, () => setIsOpen(false));

  const submit = () => {
    if (!pattern.test(url.trim())) return;
    onInsert(url.trim());
    setIsOpen(false);
  };

  return (
    <>
      <IconButton
        ref={triggerRef}
        size="7"
        disabled={disabled}
        onMouseDown={(event) => event.preventDefault()}
        onClick={() => {
          setUrl("https://");
          setIsOpen(!isOpen);
        }}
      >
        <Icon className="size-4" />
      </IconButton>
      <PortalPopover
        open={isOpen}
        triggerRef={triggerRef}
        popoverRef={popoverRef}
        align="left"
        maxHeight={60}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="w-80 p-2"
      >
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <TextInput
            autoFocus
            type="text"
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://"
            className="min-w-0 flex-1"
          />
          <Button variant="secondary" size="field" type="submit">
            {t("common.add")}
          </Button>
        </form>
      </PortalPopover>
    </>
  );
}
