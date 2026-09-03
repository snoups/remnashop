import { Filter, Pencil, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type Promocode, type PromocodeAvailability, updatePromocode } from "@entities/promocodes/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { DialogPortal } from "@shared/ui/DialogPortal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";

const AVAILABILITIES: PromocodeAvailability[] = ["ALL", "NEW", "EXISTING", "INVITED", "ALLOWED"];

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

function parseLines(value: string): string[] {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function toDateInput(iso: string | null): string {
  return iso ? iso.slice(0, 10) : "";
}

interface PromocodeEditDialogProps {
  promocode: Promocode;
  onClose: () => void;
  onSaved: (promocode: Promocode) => void;
}

export function PromocodeEditDialog({ promocode, onClose, onSaved }: PromocodeEditDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isActive, setIsActive] = useState(promocode.is_active);
  const [availability, setAvailability] = useState<PromocodeAvailability>(promocode.availability);
  const [allowedUserIds, setAllowedUserIds] = useState(promocode.allowed_user_ids.join("\n"));
  const [expiresAt, setExpiresAt] = useState(toDateInput(promocode.expires_at));
  const [maxActivations, setMaxActivations] = useState(
    promocode.max_activations !== null ? String(promocode.max_activations) : "",
  );
  const [isReusable, setIsReusable] = useState(promocode.is_reusable);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const updated = await updatePromocode(promocode.id, {
        is_active: isActive,
        availability,
        allowed_user_ids: parseLines(allowedUserIds)
          .map((id) => Number(id))
          .filter((id) => Number.isFinite(id)),
        expires_at: expiresAt ? `${expiresAt}T23:59:59.000Z` : null,
        max_activations: maxActivations.trim() ? Math.max(1, Math.round(Number(maxActivations))) : null,
        is_reusable: isReusable,
      });
      toast.success(t("promocodes.edit.saved"));
      onSaved(updated);
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.edit.error")));
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
                <span className="truncate font-mono">{promocode.code}</span>
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label={t("promocodes.edit.close")}
                className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4 px-5 pb-5 pt-4">
              <label className="flex items-center gap-2.5 text-sm font-medium text-foreground/80">
                <Switch checked={isActive} onChange={setIsActive} ariaLabel={t("promocodes.edit.activeLabel")} />
                {t("promocodes.edit.activeLabel")}
              </label>

              <div className="flex flex-col gap-1">
                <span className="text-sm font-medium text-foreground/80">{t("promocodes.edit.availabilityLabel")}</span>
                <SelectDropdown
                  id="promo-edit-availability"
                  value={availability}
                  onChange={(value) => setAvailability(value as PromocodeAvailability)}
                  icon={Filter}
                  placeholder={t(`promocodes.availability.${availability}`)}
                  options={AVAILABILITIES.map((value) => ({ value, label: t(`promocodes.availability.${value}`) }))}
                />
              </div>

              <div className="flex flex-col gap-1">
                <label htmlFor="promo-edit-allowed-users" className="text-sm font-medium text-foreground/80">
                  {t("promocodes.edit.allowedUserIdsLabel")}
                </label>
                <textarea
                  id="promo-edit-allowed-users"
                  value={allowedUserIds}
                  onChange={(event) => setAllowedUserIds(event.target.value)}
                  rows={3}
                  className={`${fieldClassName} resize-none font-mono`}
                />
                <span className="text-[11.5px] text-muted-foreground">{t("promocodes.edit.allowedUserIdsHint")}</span>
              </div>

              <div className="flex gap-3">
                <div className="flex flex-1 flex-col gap-1">
                  <span className="text-sm font-medium text-foreground/80">{t("promocodes.edit.expiresLabel")}</span>
                  <DatePickerField
                    id="promo-edit-expires-at"
                    value={expiresAt}
                    onChange={setExpiresAt}
                    placeholder={t("promocodes.edit.expiresPlaceholder")}
                    clearAriaLabel={t("promocodes.edit.clearDate")}
                  />
                </div>
                <div className="flex flex-1 flex-col gap-1">
                  <label htmlFor="promo-edit-max-activations" className="text-sm font-medium text-foreground/80">
                    {t("promocodes.edit.maxActivationsLabel")}
                  </label>
                  <input
                    id="promo-edit-max-activations"
                    type="number"
                    min={1}
                    step="1"
                    value={maxActivations}
                    onChange={(event) => setMaxActivations(event.target.value)}
                    placeholder={t("promocodes.edit.maxActivationsHint")}
                    className={fieldClassName}
                  />
                </div>
              </div>

              <label className="flex items-center gap-2.5 text-sm font-medium text-foreground/80">
                <Switch checked={isReusable} onChange={setIsReusable} ariaLabel={t("promocodes.edit.reusableLabel")} />
                {t("promocodes.edit.reusableLabel")}
              </label>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
                >
                  {t("promocodes.edit.cancel")}
                </button>
                <motion.button
                  type="submit"
                  disabled={isSubmitting}
                  {...bounceTap(bounceStrength)}
                  className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? t("promocodes.edit.saving") : t("promocodes.edit.save")}
                </motion.button>
              </div>
            </form>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    </DialogPortal>
  );
}
