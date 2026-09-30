import { ChevronDown, Loader2 } from "lucide-react";
import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";

interface LoadMoreButtonProps {
  onClick: () => void;
  shown: number;
  total: number;
  isLoading?: boolean;
  className?: string;
}

export function LoadMoreButton({ onClick, shown, total, isLoading = false, className = "" }: LoadMoreButtonProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  return (
    <motion.button
      type="button"
      onClick={onClick}
      disabled={isLoading}
      {...bounceTap(bounceStrength)}
      className={`flex h-9 w-full items-center justify-center gap-1.5 rounded-full border border-border px-4 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5 disabled:cursor-not-allowed ${className}`}
    >
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
