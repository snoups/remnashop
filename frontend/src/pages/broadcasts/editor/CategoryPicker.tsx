import { useTranslation } from "react-i18next";

import type { BroadcastCategory } from "@entities/broadcasts/api";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { SegmentedPills } from "@shared/ui/SegmentedPills";

const CATEGORIES: BroadcastCategory[] = ["SERVICE", "MARKETING"];

interface CategoryPickerProps {
  value: BroadcastCategory;
  onChange: (value: BroadcastCategory) => void;
  disabled: boolean;
}

export function CategoryPicker({ value, onChange, disabled }: CategoryPickerProps) {
  const { t } = useTranslation();
  return (
    <Card>
      <Field label={t("broadcasts.editor.category")} hint={t(`broadcasts.editor.categoryHint.${value}`)}>
        <div>
          <SegmentedPills
            value={value}
            disabled={disabled}
            onChange={onChange}
            options={CATEGORIES.map((category) => ({ value: category, label: t(`broadcasts.editor.categoryOption.${category}`) }))}
          />
        </div>
      </Field>
    </Card>
  );
}
