import { RotateCcw } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { resetUserReferralCode, type ReferralStats } from "@entities/referrals/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

interface ResetReferralCodeButtonProps {
  userId: number;
  onReset: (stats: ReferralStats) => void;
  className?: string;
}

export function ResetReferralCodeButton({ userId, onReset, className }: ResetReferralCodeButtonProps) {
  const { t } = useTranslation();
  const [isConfirming, setIsConfirming] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const handleReset = async () => {
    setIsConfirming(false);
    setIsResetting(true);
    try {
      onReset(await resetUserReferralCode(userId));
      toast.success(t("referrals.stats.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("referrals.stats.resetError")));
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <>
      <Button
        variant="danger"
        type="button"
        className={className}
        disabled={isResetting}
        onClick={() => setIsConfirming(true)}
      >
        <RotateCcw className="size-3.5" />
        {t("referrals.stats.resetCode")}
      </Button>
      {isConfirming && (
        <ConfirmDialog
          title={t("referrals.stats.resetConfirmTitle")}
          message={t("referrals.stats.resetConfirmText")}
          confirmLabel={t("referrals.stats.resetCode")}
          cancelLabel={t("referrals.stats.resetCancel")}
          danger
          onConfirm={() => void handleReset()}
          onCancel={() => setIsConfirming(false)}
        />
      )}
    </>
  );
}
