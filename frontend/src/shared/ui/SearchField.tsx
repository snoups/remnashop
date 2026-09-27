import { Search } from "lucide-react";
import { motion } from "motion/react";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";

interface SearchFieldProps {
  id: string;
  label: string;
  placeholder: string;
  value: string;
  onChange: (value: string) => void;
}

export function SearchField({ id, label, placeholder, value, onChange }: SearchFieldProps) {
  const bounceStrength = useBounceStrength();

  return (
    <div className="flex min-w-40 flex-1 flex-col gap-1.5">
      <label htmlFor={id} className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </label>
      <motion.div className="group relative" {...bounceTap(bounceStrength)}>
        <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground transition-colors group-not-focus-within:group-hover:text-foreground group-focus-within:text-primary" />
        <input
          id={id}
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          className="w-full rounded-xl border border-border bg-input/60 py-2 pl-9 pr-3 text-sm text-foreground outline-none focus:border-primary"
        />
      </motion.div>
    </div>
  );
}
