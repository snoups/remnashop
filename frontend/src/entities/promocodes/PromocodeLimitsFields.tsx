import { Users } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { PromocodeAvailability } from "@entities/promocodes/api";
import { AVAILABILITIES, type PromocodeLimitsDraft } from "@entities/promocodes/display";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { normalizePositiveInt } from "@shared/lib/chip-normalizers";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { GLASS_DIALOG_CARD_CLASS } from "@shared/ui/classes";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Switch } from "@shared/ui/glass/Switch";


function PromocodeSwitchRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-xs text-muted-foreground">{hint}</p>
      </div>
      <Switch checked={checked} onChange={onChange} />
    </div>
  );
}

interface PromocodeLimitsFieldsProps {
  idPrefix: string;
  value: PromocodeLimitsDraft;
  onChange: (value: PromocodeLimitsDraft) => void;
  /** offered only for rewards applied to a subscription */
  plans?: { id: number; name: string; allow_promocodes: boolean }[];
}

export function PromocodeLimitsFields({ idPrefix, value, onChange, plans }: PromocodeLimitsFieldsProps) {
  const { t } = useTranslation();
  const set = (patch: Partial<PromocodeLimitsDraft>) => onChange({ ...value, ...patch });

  return (
    <div className={GLASS_DIALOG_CARD_CLASS}>
      <Field label={t("promocodes.limits.availabilityLabel")} htmlFor={`${idPrefix}-availability`}>
        <SelectDropdown
          variant="well"
          size="compact"
          id={`${idPrefix}-availability`}
          value={value.availability}
          onChange={(availability) => set({ availability: availability as PromocodeAvailability })}
          icon={Users}
          placeholder={t(`promocodes.availability.${value.availability}`)}
          options={AVAILABILITIES.map((option) => ({ value: option, label: t(`promocodes.availability.${option}`) }))}
        />
      </Field>

      {value.availability === "ALLOWED" && (
        <Field label={t("promocodes.limits.allowedUserIdsLabel")} htmlFor={`${idPrefix}-allowed-users`}>
          <ChipsInput
            id={`${idPrefix}-allowed-users`}
            values={value.allowedUserIds.map(String)}
            onChange={(ids) => set({ allowedUserIds: ids.map(Number) })}
            normalize={normalizePositiveInt}
            inputMode="numeric"
            placeholder={t("promocodes.limits.allowedUserIdsPlaceholder")}
          />
        </Field>
      )}

      {plans && plans.length > 0 && (
        <Field label={t("promocodes.limits.plansLabel")}>
          <div className="flex flex-wrap gap-1.5">
            {/* an empty list is "any plan" */}
            <ChoiceChip active={value.allowedPlanIds.length === 0} onClick={() => set({ allowedPlanIds: [] })}>
              {t("promocodes.limits.plansAll")}
            </ChoiceChip>
            {plans.map((plan) => {
              const isSelected = value.allowedPlanIds.includes(plan.id);
              return (
                <ChoiceChip
                  key={plan.id}
                  active={isSelected}
                  // a plan that refuses promocodes can be unticked, not picked
                  disabled={!plan.allow_promocodes && !isSelected}
                  onClick={() =>
                    set({
                      allowedPlanIds: isSelected
                        ? value.allowedPlanIds.filter((id) => id !== plan.id)
                        : [...value.allowedPlanIds, plan.id],
                    })
                  }
                >
                  {plan.name}
                </ChoiceChip>
              );
            })}
          </div>
        </Field>
      )}
      {plans && plans.some((plan) => !plan.allow_promocodes) && (
        <p className="-mt-1 text-xs text-muted-foreground">{t("promocodes.limits.plansPromocodesOff")}</p>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label={t("promocodes.limits.expiresLabel")} htmlFor={`${idPrefix}-expires-at`}>
          <DatePickerField
            variant="well"
            id={`${idPrefix}-expires-at`}
            value={value.expiresAt}
            onChange={(expiresAt) => set({ expiresAt })}
            placeholder={t("promocodes.limits.expiresPlaceholder")}
          />
        </Field>
        <Field label={t("promocodes.limits.maxActivationsLabel")} htmlFor={`${idPrefix}-max-activations`}>
          <Input
            id={`${idPrefix}-max-activations`}
            type="number"
            onKeyDown={blockNonIntegerKeys}
            min={1}
            step="1"
            value={value.maxActivations}
            onChange={(event) => set({ maxActivations: event.target.value })}
            placeholder={t("promocodes.limits.maxActivationsHint")}
          />
        </Field>
      </div>

      <PromocodeSwitchRow
        label={t("promocodes.limits.reusableLabel")}
        hint={t("promocodes.limits.reusableHint")}
        checked={value.isReusable}
        onChange={(isReusable) => set({ isReusable })}
      />
    </div>
  );
}
