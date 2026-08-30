import { useState, type ComponentType, type ReactNode } from "react";

interface InfoRowProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  children: ReactNode;
  copyValue?: string;
}

export function InfoRow({ icon: Icon, label, children, copyValue }: InfoRowProps) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    if (!copyValue) return;
    navigator.clipboard.writeText(copyValue).catch(() => {});
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 1500);
  };

  const left = (
    <div className="flex items-center gap-2.5 text-muted-foreground">
      <Icon className="size-[15px]" />
      <span className="text-[12.5px]">{label}</span>
    </div>
  );
  const right = (
    <div className="flex items-center gap-1.5 font-mono text-[13px] font-semibold text-foreground">
      {children}
    </div>
  );

  if (copyValue) {
    return (
      <button
        type="button"
        onClick={handleCopy}
        className={`flex w-full items-center justify-between gap-3 rounded-full px-2.5 py-2.5 text-left transition-colors ${
          isCopied ? "bg-success/10" : "hover:bg-white/[0.04]"
        }`}
      >
        {left}
        {right}
      </button>
    );
  }

  return (
    <div className="flex items-center justify-between gap-3 rounded-full px-2.5 py-2.5 transition-colors hover:bg-white/[0.04]">
      {left}
      {right}
    </div>
  );
}
