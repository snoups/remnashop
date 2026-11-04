import { useTranslation } from "react-i18next";

import { getPlanShareUrls } from "@entities/plans/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Field } from "@shared/ui/glass/Field";
import { CopyInput } from "@shared/ui/glass/Input";

export function PlanShareLinks({ planId }: { planId: number }) {
  const { t } = useTranslation();
  const [state] = useAsyncResource((signal) => getPlanShareUrls(planId, signal), { deps: [planId] });
  if (state.kind !== "ready") return null;
  const { bot_url: botUrl, webcabinet_url: cabinetUrl } = state.data;
  return (
    <>
      {botUrl && (
        <div className="sm:col-span-2">
          <Field label={t("plans.edit.botLinkLabel")}>
            <CopyInput value={botUrl} />
          </Field>
        </div>
      )}
      {cabinetUrl && (
        <div className="sm:col-span-2">
          <Field label={t("plans.edit.cabinetLinkLabel")}>
            <CopyInput value={cabinetUrl} />
          </Field>
        </div>
      )}
    </>
  );
}
