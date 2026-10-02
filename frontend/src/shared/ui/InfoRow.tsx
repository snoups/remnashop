import { Check } from "lucide-react";
import { useState, type ComponentType, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { copyToClipboard } from "@shared/lib/clipboard";

interface InfoRowProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  children: ReactNode;
  copyValue?: string;
  /** machine values (IDs, codes, keys, emails, IPs, dates); words stay in the body font */
  mono?: boolean;
}

export function InfoRow({ icon: Icon, label, children, copyValue, mono = false }: InfoRowProps) {
  const { t } = useTranslation();
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = () => {
    if (!copyValue) return;
    void copyToClipboard(copyValue).then((copied) => {
      if (!copied) return;
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 1500);
    });
  };

  const left = (
    <div className="flex shrink-0 items-center gap-2.5 text-muted-foreground">
      <Icon className="size-[15px]" />
      <span className="text-[12.5px]">{label}</span>
    </div>
  );
  const right = (
    <div className={`flex min-w-0 items-center gap-1.5 text-[13px] font-semibold text-foreground ${mono ? "font-mono" : ""}`}>
      {children}
    </div>
  );

  if (copyValue) {
    return (
      <button
        type="button"
        onClick={handleCopy}
        className="relative flex w-full items-center justify-between gap-3 rounded-full px-2.5 h-9.5 text-left transition-colors hover:bg-white/[0.04]"
      >
        {left}
        {right}
        {isCopied && (
          <span className="absolute inset-0 flex items-center justify-center gap-1.5 rounded-full bg-black/35 text-[12.5px] font-medium text-success">
            <Check className="size-3.5" />
            {t("app.copied")}
          </span>
        )}
      </button>
    );
  }

  return (
    <div className="flex h-9.5 items-center justify-between gap-3 rounded-full px-2.5 transition-colors hover:bg-white/[0.04]">
      {left}
      {right}
    </div>
  );
}
