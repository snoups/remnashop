import { Users, X } from "lucide-react";
import { useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import type { PromocodeAvailability } from "@entities/promocodes/api";
import { AVAILABILITIES, type PromocodeLimitsDraft } from "@entities/promocodes/display";
import { blockNonIntegerKeys } from "@shared/lib/number-input";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { IconButton } from "@shared/ui/IconButton";


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

function parseIds(text: string): number[] {
  return text
    .split(/[\s,]+/)
    .map((token) => Number(token))
    .filter((id) => Number.isInteger(id) && id > 0);
}

interface PromocodeLimitsFieldsProps {
  idPrefix: string;
  value: PromocodeLimitsDraft;
  onChange: (value: PromocodeLimitsDraft) => void;
}

export function PromocodeLimitsFields({ idPrefix, value, onChange }: PromocodeLimitsFieldsProps) {
  const { t } = useTranslation();
  const [idDraft, setIdDraft] = useState("");
  const set = (patch: Partial<PromocodeLimitsDraft>) => onChange({ ...value, ...patch });

  const addIds = (text: string) => {
    const fresh = parseIds(text).filter((id) => !value.allowedUserIds.includes(id));
    if (fresh.length > 0) set({ allowedUserIds: [...value.allowedUserIds, ...new Set(fresh)] });
    setIdDraft("");
  };

  const handleIdKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === "," || event.key === " ") {
      event.preventDefault();
      addIds(idDraft);
    } else if (event.key === "Backspace" && idDraft === "" && value.allowedUserIds.length > 0) {
      set({ allowedUserIds: value.allowedUserIds.slice(0, -1) });
    }
  };

  const handleIdPaste = (event: ClipboardEvent<HTMLInputElement>) => {
    event.preventDefault();
    addIds(`${idDraft} ${event.clipboardData.getData("text")}`);
  };

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
          <div className="flex min-h-9.5 flex-wrap items-center gap-1.5 rounded-[19px] border border-border bg-input/60 px-1.5 py-1 focus-within:border-primary">
            {value.allowedUserIds.map((id) => (
              <span
                key={id}
                className="flex items-center gap-1 rounded-full bg-white/[0.06] py-0.5 pl-2.5 pr-0.5 font-mono text-[12.5px] text-foreground"
              >
                {id}
                <IconButton size="18px"
                  onClick={() => set({ allowedUserIds: value.allowedUserIds.filter((other) => other !== id) })}
                >
                  <X className="size-2.5" />
                </IconButton>
              </span>
            ))}
            <input
              id={`${idPrefix}-allowed-users`}
              inputMode="numeric"
              value={idDraft}
              onChange={(event) => setIdDraft(event.target.value.replace(/\D/g, ""))}
              onKeyDown={handleIdKeyDown}
              onPaste={handleIdPaste}
              onBlur={() => addIds(idDraft)}
              placeholder={t("promocodes.limits.allowedUserIdsPlaceholder")}
              className="min-w-36 flex-1 bg-transparent px-1.5 py-1 font-mono text-sm text-foreground outline-none"
            />
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
