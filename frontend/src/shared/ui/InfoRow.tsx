import { Check } from "lucide-react";
import { useState, type ComponentType, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { copyToClipboard } from "@shared/lib/clipboard";

const ROW_CLASS = "flex h-9 items-center justify-between gap-3 rounded-full px-2.5 transition-colors hover:bg-white/[0.04]";

interface InfoRowProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  children: ReactNode;
  copyValue?: string;
  /** before the value, stays clickable in a row that copies: an icon link */
  action?: ReactNode;
  /** machine values (IDs, codes, keys, emails, IPs, dates); words stay in the body font */
  mono?: boolean;
}

export function InfoRow({ icon: Icon, label, children, copyValue, action, mono = false }: InfoRowProps) {
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
      <span className="text-[12px]">{label}</span>
    </div>
  );
  const right = (
    <div className={`flex min-w-0 items-center gap-1.5 text-[13px] font-semibold text-foreground ${mono ? "font-mono" : ""}`}>
      {action && <span className="pointer-events-auto flex">{action}</span>}
      {children}
    </div>
  );

  if (copyValue) {
    return (
      <div className={`relative w-full text-left ${ROW_CLASS}`}>
        {/* a sibling under the content, not a parent: `action` may hold a link */}
        <button type="button" onClick={handleCopy} className="absolute inset-0 rounded-full" />
        <div className="pointer-events-none relative flex min-w-0 flex-1 items-center justify-between gap-3">
          {left}
          {right}
        </div>
        {isCopied && (
          <span className="absolute inset-0 flex items-center justify-center gap-1.5 rounded-full bg-black/35 text-[12px] font-medium text-primary">
            <Check className="size-3.5" />
            {t("app.copied")}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className={ROW_CLASS}>
      {left}
      {right}
    </div>
  );
}
