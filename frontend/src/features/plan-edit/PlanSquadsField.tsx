import { useTranslation } from "react-i18next";

import type { PlanSquads } from "@entities/plans/api";
import { listPanelSquads, type PanelSquad } from "@entities/subscriptions/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Spinner } from "@shared/ui/Spinner";

/** Squads from the panel; one the plan still holds but the panel dropped shows by its uuid, so it can be unpicked. */
export function PlanSquadsField({ value, onChange }: { value: PlanSquads; onChange: (value: PlanSquads) => void }) {
  const { t } = useTranslation();
  const [squadsState] = useAsyncResource(listPanelSquads);

  if (squadsState.kind === "loading") return <Spinner size="card" />;
  if (squadsState.kind === "error") return <ErrorState text={t("common.loadError")} />;

  const squads = squadsState.data.items;
  const withMissing = (kind: PanelSquad["kind"], picked: string[]): PanelSquad[] => [
    ...squads.filter((squad) => squad.kind === kind),
    ...picked
      .filter((uuid) => !squads.some((squad) => squad.uuid === uuid))
      .map((uuid) => ({ uuid, name: `${uuid.slice(0, 8)}…`, kind })),
  ];
  const internal = withMissing("internal", value.internal_squads);
  const external = withMissing("external", value.external_squad ? [value.external_squad] : []);

  const toggleInternal = (uuid: string) =>
    onChange({
      ...value,
      internal_squads: value.internal_squads.includes(uuid)
        ? value.internal_squads.filter((picked) => picked !== uuid)
        : [...value.internal_squads, uuid],
    });

  return (
    <>
      <Field label={t("plans.edit.internalSquadsLabel")} required>
        {internal.length === 0 ? (
          <p className="text-[12px] text-muted-foreground">{t("plans.edit.squadsEmpty")}</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {internal.map((squad) => (
              <ChoiceChip
                className="h-9"
                key={squad.uuid}
                active={value.internal_squads.includes(squad.uuid)}
                onClick={() => toggleInternal(squad.uuid)}
              >
                {squad.name}
              </ChoiceChip>
            ))}
          </div>
        )}
      </Field>
      {external.length > 0 && (
        <Field label={t("plans.edit.externalSquadLabel")}>
          <div className="flex flex-wrap gap-1.5">
            <ChoiceChip
              className="h-9"
              active={value.external_squad === null}
              onClick={() => onChange({ ...value, external_squad: null })}
            >
              {t("plans.edit.externalSquadNone")}
            </ChoiceChip>
            {external.map((squad) => (
              <ChoiceChip
                className="h-9"
                key={squad.uuid}
                active={value.external_squad === squad.uuid}
                onClick={() => onChange({ ...value, external_squad: squad.uuid })}
              >
                {squad.name}
              </ChoiceChip>
            ))}
          </div>
        </Field>
      )}
    </>
  );
}
