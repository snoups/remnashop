import { useTranslation } from "react-i18next";

import type { BroadcastCategory } from "@entities/broadcasts/api";
import { Tags } from "lucide-react";

import { Row } from "@shared/ui/glass/Row";
import { PillTabs } from "@shared/ui/PillTabs";

const CATEGORIES: BroadcastCategory[] = ["SERVICE", "MARKETING"];

interface CategoryPickerProps {
  value: BroadcastCategory;
  onChange: (value: BroadcastCategory) => void;
  disabled: boolean;
}

export function CategoryPicker({ value, onChange, disabled }: CategoryPickerProps) {
  const { t } = useTranslation();
  return (
    <Row
      icon={Tags}
      label={t("broadcasts.editor.category")}
      description={t(`broadcasts.editor.categoryHint.${value}`)}
    >
      <PillTabs
        items={CATEGORIES.map((category) => ({ key: category, label: t(`broadcasts.editor.categoryOption.${category}`) }))}
        activeKey={value}
        onSelect={onChange}
        disabled={disabled}
      />
    </Row>
  );
}
