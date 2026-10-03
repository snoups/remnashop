import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type Plan, type PlanAvailability, updatePlanAccess } from "@entities/plans/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Badge } from "@shared/ui/Badge";
import { normalizeEmail, normalizePositiveInt } from "@shared/lib/chip-normalizers";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { Tag } from "@shared/ui/Tag";

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
  const [availability, setAvailability] = useState<PlanAvailability>(plan.availability);
  const [telegramIds, setTelegramIds] = useState(plan.allowed_telegram_ids.map(String));
  const [emails, setEmails] = useState(plan.allowed_emails);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const updated = await updatePlanAccess(plan.id, {
        availability,
        // the lists only mean something for ALLOWED; switching away drops them
        allowed_telegram_ids: availability === "ALLOWED" ? telegramIds.map(Number) : [],
        allowed_emails: availability === "ALLOWED" ? emails : [],
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

  const telegramIdCount = telegramIds.length;
  const emailCount = emails.length;

  return (
    <>
      <DialogHeader
        icon={ShieldCheck}
        title={t("plans.access.title")}
        subtitle={plan.name}
      />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <Card variant="form">
            <Field label={t("plans.access.availabilitySection")}>
              <div className="flex flex-col gap-1.5">
                {AVAILABILITIES.map((value) => {
                  const isSelected = availability === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => setAvailability(value)}
                      className={`flex items-center gap-3 rounded-[14px] border px-3 py-2.5 text-left transition-colors ${
                        isSelected ? "border-primary/50 bg-accent" : "border-border bg-white/[0.02] hover:bg-white/[0.05]"
                      }`}
                    >
                      <span
                        className={`size-4 shrink-0 rounded-full border-[1.5px] transition-[border-width,border-color] ${
                          isSelected ? "border-[5px] border-primary" : "border-foreground/30"
                        }`}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13.5px] font-semibold text-foreground">
                          {t(`plans.access.availability.${value}`)}
                        </span>
                        <span className="block text-[11.5px] text-muted-foreground">
                          {t(`plans.access.availabilityHint.${value}`)}
                        </span>
                      </span>
                      {RESTRICTED_AVAILABILITIES.has(value) && (
                        <Badge tone="violet">
                          {t("plans.access.restricted")}
                        </Badge>
                      )}
                    </button>
                  );
                })}
              </div>
            </Field>
          </Card>

          {availability === "ALLOWED" && (
            <Card variant="form">
              <Field label={t("plans.access.telegramIdsLabel")} htmlFor="plan-access-telegram-ids" aside={<Tag>{telegramIdCount}</Tag>}>
                <ChipsInput
                  id="plan-access-telegram-ids"
                  values={telegramIds}
                  onChange={setTelegramIds}
                  normalize={normalizePositiveInt}
                  inputMode="numeric"
                  placeholder={t("plans.access.telegramIdsPlaceholder")}
                />
              </Field>
              <Field label={t("plans.access.emailsLabel")} htmlFor="plan-access-emails" aside={<Tag>{emailCount}</Tag>}>
                <ChipsInput
                  id="plan-access-emails"
                  values={emails}
                  onChange={setEmails}
                  normalize={normalizeEmail}
                  inputMode="email"
                  placeholder={t("plans.access.emailsPlaceholder")}
                />
              </Field>
            </Card>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.07] px-5 py-3.5">
          <p className="min-w-0 flex-1 truncate text-[12.5px] text-muted-foreground">
            {availability === "ALLOWED" ? (
              <span className="font-semibold text-violet-300">
                {t("plans.access.recipients", { count: telegramIdCount + emailCount })}
              </span>
            ) : (
              t(`plans.access.availability.${availability}`)
            )}
          </p>
          <Button
            variant="outline"
            type="button"
            onClick={close}
          >
            {t("plans.access.cancel")}
          </Button>
          <Button
            variant="accent"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? t("plans.access.saving") : t("plans.access.save")}
          </Button>
        </div>
      </form>
    </>
  );
}
