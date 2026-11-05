import { Braces, Search } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { VariableOption } from "@entities/dialogs/api";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { EYEBROW_CLASS, POPOVER_SCROLL_CLASS } from "@shared/ui/classes";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { SearchClearButton } from "@shared/ui/SearchField";
import { Pressable } from "@shared/ui/Pressable";

const POPOVER_MAX_HEIGHT = 340;
// below this a scan is quicker than typing
const SEARCH_THRESHOLD = 8;
const CATEGORY_ORDER = ["user", "subscription", "window"];

interface VariablePickerProps {
  variables: VariableOption[];
  /** How a picked variable reads in this field: `{ $name }` in text, `${name}` in a URL. */
  format: (name: string) => string;
  onPick: (token: string) => void;
  disabled?: boolean;
}

function categoryRank(category: string): number {
  const index = CATEGORY_ORDER.indexOf(category);
  return index === -1 ? CATEGORY_ORDER.length : index;
}

export function VariablePicker({ variables, format, onPick, disabled = false }: VariablePickerProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  useClickOutside<HTMLElement>([triggerRef, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll<HTMLElement>(isOpen, popoverRef, () => setIsOpen(false));

  const label = (name: string) => t(`dialogs.variables.${name}`, { defaultValue: name });
  const needle = query.trim().toLowerCase();
  const matching = variables.filter(
    ({ name }) => !needle || name.toLowerCase().includes(needle) || label(name).toLowerCase().includes(needle),
  );
  const groups = [...new Set(matching.map((v) => v.category))]
    .sort((a, b) => categoryRank(a) - categoryRank(b))
    .map((category) => ({ category, items: matching.filter((v) => v.category === category) }));

  const toggle = () => {
    setQuery("");
    setIsOpen(!isOpen);
  };

  return (
    <>
      <Pressable
        ref={triggerRef}
        type="button"
        disabled={disabled || variables.length === 0}
        // keeps the field's caret where it is, so the token lands there
        onMouseDown={(event) => event.preventDefault()}
        onClick={toggle}
        className="flex size-[26px] cursor-pointer items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-40"
      >
        <Braces className="size-[16px]" />
      </Pressable>

      <PortalPopover
        glass
        open={isOpen}
        triggerRef={triggerRef}
        popoverRef={popoverRef}
        align="right"
        maxHeight={POPOVER_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="w-60 p-1.5"
>
        {variables.length > SEARCH_THRESHOLD && (
          <label className="glass-well mb-1.5 flex h-8 items-center gap-2 rounded-full px-3">
            <Search className="size-3.5 shrink-0 text-muted-foreground" />
            <input
              autoFocus
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("dialogs.inspector.variableSearch")}
              className="w-full min-w-0 bg-transparent text-[12px] text-foreground outline-none placeholder:text-muted-foreground"
            />
            {/* 20px in the 30px inner height: 5px inset (px-3 minus 7) */}
            {query && <SearchClearButton size="5" className="-mr-[7px]" onClear={() => setQuery("")} />}
          </label>
        )}
        <div className={`max-h-72 ${POPOVER_SCROLL_CLASS}`}>
          {groups.length === 0 && (
            <p className="px-2.5 py-2 text-[12px] text-muted-foreground">{t("dialogs.inspector.variableEmpty")}</p>
          )}
          {groups.map(({ category, items }) => (
            <div key={category} className="mb-1 last:mb-0">
              <span className={`${EYEBROW_CLASS} block px-2.5 pb-1 pt-1.5`}>
                {t(`dialogs.variableCategories.${category}`, { defaultValue: category })}
              </span>
              {items.map(({ name }) => (
                <Pressable
                  key={name}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => {
                    onPick(format(name));
                    setIsOpen(false);
                  }}
                  className="flex w-full flex-col items-start rounded-popover-item px-2.5 py-1.5 text-left transition-colors hover:bg-white/[0.07]"
                >
                  <span className="text-[13px] font-medium text-foreground">{label(name)}</span>
                  <span className="font-mono text-[12px] text-muted-foreground">{format(name)}</span>
                </Pressable>
              ))}
            </div>
          ))}
        </div>
      </PortalPopover>
    </>
  );
}
