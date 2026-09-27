import { Users, X } from "lucide-react";
import { useState, type ClipboardEvent, type KeyboardEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { PromocodeAvailability } from "@entities/promocodes/api";
import { AVAILABILITIES, type PromocodeLimitsDraft } from "@entities/promocodes/display";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";

export const promocodeFieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";
export const promocodeSectionClassName = "flex flex-col gap-3 rounded-2xl border border-white/[0.08] bg-white/[0.03] px-3.5 pb-3.5 pt-1.5";
export const promocodeSectionTitleClassName =
  "pt-2 text-[11px] font-semibold uppercase tracking-wide text-foreground";
const labelClassName = "text-sm font-medium text-foreground/80";

export function PromocodeSwitchRow({
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
      <Switch checked={checked} onChange={onChange} ariaLabel={label} />
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
  /** rendered first inside the section, e.g. the edit dialog's "Active" switch */
  children?: ReactNode;
}

export function PromocodeLimitsFields({ idPrefix, value, onChange, children }: PromocodeLimitsFieldsProps) {
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
    <section className={promocodeSectionClassName}>
      <h3 className={promocodeSectionTitleClassName}>{t("promocodes.sections.limits")}</h3>
      {children}

      <div className="flex flex-col gap-1">
        <span className={labelClassName}>{t("promocodes.limits.availabilityLabel")}</span>
        <SelectDropdown
          id={`${idPrefix}-availability`}
          value={value.availability}
          onChange={(availability) => set({ availability: availability as PromocodeAvailability })}
          icon={Users}
          placeholder={t(`promocodes.availability.${value.availability}`)}
          options={AVAILABILITIES.map((option) => ({ value: option, label: t(`promocodes.availability.${option}`) }))}
        />
      </div>

      {value.availability === "ALLOWED" && (
        <div className="flex flex-col gap-1.5 rounded-xl border border-primary/20 bg-primary/[0.04] p-3">
          <label htmlFor={`${idPrefix}-allowed-users`} className={labelClassName}>
            {t("promocodes.limits.allowedUserIdsLabel")}
          </label>
          <div className="flex flex-wrap items-center gap-1.5">
            {value.allowedUserIds.map((id) => (
              <span
                key={id}
                className="flex items-center gap-1 rounded-full bg-white/[0.06] py-0.5 pl-2.5 pr-1 font-mono text-[12.5px] text-foreground"
              >
                {id}
                <button
                  type="button"
                  onClick={() => set({ allowedUserIds: value.allowedUserIds.filter((other) => other !== id) })}
                  aria-label={t("promocodes.limits.removeUserAria", { id })}
                  className="flex size-[18px] items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.08] hover:text-foreground"
                >
                  <X className="size-2.5" />
                </button>
              </span>
            ))}
            <input
              id={`${idPrefix}-allowed-users`}
              inputMode="numeric"
              value={idDraft}
              onChange={(event) => setIdDraft(event.target.value)}
              onKeyDown={handleIdKeyDown}
              onPaste={handleIdPaste}
              onBlur={() => addIds(idDraft)}
              placeholder={t("promocodes.limits.allowedUserIdsPlaceholder")}
              className="min-w-36 flex-1 bg-transparent px-1.5 py-1 font-mono text-[12.5px] text-foreground outline-none placeholder:text-muted-foreground"
            />
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1">
          <span className={labelClassName}>{t("promocodes.limits.expiresLabel")}</span>
          <DatePickerField
            id={`${idPrefix}-expires-at`}
            value={value.expiresAt}
            onChange={(expiresAt) => set({ expiresAt })}
            placeholder={t("promocodes.limits.expiresPlaceholder")}
            clearAriaLabel={t("promocodes.limits.clearDate")}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={`${idPrefix}-max-activations`} className={labelClassName}>
            {t("promocodes.limits.maxActivationsLabel")}
          </label>
          <input
            id={`${idPrefix}-max-activations`}
            type="number"
            min={1}
            step="1"
            value={value.maxActivations}
            onChange={(event) => set({ maxActivations: event.target.value })}
            placeholder={t("promocodes.limits.maxActivationsHint")}
            className={promocodeFieldClassName}
          />
        </div>
      </div>

      <PromocodeSwitchRow
        label={t("promocodes.limits.reusableLabel")}
        hint={t("promocodes.limits.reusableHint")}
        checked={value.isReusable}
        onChange={(isReusable) => set({ isReusable })}
      />
    </section>
  );
}
