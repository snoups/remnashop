import { motion } from "motion/react";
import { useTranslation } from "react-i18next";

import { useBounceStrength } from "@shared/lib/bounceState";
import type { PeriodDays } from "@shared/ui/PeriodToggle";

const PERIODS: PeriodDays[] = [7, 30, 90, 0];

export function PeriodPills({
  value,
  onChange,
  ariaLabel,
}: {
  value: PeriodDays;
  onChange: (days: PeriodDays) => void;
  ariaLabel: string;
}) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();

  return (
    <nav
      aria-label={ariaLabel}
      className="no-scrollbar flex max-w-full gap-1 overflow-x-auto rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md"
    >
      {PERIODS.map((days) => (
        <motion.button
          key={days}
          type="button"
          aria-pressed={value === days}
          onClick={() => onChange(days)}
          initial="rest"
          whileTap="tap"
          className="group relative isolate shrink-0 whitespace-nowrap rounded-full"
        >
          {/* only the pill scales, so the label stays crisp */}
          <motion.span
            aria-hidden
            variants={{ rest: { scale: 1 }, tap: { scale: 1 + 0.05 * bounceStrength } }}
            className={`absolute inset-0 rounded-full transition-colors ${
              value === days ? "bg-accent" : "group-hover:bg-white/[0.06]"
            }`}
          />
          <span
            className={`relative z-10 block px-3.5 py-1 text-sm font-medium ${
              value === days ? "text-primary" : "text-foreground"
            }`}
          >
            {days === 0 ? t("dashboard.periodAll") : t("dashboard.periodDays", { count: days })}
          </span>
        </motion.button>
      ))}
    </nav>
  );
}
