import { CalendarDays, Package } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { Plan } from "@entities/plans/api";
import type { DurationChoice } from "@features/subscription-grant/duration";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const KEEP = "keep";
const CUSTOM = "custom";

interface PlanDurationPickerProps {
  plans: Plan[];
  planId: number | null;
  onPlanChange: (planId: number) => void;
  duration: DurationChoice;
  onDurationChange: (choice: DurationChoice) => void;
  /** offered first when set: keep the current expiry */
  keepLabel?: string;
}

export function PlanDurationPicker({ plans, planId, onPlanChange, duration, onDurationChange, keepLabel }: PlanDurationPickerProps) {
  const { t } = useTranslation();
  const plan = plans.find((item) => item.id === planId);
  const durationValue = duration.kind === "plan" ? String(duration.days) : duration.kind === "keep" ? KEEP : CUSTOM;
  const durationOptions = [
    ...(keepLabel ? [{ value: KEEP, label: keepLabel }] : []),
    ...(plan?.durations ?? []).map((item) => ({
      value: String(item.days),
      label: t("subscriptions.duration.days", { count: item.days }),
    })),
    { value: CUSTOM, label: t("subscriptions.duration.custom") },
  ];

  const handleDurationChange = (value: string) => {
    if (value === KEEP) onDurationChange({ kind: "keep" });
    else if (value === CUSTOM) onDurationChange({ kind: "custom", days: "" });
    else onDurationChange({ kind: "plan", days: Number(value) });
  };

  return (
    <>
      <Field label={t("subscriptions.grant.planLabel")} htmlFor="subscription-plan">
        <SelectDropdown
          variant="well"
          size="compact"
          id="subscription-plan"
          value={planId === null ? "" : String(planId)}
          onChange={(value) => onPlanChange(Number(value))}
          icon={Package}
          placeholder={plan?.name ?? t("subscriptions.grant.planPlaceholder")}
          options={plans.map((item) => ({ value: String(item.id), label: item.name }))}
        />
      </Field>
      <Field label={t("subscriptions.grant.durationLabel")} htmlFor="subscription-duration">
        <SelectDropdown
          variant="well"
          size="compact"
          id="subscription-duration"
          value={durationValue}
          onChange={handleDurationChange}
          icon={CalendarDays}
          placeholder={durationOptions.find((option) => option.value === durationValue)?.label ?? ""}
          options={durationOptions}
        />
      </Field>
      {duration.kind === "custom" && (
        <Field label={t("subscriptions.duration.customLabel")} htmlFor="subscription-custom-days">
          <Input
            id="subscription-custom-days"
            type="number"
            min={1}
            step="1"
            onKeyDown={blockNonIntegerKeys}
            value={duration.days}
            onChange={(event) => onDurationChange({ kind: "custom", days: event.target.value })}
          />
        </Field>
      )}
    </>
  );
}
