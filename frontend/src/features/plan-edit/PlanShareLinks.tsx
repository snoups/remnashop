import { useTranslation } from "react-i18next";

import { getPlanShareUrls } from "@entities/plans/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { Field } from "@shared/ui/Field";

export function PlanShareLinks({ planId }: { planId: number }) {
  const { t } = useTranslation();
  const [state] = useAsyncResource((signal) => getPlanShareUrls(planId, signal), { deps: [planId] });
  if (state.kind !== "ready") return null;
  const { bot_url: botUrl, webcabinet_url: cabinetUrl } = state.data;
  return (
    <>
      {botUrl && (
        <Field label={t("plans.edit.botLinkLabel")} className="sm:col-span-2">
          <CopyableValue value={botUrl} />
        </Field>
      )}
      {cabinetUrl && (
        <Field label={t("plans.edit.cabinetLinkLabel")} className="sm:col-span-2">
          <CopyableValue value={cabinetUrl} />
        </Field>
      )}
    </>
  );
}
