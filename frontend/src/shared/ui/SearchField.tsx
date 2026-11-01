import { Search, X } from "lucide-react";
import { motion } from "motion/react";
import { useRef, type ComponentProps } from "react";

import { EYEBROW_CLASS } from "@shared/ui/classes";
import { IconButton } from "@shared/ui/IconButton";
import { Ripple } from "@shared/ui/Ripple";

interface SearchFieldProps {
  id: string;
  label: string;
  /** no visible label above the field */
  hideLabel?: boolean;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}

/** Clears a search input; the native (x) is hidden in app/styles.css since Firefox has none.
 * `size`/`className` put it at an equal inset from the field's top, bottom and right edge. */
export function SearchClearButton({
  onClear,
  size,
  className,
}: {
  onClear: () => void;
  size: ComponentProps<typeof IconButton>["size"];
  className: string;
}) {
  return (
    <IconButton size={size} onClick={onClear} className={className}>
      <X className="size-3.5" />
    </IconButton>
  );
}

// glass: filters and search, not form fields (those use TextInput)
export function SearchField({ id, label, hideLabel = false, placeholder, value, onChange }: SearchFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex min-w-40 flex-1 flex-col gap-1.5">
      {!hideLabel && <span className={EYEBROW_CLASS}>{label}</span>}
      <motion.label
        className="group relative flex w-full items-center gap-2.5 rounded-full border border-glass-border bg-white/[0.03] px-3 py-2 backdrop-blur-md transition-colors not-focus-within:hover:bg-white/[0.06] focus-within:border-primary"
      >
        <Ripple />
        <Search className="size-3.5 shrink-0 text-muted-foreground transition-colors group-not-focus-within:group-hover:text-foreground group-focus-within:text-primary" />
        <input
          ref={inputRef}
          id={id}
          type="search"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="w-full min-w-0 border-0 bg-transparent text-sm font-medium text-foreground outline-none focus-visible:outline-none placeholder:text-muted-foreground"
        />
        {value && (
          // 24px in a 36px-tall field: 6px inset top, bottom and right (px-3 minus 6)
          <SearchClearButton
            size="6"
            className="-my-0.5 -mr-1.5"
            onClear={() => {
              onChange("");
              inputRef.current?.focus();
            }}
          />
        )}
      </motion.label>
    </div>
  );
}
