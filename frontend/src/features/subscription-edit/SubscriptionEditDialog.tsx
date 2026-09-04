import { Filter, Pencil, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  type SubscriptionListItem,
  type TrafficLimitStrategy,
  updateSubscription,
} from "@entities/subscriptions/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const STRATEGIES: TrafficLimitStrategy[] = ["NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"];

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

interface SubscriptionEditDialogProps {
  subscription: SubscriptionListItem;
  onClose: () => void;
  onSaved: (updated: SubscriptionListItem) => void;
}

export function SubscriptionEditDialog({ subscription, onClose, onSaved }: SubscriptionEditDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <SubscriptionEditDialogBody subscription={subscription} onSaved={onSaved} />
    </Modal>
  );
}

function SubscriptionEditDialogBody({
  subscription,
  onSaved,
}: Pick<SubscriptionEditDialogProps, "subscription" | "onSaved">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tag, setTag] = useState(subscription.tag ?? "");
  const [trafficGb, setTrafficGb] = useState(String(subscription.traffic_limit));
  const [deviceLimit, setDeviceLimit] = useState(String(subscription.device_limit));
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(subscription.traffic_limit_strategy);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const parsedTrafficGb = parseRequiredInt(trafficGb, 0);
    const parsedDeviceLimit = parseRequiredInt(deviceLimit, 0);
    if (parsedTrafficGb === undefined || parsedDeviceLimit === undefined) {
      toast.error(t("errors.invalidNumber"));
      return;
    }

    setIsSubmitting(true);
    try {
      const updated = await updateSubscription(subscription.id, {
        tag: tag.trim() || null,
        traffic_limit: parsedTrafficGb,
        device_limit: parsedDeviceLimit,
        traffic_limit_strategy: strategy,
      });
      toast.success(t("subscriptions.edit.saved"));
      onSaved(updated);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Pencil className="size-4" />
          </div>
          {t("subscriptions.edit.title")}
        </h2>
        <button
          type="button"
          onClick={close}
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
            className={fieldClassName}
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
            className={fieldClassName}
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
            className={fieldClassName}
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
            onClick={close}
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
    </>
  );
}
