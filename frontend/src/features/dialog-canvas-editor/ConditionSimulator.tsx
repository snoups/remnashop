import { useTranslation } from "react-i18next";

interface ConditionSimulatorProps {
  conditions: string[];
  toggles: Record<string, boolean>;
  onToggle: (condition: string, value: boolean) => void;
}

export function ConditionSimulator({ conditions, toggles, onToggle }: ConditionSimulatorProps) {
  const { t } = useTranslation();
  if (conditions.length === 0) return null;

  return (
    <div className="mt-3 rounded-2xl border border-white/[0.08] bg-white/[0.03] p-3">
      <h4 className="mb-2 text-[12px] font-semibold text-foreground">{t("dialogs.simulator.title")}</h4>
      <div className="flex flex-col gap-1.5">
        {conditions.map((condition) => (
          <label key={condition} className="flex items-center justify-between gap-2 text-[12.5px]">
            <span className="rounded-full border border-white/[0.12] px-2 py-0.5 text-[11px] text-foreground/80">
              {condition}
            </span>
            <input
              type="checkbox"
              checked={toggles[condition] ?? true}
              onChange={(event) => onToggle(condition, event.target.checked)}
            />
          </label>
        ))}
      </div>
    </div>
  );
}
