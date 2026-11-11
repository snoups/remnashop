import { useTranslation } from "react-i18next";

import { listPanelSquads } from "@entities/subscriptions/api";
import type { MissingSquad, SquadReplacements } from "@entities/subscriptions/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Tag } from "@shared/ui/Tag";

const PLATE_CLASS = "rounded-xl bg-error/[0.06] p-3 shadow-[inset_0_0_0_1px_rgb(251_44_54/0.22)]";

// the translated sentence with the uuid set in mono, without markup in the locale
function withMonoUuid(text: string, uuid: string) {
  const [before, after] = text.split(uuid);
  return (
    <>
      {before}
      <span className="font-mono">{uuid}</span>
      {after}
    </>
  );
}

interface SquadReplacementsFieldProps {
  missing: MissingSquad[];
  value: SquadReplacements;
  onChange: (value: SquadReplacements) => void;
  /** bulk push: how many subscriptions hold each squad */
  showHolders?: boolean;
}

/** A replacement of the same kind, or none, for each squad the panel no longer has: one red plate per squad. */
export function SquadReplacementsField({
  missing,
  value,
  onChange,
  showHolders = false,
}: SquadReplacementsFieldProps) {
  const { t, i18n } = useTranslation();
  const [squadsState] = useAsyncResource(listPanelSquads);

  if (squadsState.kind === "loading") return <Spinner size="card" />;
  if (squadsState.kind === "error") return <ErrorState text={t("common.loadError")} />;

  const pick = (uuid: string, target: string | null) => onChange({ ...value, [uuid]: target });

  return (
    <div className="flex flex-col gap-3">
      {missing.map((squad) => (
        <div key={squad.uuid} className={`flex flex-col gap-1.5 ${PLATE_CLASS}`}>
          <div className="flex items-start justify-between gap-3 text-xs">
            <span className="min-w-0">{withMonoUuid(t("subscriptions.panelSync.squads.replace", { squad: squad.uuid }), squad.uuid)}</span>
            {showHolders && (
              <Tag>
                {t("subscriptions.panelSync.squads.held", {
                  count: squad.subscriptions,
                  formatted: squad.subscriptions.toLocaleString(i18n.language),
                })}
              </Tag>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            <ChoiceChip className="h-8" active={value[squad.uuid] == null} onClick={() => pick(squad.uuid, null)}>
              {t("subscriptions.panelSync.squads.drop")}
            </ChoiceChip>
            {squadsState.data.items
              .filter((candidate) => candidate.kind === squad.kind)
              .map((candidate) => (
                <ChoiceChip
                  className="h-8"
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
