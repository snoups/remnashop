import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@shared/ui/Button";

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
    <Button
      variant="glass"
      icon={ChevronDown}
      isLoading={isLoading}
      onClick={onClick}
      className={`w-full ${className}`}
    >
      {isLoading ? t("pagination.loading") : t("pagination.loadMore")}
      {!isLoading && (
        <span className="tabular-nums text-muted-foreground">· {t("pagination.progress", { shown, total })}</span>
      )}
    </Button>
  );
}
