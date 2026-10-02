import { motion } from "motion/react";
import { useId } from "react";
import { useTranslation } from "react-i18next";

import { TAP_PILL_SCALE } from "@shared/lib/bounceState";
import { ActivePill } from "@shared/ui/ActivePill";

export type PeriodDays = 0 | 7 | 30 | 90;

const PERIODS: PeriodDays[] = [7, 30, 90, 0];

export function PeriodPills({
  value,
  onChange,
}: {
  value: PeriodDays;
  onChange: (days: PeriodDays) => void;
}) {
  const { t } = useTranslation();
  const pillId = useId();

  return (
    <motion.nav
      layoutScroll
      className="no-scrollbar flex max-w-full gap-1 overflow-x-auto rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md"
    >
      {PERIODS.map((days) => (
        <motion.button
          key={days}
          type="button"
          onClick={() => onChange(days)}
          initial="rest"
          whileTap="tap"
          className="group relative isolate shrink-0 whitespace-nowrap rounded-full"
        >
          {/* only the pill scales, so the label stays crisp */}
          {value === days ? (
            <ActivePill layoutId={pillId} />
          ) : (
            <motion.span
              variants={{ rest: { scale: 1 }, tap: { scale: TAP_PILL_SCALE } }}
              className="absolute inset-0 rounded-full transition-colors group-hover:bg-white/[0.06]"
            />
          )}
          <span
            className={`relative z-10 block px-3.5 py-1 text-sm font-medium ${
              value === days ? "text-primary" : "text-foreground"
            }`}
          >
            {days === 0 ? t("dashboard.periodAll") : t("dashboard.periodDays", { count: days })}
          </span>
        </motion.button>
      ))}
    </motion.nav>
  );
}
