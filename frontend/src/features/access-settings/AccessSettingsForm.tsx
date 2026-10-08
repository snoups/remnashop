import { CreditCard, ShieldCheck, UserPlus } from "lucide-react";
import { useEffect, useState, type ComponentType, type FormEvent, type ReactNode } from "react";
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
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Tag } from "@shared/ui/Tag";

const rowIconClassName =
  "flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground";

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

  const activeKey = MODES.find((m) => m.mode === mode)?.key ?? "public";

  return (
    <Card>
      <CardHeader
        icon={ShieldCheck}
        title={t("settings.access.title")}
        description={t("settings.access.description")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("settings.access.loadError")} />}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <fieldset disabled={!canManage} className="contents">
            <div className="flex flex-wrap gap-2 px-[12.5px]">
              {MODES.map((m) => (
                <ChoiceChip key={m.mode} active={mode === m.mode} onClick={() => setMode(m.mode)}>
                  {t(`settings.access.modes.${m.key}`)}
                </ChoiceChip>
              ))}
            </div>
            <p className="mt-2 px-[12.5px] text-[12px] text-muted-foreground">
              {t(`settings.access.modeHints.${activeKey}`)}
            </p>

            <div className="mt-2 flex flex-col gap-1 border-t border-white/[0.08] pt-2">
              <SwitchRow
                icon={UserPlus}
                label={t("settings.access.registrationLabel")}
                enabled={registrationEnabled}
                onChange={setRegistrationEnabled}
              />
              <SwitchRow
                icon={CreditCard}
                label={t("settings.access.paymentsLabel")}
                enabled={paymentsEnabled}
                onChange={setPaymentsEnabled}
                extra={
                  !paymentsEnabled && permissions.includes("PAYMENT_WAITLIST_VIEW") ? <WaitlistTag /> : null
                }
              />
            </div>
          </fieldset>

          {canManage && (
            <Button variant="accent" className="mt-4 w-fit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("common.saving") : t("common.save")}
            </Button>
          )}
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

interface SwitchRowProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  enabled: boolean;
  onChange: (value: boolean) => void;
  extra?: ReactNode;
}

function SwitchRow({ icon: Icon, label, enabled, onChange, extra }: SwitchRowProps) {
  return (
    <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]">
      <div className={rowIconClassName}>
        <Icon className="size-4" />
      </div>
      <p className="min-w-0 flex-1 text-[13px] font-medium text-foreground">{label}</p>
      {extra}
      <div className="mr-1 flex">
        <Switch checked={enabled} onChange={onChange} />
      </div>
    </div>
  );
}
