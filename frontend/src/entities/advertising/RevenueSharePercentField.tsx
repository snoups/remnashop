import { useTranslation } from "react-i18next";

import { blockNonDecimalKeys } from "@shared/lib/number-input";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";

export function RevenueSharePercentField({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <Field label={t("advertising.revenueShare.label")} htmlFor={id} hint={t("advertising.revenueShare.hint")}>
      <Input
        id={id}
        type="number"
        onKeyDown={blockNonDecimalKeys}
        min={0}
        max={100}
        step="0.01"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full"
      />
    </Field>
  );
}
