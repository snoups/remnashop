import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { InfoRow } from "@shared/ui/InfoRow";

/** A value row of the subscription dialog: a tap copies what it shows; an empty one is a dash and copies nothing. */
export function SubscriptionField({
  icon,
  label,
  value,
  copyValue = value,
  mono = false,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string | null | undefined;
  /** what a tap copies, when it isn't the shown value */
  copyValue?: string | null;
  mono?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <InfoRow icon={icon} label={label} mono={mono && Boolean(value)} copyValue={copyValue || undefined}>
      <span className="truncate">{value || t("common.none")}</span>
    </InfoRow>
  );
}
