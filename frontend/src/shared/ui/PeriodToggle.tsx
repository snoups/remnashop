import { useTranslation } from "react-i18next";

export type PeriodDays = 0 | 7 | 30 | 90;

const PERIOD_OPTIONS: PeriodDays[] = [7, 30, 90, 0];

export function PeriodToggle({
  value,
  onChange,
}: {
  value: PeriodDays;
  onChange: (days: PeriodDays) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="inline-flex rounded-full border border-border p-0.5">
      {PERIOD_OPTIONS.map((days) => (
        <button
          key={days}
          type="button"
          onClick={() => onChange(days)}
          className={`rounded-full px-3 py-1 text-[12px] font-semibold transition-colors ${
            value === days ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {days === 0 ? t("dashboard.periodAll") : t("dashboard.periodDays", { count: days })}
        </button>
      ))}
    </div>
  );
}
