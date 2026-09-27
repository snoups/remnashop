import { AlertCircle, Gift, Loader2, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { adjustUserPoints, getUserReferralStats } from "@entities/referrals/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Modal, useModalClose } from "@shared/ui/Modal";

interface UserReferralsDialogProps {
  userId: number;
  userName: string;
  canAdjustPoints: boolean;
  onClose: () => void;
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="text-[12.5px] text-muted-foreground">{label}</span>
      <span className="truncate text-[13px] font-medium text-foreground">{value}</span>
    </div>
  );
}

export function UserReferralsDialog({ userId, userName, canAdjustPoints, onClose }: UserReferralsDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <UserReferralsDialogBody userId={userId} userName={userName} canAdjustPoints={canAdjustPoints} />
    </Modal>
  );
}

function UserReferralsDialogBody({
  userId,
  userName,
  canAdjustPoints,
}: Pick<UserReferralsDialogProps, "userId" | "userName" | "canAdjustPoints">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [state, , setData] = useAsyncResource((signal) => getUserReferralStats(userId, signal));
  const [delta, setDelta] = useState("");
  const [isAdjusting, setIsAdjusting] = useState(false);
  const none = t("referrals.stats.none");

  const handleAdjust = async (event: FormEvent) => {
    event.preventDefault();
    if (!delta.trim()) return;
    setIsAdjusting(true);
    try {
      const updated = await adjustUserPoints(userId, delta.trim());
      setData(updated);
      setDelta("");
      toast.success(t("referrals.stats.adjustSaved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("referrals.stats.adjustError")));
    } finally {
      setIsAdjusting(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Gift className="size-4" />
          </div>
          <span className="truncate">{userName}</span>
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("referrals.stats.close")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      {state.kind === "loading" && (
        <div className="flex flex-col items-center gap-2 px-5 py-10 text-muted-foreground">
          <Loader2 className="size-5 animate-spin" />
        </div>
      )}
      {state.kind === "error" && (
        <div className="flex flex-col items-center gap-2 px-5 py-10 text-error">
          <AlertCircle className="size-5" />
          <p className="text-sm">{t("referrals.stats.loadError")}</p>
        </div>
      )}
      {state.kind === "ready" && (
        <>
          <div className="divide-y divide-border/50 px-5 pb-2 pt-1">
            <DetailRow label={t("referrals.stats.referralCodeLabel")} value={state.data.referral_code ?? none} />
            <DetailRow
              label={t("referrals.stats.referrerLabel")}
              value={state.data.referrer_id !== null ? `#${state.data.referrer_id}` : none}
            />
            <DetailRow label={t("referrals.stats.pointsLabel")} value={state.data.points} />
            {Object.entries(state.data.counts_by_level).map(([level, count]) => (
              <DetailRow
                key={level}
                label={t("referrals.stats.levelCountLabel", { level })}
                value={String(count)}
              />
            ))}
          </div>

          <div className="px-5 pb-2 pt-2">
            <p className="mb-1.5 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
              {t("referrals.stats.rewardsTitle")}
            </p>
            {state.data.rewards.length === 0 ? (
              <p className="py-2 text-[12.5px] text-muted-foreground">{t("referrals.stats.rewardsEmpty")}</p>
            ) : (
              <div className="flex flex-col divide-y divide-border/50">
                {state.data.rewards.map((reward, index) => (
                  <div key={index} className="flex items-center justify-between gap-3 py-1.5">
                    <span className="text-[12.5px] text-muted-foreground">
                      {reward.created_at ? new Date(reward.created_at).toLocaleDateString() : none}
                    </span>
                    <span className="text-[13px] font-medium text-foreground">
                      +{reward.amount} {reward.type === "POINTS" ? "pts" : "d"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {canAdjustPoints && (
            <form
              onSubmit={(event) => void handleAdjust(event)}
              className="flex items-end gap-2 border-t border-border px-5 py-4"
            >
              <div className="flex flex-1 flex-col gap-1">
                <label htmlFor="referral-adjust-delta" className="text-sm font-medium text-foreground/80">
                  {t("referrals.stats.adjustLabel")}
                </label>
                <input
                  id="referral-adjust-delta"
                  type="number"
                  step="1"
                  value={delta}
                  onChange={(event) => setDelta(event.target.value)}
                  placeholder={t("referrals.stats.adjustPlaceholder")}
                  className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                />
              </div>
              <motion.button
                type="submit"
                disabled={isAdjusting || !delta.trim()}
                {...bounceTap(bounceStrength)}
                className="shrink-0 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t("referrals.stats.adjustButton")}
              </motion.button>
            </form>
          )}
        </>
      )}
    </>
  );
}
