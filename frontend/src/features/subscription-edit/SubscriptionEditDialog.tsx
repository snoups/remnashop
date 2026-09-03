import { Filter, Pencil, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  type SubscriptionListItem,
  type TrafficLimitStrategy,
  updateSubscription,
} from "@entities/subscriptions/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { DialogPortal } from "@shared/ui/DialogPortal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const STRATEGIES: TrafficLimitStrategy[] = ["NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"];

interface SubscriptionEditDialogProps {
  subscription: SubscriptionListItem;
  onClose: () => void;
  onSaved: (updated: SubscriptionListItem) => void;
}

export function SubscriptionEditDialog({ subscription, onClose, onSaved }: SubscriptionEditDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tag, setTag] = useState(subscription.tag ?? "");
  const [trafficGb, setTrafficGb] = useState(String(subscription.traffic_limit));
  const [deviceLimit, setDeviceLimit] = useState(String(subscription.device_limit));
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(subscription.traffic_limit_strategy);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const updated = await updateSubscription(subscription.id, {
        tag: tag.trim() || null,
        traffic_limit: Math.max(0, Math.round(Number(trafficGb))),
        device_limit: Math.max(0, Math.round(Number(deviceLimit))),
        traffic_limit_strategy: strategy,
      });
      toast.success(t("subscriptions.edit.saved"));
      onSaved(updated);
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DialogPortal>
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15, ease: "easeOut" }}
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
        >
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            className="absolute inset-0 cursor-default"
            onClick={onClose}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                  <Pencil className="size-4" />
                </div>
                {t("subscriptions.edit.title")}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label={t("subscriptions.edit.close")}
                className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4 px-5 pb-5 pt-4">
              <div className="flex flex-col gap-1">
                <label htmlFor="sub-edit-tag" className="text-sm font-medium text-foreground/80">
                  {t("subscriptions.edit.tagLabel")}
                </label>
                <input
                  id="sub-edit-tag"
                  value={tag}
                  onChange={(event) => setTag(event.target.value)}
                  placeholder={t("subscriptions.edit.tagPlaceholder")}
                  className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label htmlFor="sub-edit-traffic" className="text-sm font-medium text-foreground/80">
                  {t("subscriptions.edit.trafficLabel")}
                </label>
                <input
                  id="sub-edit-traffic"
                  type="number"
                  min={0}
                  step="1"
                  value={trafficGb}
                  onChange={(event) => setTrafficGb(event.target.value)}
                  className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                />
                <span className="text-[11.5px] text-muted-foreground">{t("subscriptions.edit.trafficHint")}</span>
              </div>

              <div className="flex flex-col gap-1">
                <label htmlFor="sub-edit-devices" className="text-sm font-medium text-foreground/80">
                  {t("subscriptions.edit.deviceLabel")}
                </label>
                <input
                  id="sub-edit-devices"
                  type="number"
                  min={0}
                  step="1"
                  value={deviceLimit}
                  onChange={(event) => setDeviceLimit(event.target.value)}
                  className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                />
                <span className="text-[11.5px] text-muted-foreground">{t("subscriptions.edit.deviceHint")}</span>
              </div>

              <div className="flex flex-col gap-1">
                <span className="text-sm font-medium text-foreground/80">{t("subscriptions.edit.strategyLabel")}</span>
                <SelectDropdown
                  id="sub-edit-strategy"
                  value={strategy}
                  onChange={(value) => setStrategy(value as TrafficLimitStrategy)}
                  icon={Filter}
                  placeholder={t(`subscriptions.edit.strategy.${strategy}`)}
                  options={STRATEGIES.map((value) => ({ value, label: t(`subscriptions.edit.strategy.${value}`) }))}
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
                >
                  {t("subscriptions.edit.cancel")}
                </button>
                <motion.button
                  type="submit"
                  disabled={isSubmitting}
                  {...bounceTap(bounceStrength)}
                  className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? t("subscriptions.edit.saving") : t("subscriptions.edit.save")}
                </motion.button>
              </div>
            </form>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    </DialogPortal>
  );
}
