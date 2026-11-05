import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type Plan, type PlanAvailability, updatePlanAccess } from "@entities/plans/api";
import { type PlanAccessValue, planAccessPayload, planAccessValue } from "@features/plan-access/access-value";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { Badge } from "@shared/ui/Badge";
import { normalizeEmail, normalizePositiveInt } from "@shared/lib/chip-normalizers";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { GLASS_DIALOG_BODY_CLASS, GLASS_DIALOG_CARD_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Tag } from "@shared/ui/Tag";
import { Pressable } from "@shared/ui/Pressable";

const AVAILABILITIES: PlanAvailability[] = ["ALL", "NEW", "EXISTING", "INVITED", "ALLOWED", "LINK"];
const RESTRICTED_AVAILABILITIES: ReadonlySet<PlanAvailability> = new Set(["INVITED", "ALLOWED", "LINK"]);

interface PlanAccessDialogProps {
  plan: Plan;
  onClose: () => void;
  onSaved: (plan: Plan) => void;
}


export function PlanAccessDialog({ plan, onClose, onSaved }: PlanAccessDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <PlanAccessDialogBody plan={plan} onSaved={onSaved} />
    </Modal>
  );
}

function PlanAccessDialogBody({ plan, onSaved }: Pick<PlanAccessDialogProps, "plan" | "onSaved">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [value, setValue] = useState(() => planAccessValue(plan));
  const { availability } = value;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const updated = await updatePlanAccess(plan.id, planAccessPayload(value));
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
      <DialogHeader
        icon={ShieldCheck}
        title={t("plans.access.title")}
        subtitle={plan.name}
      />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className={`${GLASS_DIALOG_BODY_CLASS} flex flex-col gap-3`}>
          <PlanAccessFields value={value} onChange={setValue} isTrial={plan.is_trial} />
        </div>

        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 items-center`}>
          <p className="min-w-0 flex-1 truncate text-[12.5px] text-muted-foreground">
            {availability === "ALLOWED" ? (
              <span className="font-semibold text-violet-300">
                {t("plans.access.recipients", { count: value.telegramIds.length + value.emails.length })}
              </span>
            ) : (
              t(`plans.access.availability.${availability}`)
            )}
          </p>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" isLoading={isSubmitting}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </>
  );
}

export function PlanAccessFields({
  value,
  onChange,
  isTrial,
}: {
  value: PlanAccessValue;
  onChange: (value: PlanAccessValue) => void;
  isTrial: boolean;
}) {
  const { t } = useTranslation();
  const { availability, telegramIds, emails } = value;

  return (
    <>
      <div className={GLASS_DIALOG_CARD_CLASS}>
        <Field label={t("plans.access.availabilitySection")}>
          <div className="flex flex-col gap-1.5">
            {AVAILABILITIES.map((option) => {
              const isSelected = availability === option;
              // the trial button never offers an EXISTING trial
              const isDisabled = isTrial && option === "EXISTING";
              return (
                <Pressable
                  key={option}
                  type="button"
                  disabled={isDisabled}
                  onClick={() => onChange({ ...value, availability: option })}
                  className={`flex items-center gap-3 rounded-[10px] border px-3 py-2.5 text-left transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                    isSelected ? "border-primary/35 bg-primary/15" : "border-glass-border bg-white/[0.03] hover:bg-white/[0.06]"
                  }`}
                >
                  <span
                    className={`size-4 shrink-0 rounded-full border-[1.5px] transition-[border-width,border-color] ${
                      isSelected ? "border-[5px] border-primary" : "border-foreground/30"
                    }`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] font-semibold text-foreground">
                      {t(`plans.access.availability.${option}`)}
                    </span>
                    <span className="block text-[12px] text-muted-foreground">
                      {isDisabled ? t("plans.access.trialUnavailable") : t(`plans.access.availabilityHint.${option}`)}
                    </span>
                  </span>
                  {RESTRICTED_AVAILABILITIES.has(option) && (
                    <Badge borderless tone="violet">
                      {t("plans.access.restricted")}
                    </Badge>
                  )}
                </Pressable>
              );
            })}
          </div>
        </Field>
      </div>

      {availability === "ALLOWED" && (
        <div className={GLASS_DIALOG_CARD_CLASS}>
          <Field label={t("plans.access.telegramIdsLabel")} htmlFor="plan-access-telegram-ids" aside={<Tag>{telegramIds.length}</Tag>}>
            <ChipsInput
              glass
              id="plan-access-telegram-ids"
              values={telegramIds}
              onChange={(next) => onChange({ ...value, telegramIds: next })}
              normalize={normalizePositiveInt}
              inputMode="numeric"
              placeholder={t("plans.access.telegramIdsPlaceholder")}
            />
          </Field>
          <Field label={t("plans.access.emailsLabel")} htmlFor="plan-access-emails" aside={<Tag>{emails.length}</Tag>}>
            <ChipsInput
              glass
              id="plan-access-emails"
              values={emails}
              onChange={(next) => onChange({ ...value, emails: next })}
              normalize={normalizeEmail}
              inputMode="email"
              placeholder={t("plans.access.emailsPlaceholder")}
            />
          </Field>
        </div>
      )}
    </>
  );
}
