import { ChevronDown, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";
import { Ripple } from "@shared/ui/Ripple";


interface LoadMoreButtonProps {
  onClick: () => void;
  shown: number;
  total: number;
  isLoading?: boolean;
  className?: string;
}

export function LoadMoreButton({ onClick, shown, total, isLoading = false, className = "" }: LoadMoreButtonProps) {
  const { t } = useTranslation();

  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={isLoading}
      className={`relative flex h-9 w-full items-center justify-center gap-1.5 rounded-full border border-glass-border bg-white/[0.03] px-4 text-[13px] font-medium text-foreground/80 transition-colors hover:bg-white/[0.06] disabled:cursor-not-allowed ${className}`}
    >
      <Ripple />
      {isLoading ? <Loader2 className="size-3.5 animate-spin" /> : <ChevronDown className="size-3.5" />}
      {isLoading ? t("pagination.loading") : t("pagination.loadMore")}
      {!isLoading && (
        <span className="tabular-nums text-muted-foreground">
          · {t("pagination.progress", { shown, total })}
        </span>
      )}
    </motion.button>
  );
}
