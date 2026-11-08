import { useTranslation } from "react-i18next";

import { listPanelSquads } from "@entities/subscriptions/api";
import type { MissingSquad, SquadReplacements } from "@entities/subscriptions/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Spinner } from "@shared/ui/Spinner";

interface SquadReplacementsFieldProps {
  missing: MissingSquad[];
  value: SquadReplacements;
  onChange: (value: SquadReplacements) => void;
  /** bulk push: how many subscriptions hold each squad */
  showHolders?: boolean;
}

/** A replacement of the same kind, or none, for each squad the panel no longer has. */
export function SquadReplacementsField({ missing, value, onChange, showHolders = false }: SquadReplacementsFieldProps) {
  const { t, i18n } = useTranslation();
  const [squadsState] = useAsyncResource(listPanelSquads);

  if (squadsState.kind === "loading") return <Spinner size="card" />;
  if (squadsState.kind === "error") return <ErrorState text={t("common.loadError")} />;

  const pick = (uuid: string, target: string | null) => onChange({ ...value, [uuid]: target });

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <span className="text-[13px] font-medium">{t("subscriptions.panelSync.squads.title")}</span>
        <p className="text-[12px] text-muted-foreground">{t("subscriptions.panelSync.squads.hint")}</p>
      </div>
      {missing.map((squad) => (
        <div key={squad.uuid} className="flex flex-col gap-1.5">
          <div className="flex items-baseline justify-between gap-3 text-[12px]">
            <span className="font-mono">{`${squad.uuid.slice(0, 8)}…`}</span>
            {showHolders && (
              <span className="text-muted-foreground">
                {t("subscriptions.panelSync.squads.held", {
                  count: squad.subscriptions,
                  formatted: squad.subscriptions.toLocaleString(i18n.language),
                })}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <ChoiceChip className="h-9" active={value[squad.uuid] == null} onClick={() => pick(squad.uuid, null)}>
              {t("subscriptions.panelSync.squads.drop")}
            </ChoiceChip>
            {squadsState.data.items
              .filter((candidate) => candidate.kind === squad.kind)
              .map((candidate) => (
                <ChoiceChip
                  className="h-9"
                  key={candidate.uuid}
                  active={value[squad.uuid] === candidate.uuid}
                  onClick={() => pick(squad.uuid, candidate.uuid)}
                >
                  {candidate.name}
                </ChoiceChip>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
