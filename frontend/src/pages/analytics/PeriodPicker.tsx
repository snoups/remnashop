import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { ParseKeys } from "i18next";

import { periodParams } from "@entities/analytics/api";
import type { AnalyticsPeriod } from "@entities/analytics/api";
import { parseIsoDate, toIsoDate } from "@shared/lib/iso-date";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { Button } from "@shared/ui/Button";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { MonthCalendar } from "@shared/ui/MonthCalendar";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { periodLabel } from "@pages/analytics/period";
import { Pressable } from "@shared/ui/Pressable";

type PillValue = "7" | "30" | "90" | "365" | "custom";
type Draft = { kind: "all" } | { kind: "range"; from: string; to: string };

const DEFAULT_PERIOD: AnalyticsPeriod = { kind: "days", days: 30 };

function presetDrafts(now: Date): { key: string; label: ParseKeys; draft: Draft }[] {
  const y = now.getFullYear();
  const m = now.getMonth();
  const d = now.getDate();
  const day = (year: number, month: number, date: number) => toIsoDate(new Date(year, month, date));
  const today = day(y, m, d);
  const range = (from: string, to = today): Draft => ({ kind: "range", from, to });
  return [
    { key: "today", label: "common.today", draft: range(today) },
    { key: "yesterday", label: "common.yesterday", draft: range(day(y, m, d - 1), day(y, m, d - 1)) },
    { key: "thisWeek", label: "analytics.period.thisWeek", draft: range(day(y, m, d - ((now.getDay() + 6) % 7))) },
    { key: "thisMonth", label: "analytics.period.thisMonth", draft: range(day(y, m, 1)) },
    { key: "lastMonth", label: "analytics.period.lastMonth", draft: range(day(y, m - 1, 1), day(y, m, 0)) },
    { key: "thisYear", label: "analytics.period.thisYear", draft: range(day(y, 0, 1)) },
    { key: "allTime", label: "dashboard.periodAll", draft: { kind: "all" } },
  ];
}

function draftFrom(period: AnalyticsPeriod): Draft {
  if (period.kind !== "days") return period;
  const params = periodParams(period);
  return { kind: "range", from: params.get("period_from") ?? "", to: params.get("period_to") ?? "" };
}

function sameDraft(a: Draft, b: Draft): boolean {
  if (a.kind === "all" || b.kind === "all") return a.kind === b.kind;
  return a.from === b.from && a.to === b.to;
}

export function PeriodPicker({ period, onChange: setPeriod }: { period: AnalyticsPeriod; onChange: (period: AnalyticsPeriod) => void }) {
  const { t, i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>({ kind: "all" });
  const wrapperRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  const close = () => setIsOpen(false);
  useClickOutside([wrapperRef, popoverRef], isOpen, close);
  useCloseOnScroll(isOpen, popoverRef, close);

  const value: PillValue = period.kind === "days" ? (String(period.days) as PillValue) : "custom";
  const options: { value: PillValue; label: string }[] = [
    ...([7, 30, 90] as const).map((days) => ({ value: String(days) as PillValue, label: t("dashboard.periodDays", { count: days }) })),
    { value: "365", label: t("analytics.period.year") },
    {
      value: "custom",
      label: period.kind === "days" ? t("analytics.period.custom") : periodLabel(period, t, i18n.language),
    },
  ];

  const handleChange = (next: PillValue) => {
    if (next === "custom") {
      setDraft(draftFrom(period));
      setIsOpen(true);
      return;
    }
    setPeriod({ kind: "days", days: Number(next) as 7 | 30 | 90 | 365 });
    close();
  };

  const pickDay = (iso: string) => {
    if (draft.kind === "all" || draft.from === "" || draft.to !== "") {
      setDraft({ kind: "range", from: iso, to: "" });
    } else {
      setDraft(iso < draft.from ? { kind: "range", from: iso, to: draft.from } : { ...draft, to: iso });
    }
  };

  const formatDay = (iso: string) => parseIsoDate(iso)?.toLocaleDateString(i18n.language) ?? t("common.none");
  const from = draft.kind === "range" ? draft.from : "";
  const to = draft.kind === "range" ? draft.to : "";
  const canApply = draft.kind === "all" || (from !== "" && to !== "");

  return (
    <div ref={wrapperRef}>
      <SegmentedPills panel value={value} onChange={handleChange} options={options} />
      <PortalPopover
        open={isOpen}
        triggerRef={wrapperRef}
        popoverRef={popoverRef}
        align="right"
        glass
        maxHeight={420}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="w-[min(520px,calc(100vw-32px))] p-3"
      >
        <div className="grid gap-3 sm:grid-cols-[150px_minmax(0,1fr)]">
          <div className="grid grid-cols-2 gap-0.5 sm:flex sm:flex-col">
            {presetDrafts(new Date()).map((preset) => (
              <Pressable
                key={preset.key}
                type="button"
                onClick={() => setDraft(preset.draft)}
                className={`h-9 rounded-full px-3 text-left text-[13px] font-medium transition-colors ${
                  sameDraft(draft, preset.draft) ? "bg-accent text-primary" : "text-foreground hover:bg-white/[0.07]"
                }`}
              >
                {t(preset.label)}
              </Pressable>
            ))}
          </div>
          <div className="flex flex-col gap-2.5">
            <div className="grid grid-cols-2 gap-2">
              <div className="flex flex-col gap-1">
                <span className={EYEBROW_CLASS}>{t("analytics.period.start")}</span>
                <span className="text-[13px] font-medium tabular-nums text-foreground">{formatDay(from)}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className={EYEBROW_CLASS}>{t("analytics.period.end")}</span>
                <span className="text-[13px] font-medium tabular-nums text-foreground">{formatDay(to)}</span>
              </div>
            </div>
            {/* remounts on a new start so a preset jumps the view to its month */}
            <MonthCalendar key={from} value={from} rangeEnd={to} onPick={pickDay} />
            <div className="flex justify-end gap-2">
              <Button
                variant="glass"
                onClick={() => {
                  setPeriod(DEFAULT_PERIOD);
                  close();
                }}
              >
                {t("common.reset")}
              </Button>
              <Button
                variant="glassAccent"
                disabled={!canApply}
                onClick={() => {
                  setPeriod(draft);
                  close();
                }}
              >
                {t("analytics.period.apply")}
              </Button>
            </div>
          </div>
        </div>
      </PortalPopover>
    </div>
  );
}
