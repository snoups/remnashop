import { Filter, ShieldCheck, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type Plan, type PlanAvailability, updatePlanAccess } from "@entities/plans/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const AVAILABILITIES: PlanAvailability[] = ["ALL", "NEW", "EXISTING", "INVITED", "ALLOWED", "LINK"];

interface PlanAccessDialogProps {
  plan: Plan;
  onClose: () => void;
  onSaved: (plan: Plan) => void;
}

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

export function PlanAccessDialog({ plan, onClose, onSaved }: PlanAccessDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <PlanAccessDialogBody plan={plan} onSaved={onSaved} />
    </Modal>
  );
}

function PlanAccessDialogBody({ plan, onSaved }: Pick<PlanAccessDialogProps, "plan" | "onSaved">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [availability, setAvailability] = useState<PlanAvailability>(plan.availability);
  const [telegramIds, setTelegramIds] = useState(plan.allowed_telegram_ids.join("\n"));
  const [emails, setEmails] = useState(plan.allowed_emails.join("\n"));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const updated = await updatePlanAccess(plan.id, {
        availability,
        allowed_telegram_ids: parseLines(telegramIds)
          .map((id) => Number(id))
          .filter((id) => Number.isFinite(id)),
        allowed_emails: parseLines(emails),
      });
      toast.success(t("plans.access.saved"));
      onSaved(updated);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("plans.access.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <ShieldCheck className="size-4" />
          </div>
          {t("plans.access.title")}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("plans.access.close")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4 px-5 pb-5 pt-4">
        <div className="flex flex-col gap-1">
          <span className="text-sm font-medium text-foreground/80">{t("plans.access.availabilityLabel")}</span>
          <SelectDropdown
            id="plan-access-availability"
            value={availability}
            onChange={(value) => setAvailability(value as PlanAvailability)}
            icon={Filter}
            placeholder={t(`plans.access.availability.${availability}`)}
            options={AVAILABILITIES.map((value) => ({
              value,
              label: t(`plans.access.availability.${value}`),
            }))}
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="plan-access-telegram-ids" className="text-sm font-medium text-foreground/80">
            {t("plans.access.telegramIdsLabel")}
          </label>
          <textarea
            id="plan-access-telegram-ids"
            value={telegramIds}
            onChange={(event) => setTelegramIds(event.target.value)}
            rows={3}
            className={`${fieldClassName} resize-none font-mono`}
          />
          <span className="text-[11.5px] text-muted-foreground">{t("plans.access.telegramIdsHint")}</span>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="plan-access-emails" className="text-sm font-medium text-foreground/80">
            {t("plans.access.emailsLabel")}
          </label>
          <textarea
            id="plan-access-emails"
            value={emails}
            onChange={(event) => setEmails(event.target.value)}
            rows={3}
            className={`${fieldClassName} resize-none font-mono`}
          />
          <span className="text-[11.5px] text-muted-foreground">{t("plans.access.emailsHint")}</span>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={close}
            className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("plans.access.cancel")}
          </button>
          <motion.button
            type="submit"
            disabled={isSubmitting}
            {...bounceTap(bounceStrength)}
            className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("plans.access.saving") : t("plans.access.save")}
          </motion.button>
        </div>
      </form>
    </>
  );
}
