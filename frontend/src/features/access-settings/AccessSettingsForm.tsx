import { CreditCard, DoorOpen, ShieldCheck, UserPlus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { publishAccessSettings } from "@entities/settings/access-sync";
import {
  getAccessSettings,
  getPaymentWaitlistCount,
  updateAccessSettings,
  type AccessMode,
  type AccessSettings,
} from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { PillTabs } from "@shared/ui/PillTabs";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { SettingsRow } from "@shared/ui/SettingsRow";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { SETTINGS_ROWS_CLASS } from "@shared/ui/classes";
import { Tag } from "@shared/ui/Tag";

const MODES = [
  { mode: "PUBLIC", key: "public" },
  { mode: "INVITED", key: "invited" },
  { mode: "RESTRICTED", key: "restricted" },
] as const;

export function AccessSettingsForm() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("ACCESS_SETTINGS_MANAGE");
  const [state, , setData] = useAsyncResource(getAccessSettings);
  const [mode, setMode] = useState<AccessMode>("PUBLIC");
  const [registrationEnabled, setRegistrationEnabled] = useState(true);
  const [paymentsEnabled, setPaymentsEnabled] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (state.kind !== "ready") return;
    setMode(state.data.mode);
    setRegistrationEnabled(state.data.registration_enabled);
    setPaymentsEnabled(state.data.payments_enabled);
  }, [state]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (state.kind !== "ready") return;
    const changes: Partial<AccessSettings> = {};
    if (mode !== state.data.mode) changes.mode = mode;
    if (registrationEnabled !== state.data.registration_enabled) {
      changes.registration_enabled = registrationEnabled;
    }
    if (paymentsEnabled !== state.data.payments_enabled) changes.payments_enabled = paymentsEnabled;
    if (Object.keys(changes).length === 0) return;
    setIsSubmitting(true);
    try {
      const settings = await updateAccessSettings(changes);
      setData(settings);
      publishAccessSettings(settings);
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const dirty =
    state.kind === "ready" &&
    (mode !== state.data.mode ||
      registrationEnabled !== state.data.registration_enabled ||
      paymentsEnabled !== state.data.payments_enabled);
  const activeKey = MODES.find((m) => m.mode === mode)?.key ?? "public";

  return (
    <Card>
      <CardHeader
        icon={ShieldCheck}
        title={t("settings.access.title")}
        description={t("settings.access.description")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <fieldset disabled={!canManage} className="contents">
            <div className={SETTINGS_ROWS_CLASS}>
              <SettingsRow
                icon={DoorOpen}
                label={t("settings.access.modeLabel")}
                description={t(`settings.access.modeHints.${activeKey}`)}
              >
                <PillTabs
                  items={MODES.map((m) => ({ key: m.mode, label: t(`settings.access.modes.${m.key}`) }))}
                  activeKey={mode}
                  onSelect={setMode}
                  disabled={!canManage}
                />
              </SettingsRow>
              <SettingsRow icon={UserPlus} label={t("settings.access.registrationLabel")}>
                <Switch checked={registrationEnabled} onChange={setRegistrationEnabled} />
              </SettingsRow>
              <SettingsRow icon={CreditCard} label={t("settings.access.paymentsLabel")}>
                {!paymentsEnabled && permissions.includes("PAYMENT_WAITLIST_VIEW") && <WaitlistTag />}
                <Switch checked={paymentsEnabled} onChange={setPaymentsEnabled} />
              </SettingsRow>
            </div>
          </fieldset>

          {canManage && <SaveFooter dirty={dirty} saving={isSubmitting} />}
        </form>
      )}
    </Card>
  );
}

function WaitlistTag() {
  const { t } = useTranslation();
  const [state] = useAsyncResource(getPaymentWaitlistCount);
  if (state.kind !== "ready") return null;
  return <Tag>{t("settings.access.waitlist", { count: state.data.total })}</Tag>;
}
