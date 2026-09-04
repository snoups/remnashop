import { Check, Copy } from "lucide-react";
import { useState } from "react";

interface CopyableValueProps {
  label: string;
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
    <div className="flex items-center justify-between gap-2 rounded-xl border border-border bg-input/60 px-3 py-2">
      <div className="min-w-0">
        <p className="text-[11px] font-medium text-muted-foreground">{label}</p>
        <p className="truncate font-mono text-[13px] text-foreground">{value}</p>
      </div>
      <button
        type="button"
        onClick={handleCopy}
        aria-label={copyAria}
        className="flex size-7 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
      >
        {isCopied ? <Check className="size-3.5 text-success" /> : <Copy className="size-3.5" />}
      </button>
    </div>
  );
}
