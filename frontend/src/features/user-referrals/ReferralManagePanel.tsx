import { Coins, Hash } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { adjustUserPoints, type ReferralStats } from "@entities/referrals/api";
import { getErrorMessage } from "@shared/api/http";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { Field } from "@shared/ui/Field";
import { TextInput } from "@shared/ui/TextInput";

const QUICK_DELTAS = [-50, -10, 10, 50];

interface ReferralManagePanelProps {
  userId: number;
  stats: ReferralStats;
  canAdjustPoints: boolean;
  onChanged: (stats: ReferralStats) => void;
}

export function ReferralManagePanel({ userId, stats, canAdjustPoints, onChanged }: ReferralManagePanelProps) {
  const { t, i18n } = useTranslation();
  const [delta, setDelta] = useState("");
  const [isAdjusting, setIsAdjusting] = useState(false);
  const points = Math.trunc(Number(stats.points));
  const parsedDelta = Number(delta.trim());
  const hasDelta = delta.trim() !== "" && Number.isInteger(parsedDelta) && parsedDelta !== 0;
  const invited = Object.values(stats.counts_by_level).reduce((sum, count) => sum + count, 0);

  const handleAdjust = async (event: FormEvent) => {
    event.preventDefault();
    if (!hasDelta) return;
    setIsAdjusting(true);
    try {
      onChanged(await adjustUserPoints(userId, String(parsedDelta)));
      setDelta("");
      toast.success(t("referrals.stats.adjustSaved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("referrals.stats.adjustError")));
    } finally {
      setIsAdjusting(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {canAdjustPoints && (
        <Card
          variant="form"
          icon={Coins}
          title={
            <>
              {t("referrals.stats.pointsLabel")}
              <span className="ml-auto text-[13px] font-normal normal-case tracking-normal text-muted-foreground">
                {t("referrals.dialog.onBalance")}{" "}
                <span className="text-[15px] font-bold tabular-nums text-foreground">
                  {points.toLocaleString(i18n.language)}
                </span>
              </span>
            </>
          }
        >
          <form onSubmit={(event) => void handleAdjust(event)} className="flex flex-col gap-2">
            <div className="flex items-end gap-2">
              <Field label={t("referrals.stats.adjustLabel")} htmlFor={`referral-adjust-${userId}`} className="flex-1">
                <TextInput
                  id={`referral-adjust-${userId}`}
                  type="number"
                  onKeyDown={(event) => event.key !== "-" && blockNonIntegerKeys(event)}
                  step="1"
                  value={delta}
                  onChange={(event) => setDelta(event.target.value)}
                  placeholder={t("referrals.stats.adjustPlaceholder")}
                />
              </Field>
              <Button variant="accent" size="field" type="submit" disabled={isAdjusting || !hasDelta}>
                {t("referrals.stats.adjustButton")}
              </Button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_DELTAS.map((value) => (
                <ChoiceChip
                  key={value}
                  active={hasDelta && parsedDelta === value}
                  onClick={() => setDelta(String(value))}
                >
                  {value > 0 ? `+${value}` : `−${-value}`}
                </ChoiceChip>
              ))}
            </div>
            {hasDelta && (
              <p className="text-[12px] text-muted-foreground">
                {t("referrals.dialog.afterAdjust")}{" "}
                <span className="font-semibold tabular-nums text-foreground">
                  {(points + parsedDelta).toLocaleString(i18n.language)}
                </span>
              </p>
            )}
          </form>
        </Card>
      )}

      <Card variant="form" title={t("referrals.stats.referralCodeLabel")} icon={Hash}>
        <div className="flex items-center justify-between gap-3">
          <span className="font-mono text-xl font-semibold tracking-wider text-foreground">
            {stats.referral_code ?? t("common.none")}
          </span>
          <span className="text-[12px] text-muted-foreground">{t("referrals.dialog.invitedByCode", { count: invited })}</span>
        </div>
        <p className="mt-3 text-[12.5px] leading-relaxed text-muted-foreground">{t("referrals.dialog.resetHint")}</p>
      </Card>
    </div>
  );
}
