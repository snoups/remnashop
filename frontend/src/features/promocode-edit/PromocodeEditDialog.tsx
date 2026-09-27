import { Check, Copy, Lock, Ticket, Trash2, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { AddOnListItem } from "@entities/addons/api";
import type { Plan } from "@entities/plans/api";
import { type Promocode, updatePromocode } from "@entities/promocodes/api";
import {
  describeReward,
  getPromocodeStatus,
  limitsDraftOf,
  limitsToPayload,
  PROMOCODE_STATUS_BADGE_CLASSNAME,
  REWARD_TYPE_ICON,
} from "@entities/promocodes/display";
import {
  PromocodeLimitsFields,
  PromocodeSwitchRow,
  promocodeSectionClassName,
  promocodeSectionTitleClassName,
} from "@entities/promocodes/PromocodeLimitsFields";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { Modal, useModalClose } from "@shared/ui/Modal";

const COPIED_RESET_MS = 1500;

interface PromocodeEditDialogProps {
  promocode: Promocode;
  addons: AddOnListItem[];
  plans: Plan[];
  /** omitted when the actor can't delete; the page owns the confirmation */
  onDelete?: () => void;
  onClose: () => void;
  onSaved: (promocode: Promocode) => void;
}

export function PromocodeEditDialog({ onClose, ...props }: PromocodeEditDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <PromocodeEditDialogBody {...props} />
    </Modal>
  );
}

function PromocodeEditDialogBody({
  promocode,
  addons,
  plans,
  onDelete,
  onSaved,
}: Omit<PromocodeEditDialogProps, "onClose">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [isActive, setIsActive] = useState(promocode.is_active);
  const [limits, setLimits] = useState(() => limitsDraftOf(promocode));

  const status = getPromocodeStatus(promocode);
  const RewardIcon = REWARD_TYPE_ICON[promocode.reward_type];

  const handleCopy = () => {
    navigator.clipboard?.writeText(promocode.code).catch(() => {});
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), COPIED_RESET_MS);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const limitsPayload = limitsToPayload(limits);
    if (limitsPayload === undefined) {
      toast.error(t("errors.invalidNumber"));
      return;
    }

    setIsSubmitting(true);
    try {
      const updated = await updatePromocode(promocode.id, { is_active: isActive, ...limitsPayload });
      toast.success(t("promocodes.edit.saved"));
      onSaved(updated);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex min-w-0 items-center gap-2.5">
          <div
            className={`flex size-8 shrink-0 items-center justify-center rounded-full ${
              status === "ACTIVE" ? "bg-primary/10 text-primary" : "bg-white/[0.06] text-muted-foreground"
            }`}
          >
            <Ticket className="size-4" />
          </div>
          <h2 className="truncate font-mono text-base font-bold text-foreground">{promocode.code}</h2>
          <button
            type="button"
            onClick={handleCopy}
            aria-label={t("promocodes.copyAria", { code: promocode.code })}
            className="flex size-6 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
          >
            {isCopied ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
          </button>
          <span
            className={`shrink-0 rounded-full border px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide ${PROMOCODE_STATUS_BADGE_CLASSNAME[status]}`}
          >
            {t(`promocodes.status.${status}`)}
          </span>
        </div>
        <button
          type="button"
          onClick={close}
          aria-label={t("promocodes.edit.close")}
          className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <section className={promocodeSectionClassName}>
            <h3 className={promocodeSectionTitleClassName}>{t("promocodes.sections.reward")}</h3>
            <div className="flex items-center gap-3">
              <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <RewardIcon className="size-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[28px] font-bold leading-none tracking-tight text-foreground">
                  {describeReward(promocode, addons, plans, t)}
                </p>
                <p className="mt-1 text-[12.5px] text-muted-foreground">
                  {t(`promocodes.rewardType.${promocode.reward_type}`)}
                </p>
              </div>
              <span className="flex shrink-0 items-center gap-1.5 text-[11.5px] text-muted-foreground">
                <Lock className="size-3" />
                {t("promocodes.edit.rewardLocked")}
              </span>
            </div>
          </section>

          <PromocodeLimitsFields idPrefix="promo-edit" value={limits} onChange={setLimits}>
            <PromocodeSwitchRow
              label={t("promocodes.edit.activeLabel")}
              hint={t("promocodes.edit.activeHint")}
              checked={isActive}
              onChange={setIsActive}
            />
          </PromocodeLimitsFields>
        </div>

        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.07] px-5 py-3.5">
          {onDelete && (
            <button
              type="button"
              onClick={onDelete}
              className="flex items-center gap-1.5 rounded-full bg-error/10 px-3.5 py-2 text-sm font-medium text-error transition-colors hover:bg-error/20"
            >
              <Trash2 className="size-3.5" />
              {t("promocodes.delete.confirmButton")}
            </button>
          )}
          <span className="flex-1" />
          <button
            type="button"
            onClick={close}
            className="rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("promocodes.edit.cancel")}
          </button>
          <motion.button
            type="submit"
            disabled={isSubmitting}
            {...bounceTap(bounceStrength)}
            className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("promocodes.edit.saving") : t("promocodes.edit.save")}
          </motion.button>
        </div>
      </form>
    </>
  );
}
