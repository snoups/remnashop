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
import { Switch } from "@shared/ui/Switch";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";


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
    <div className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">{label}</p>
        <p className="text-[12px] text-muted-foreground">{hint}</p>
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
  plans?: { id: number; name: string }[];
}

export function PromocodeLimitsFields({ idPrefix, value, onChange, plans }: PromocodeLimitsFieldsProps) {
  const { t } = useTranslation();
  const set = (patch: Partial<PromocodeLimitsDraft>) => onChange({ ...value, ...patch });

  return (
    <Card variant="form">
      <Field label={t("promocodes.limits.availabilityLabel")} htmlFor={`${idPrefix}-availability`}>
        <SelectDropdown
          variant="form"
          id={`${idPrefix}-availability`}
          value={value.availability}
          onChange={(availability) => set({ availability: availability as PromocodeAvailability })}
          icon={Users}
          placeholder={t(`promocodes.availability.${value.availability}`)}
          options={AVAILABILITIES.map((option) => ({ value: option, label: t(`promocodes.availability.${option}`) }))}
        />
      </Field>

      {value.availability === "ALLOWED" && (
        <Field label={t("promocodes.limits.allowedUserIdsLabel")} htmlFor={`${idPrefix}-allowed-users`} className="rounded-xl border border-primary/20 bg-primary/[0.04] p-3">
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
        <Field label={t("promocodes.limits.plansLabel")} hint={t("promocodes.limits.plansHint")}>
          <div className="flex flex-wrap gap-1.5">
            {plans.map((plan) => {
              const isSelected = value.allowedPlanIds.includes(plan.id);
              return (
                <ChoiceChip
                  key={plan.id}
                  active={isSelected}
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

      <div className="grid grid-cols-2 gap-3">
        <Field label={t("promocodes.limits.expiresLabel")} htmlFor={`${idPrefix}-expires-at`}>
          <DatePickerField
            variant="form"
            id={`${idPrefix}-expires-at`}
            value={value.expiresAt}
            onChange={(expiresAt) => set({ expiresAt })}
            placeholder={t("promocodes.limits.expiresPlaceholder")}
          />
        </Field>
        <Field label={t("promocodes.limits.maxActivationsLabel")} htmlFor={`${idPrefix}-max-activations`}>
          <TextInput
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
    </Card>
  );
}
