import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { IconButton } from "@shared/ui/IconButton";

interface CopyableValueProps {
  /** omit when the surrounding Field/Card already names the value */
  label?: string;
  value: string;
  copyAria: string;
}

export function CopyableValue({ label, value, copyAria }: CopyableValueProps) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard?.writeText(value).catch(() => {});
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
  };

  return (
    <div className="flex flex-col gap-1">
      {label && <p className="text-[11px] font-medium text-muted-foreground">{label}</p>}
      <div
        onClick={() => {
          // drag-selecting the text shouldn't also copy it
          if (window.getSelection()?.isCollapsed !== false) handleCopy();
        }}
        className="group flex h-9.5 w-full cursor-pointer items-center justify-between gap-2 rounded-full border border-border bg-input/60 pl-3 pr-1"
      >
        <span className="min-w-0 truncate font-mono text-[13px] text-foreground">{value}</span>
        <IconButton size="7" tone="group"
          aria-label={copyAria}
        >
          {isCopied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
        </IconButton>
      </div>
    </div>
  );
}
