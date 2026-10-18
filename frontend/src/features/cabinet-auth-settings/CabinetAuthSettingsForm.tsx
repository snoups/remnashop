import { DoorOpen, Globe, Mail, MailX } from "lucide-react";
import { useEffect, useState, type ComponentType, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getCabinetAuthSettings,
  getOAuthSettings,
  updateCabinetAuthSettings,
  updateOAuthSettings,
  type CabinetAuthSettings,
  type OAuthSettings,
} from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { TelegramIcon } from "@shared/ui/BrandIcons";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Field } from "@shared/ui/Field";
import { Switch } from "@shared/ui/Switch";
import { TextArea } from "@shared/ui/TextInput";
import { ProviderPanel } from "@features/oauth-settings/OAuthSettingsForm";

type MethodKey = "telegram_enabled" | "google_enabled" | "yandex_enabled" | "email_enabled";

type OAuthMethod = "google" | "yandex";

const METHODS: { key: MethodKey; label: "telegram" | OAuthMethod | "email"; icon: ComponentType<{ className?: string }>; oauth?: OAuthMethod }[] = [
  { key: "telegram_enabled", label: "telegram", icon: TelegramIcon },
  { key: "google_enabled", label: "google", icon: Globe, oauth: "google" },
  { key: "yandex_enabled", label: "yandex", icon: Globe, oauth: "yandex" },
  { key: "email_enabled", label: "email", icon: Mail },
];

export function CabinetAuthSettingsForm() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("CABINET_AUTH_SETTINGS_MANAGE");
  const canViewOAuth = permissions.includes("OAUTH_SETTINGS_VIEW");
  const [state, , setData] = useAsyncResource(getCabinetAuthSettings);
  // Google/Yandex credentials live in OAuth settings; without that permission only the switches show
  const [oauthState, , setOAuthData] = useAsyncResource((signal) =>
    canViewOAuth ? getOAuthSettings(signal) : Promise.resolve(null),
  );
  const oauthSettings = oauthState.kind === "ready" ? oauthState.data : null;
  const [pendingKey, setPendingKey] = useState<MethodKey | "domains" | null>(null);

  const handleToggle = async (key: MethodKey, next: boolean) => {
    setPendingKey(key);
    try {
      setData(await updateCabinetAuthSettings({ [key]: next }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setPendingKey(null);
    }
  };

  const [domainsText, setDomainsText] = useState("");
  const savedDomains = state.kind === "ready" ? state.data.allowed_email_domains.join("\n") : null;
  useEffect(() => {
    if (savedDomains !== null) setDomainsText(savedDomains);
  }, [savedDomains]);

  const saveDomains = async (patch: Partial<CabinetAuthSettings>) => {
    setPendingKey("domains");
    try {
      setData(await updateCabinetAuthSettings(patch));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setPendingKey(null);
    }
  };

  return (
    <Card>
      <CardHeader
        icon={DoorOpen}
        title={t("settings.cabinetAuth.title")}
        description={t("settings.cabinetAuth.description")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("settings.cabinetAuth.loadError")} />}
      {state.kind === "ready" && (
        <div className="mt-4 flex flex-col gap-1">
          {METHODS.map(({ key, label, icon: Icon, oauth }) =>
            oauth && oauthSettings ? (
              <OAuthMethodPanel
                key={key}
                method={oauth}
                icon={Icon}
                label={t(`settings.cabinetAuth.methods.${label}`)}
                oauthSettings={oauthSettings}
                onSaved={setOAuthData}
                isEnabled={state.data[key]}
                onToggle={async (next) => setData(await updateCabinetAuthSettings({ [key]: next }))}
                canToggle={canManage && pendingKey === null}
              />
            ) : (
              <div
                key={key}
                className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
              >
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                  <Icon className="size-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-foreground">
                    {t(`settings.cabinetAuth.methods.${label}`)}
                  </p>
                  {oauth && (
                    <p className="text-[12px] text-muted-foreground">
                      {t("settings.oauth.redirectHint", { path: `/login/callback/${oauth}` })}
                    </p>
                  )}
                  {label === "telegram" && (
                    <p className="text-[12px] text-muted-foreground">{t("settings.cabinetAuth.telegramHint")}</p>
                  )}
                </div>
                <div className="mr-1 flex">
                  <Switch
                    checked={state.data[key]}
                    onChange={(value) => void handleToggle(key, value)}
                    disabled={!canManage || pendingKey !== null}
                  />
                </div>
              </div>
            ),
          )}
          <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
              <MailX className="size-4" />
            </div>
            <p className="min-w-0 flex-1 text-[13px] font-medium text-foreground">
              {t("settings.cabinetAuth.restrictDomains")}
            </p>
            <div className="mr-1 flex">
              <Switch
                checked={state.data.restrict_email_domains}
                onChange={(value) => void saveDomains({ restrict_email_domains: value })}
                disabled={!canManage || pendingKey !== null}
              />
            </div>
          </div>
          {state.data.restrict_email_domains && (
            <Field
              label={t("settings.cabinetAuth.allowedDomains")}
              htmlFor="cabinet-allowed-domains"
              hint={t("settings.cabinetAuth.allowedDomainsHint")}
              className="mt-2 px-[12.5px]"
            >
              <TextArea
                id="cabinet-allowed-domains"
                value={domainsText}
                onChange={(event) => setDomainsText(event.target.value)}
                onBlur={() => {
                  const next = domainsText.split(/[\s,;]+/).filter(Boolean);
                  if (next.join("\n") !== savedDomains)
                    void saveDomains({ allowed_email_domains: next });
                }}
                disabled={!canManage}
                spellCheck={false}
                rows={6}
                className="mt-1 w-full"
              />
            </Field>
          )}
        </div>
      )}
    </Card>
  );
}

interface OAuthMethodPanelProps {
  method: OAuthMethod;
  icon: ComponentType<{ className?: string }>;
  label: string;
  oauthSettings: OAuthSettings;
  onSaved: (settings: OAuthSettings) => void;
  isEnabled: boolean;
  onToggle: (next: boolean) => Promise<void>;
  canToggle: boolean;
}

function OAuthMethodPanel({
  method,
  icon,
  label,
  oauthSettings,
  onSaved,
  isEnabled,
  onToggle,
  canToggle,
}: OAuthMethodPanelProps) {
  const { t } = useTranslation();
  const canManageOAuth = usePermissions().includes("OAUTH_SETTINGS_MANAGE");
  const [clientId, setClientId] = useState("");
  const [clientSecret, setClientSecret] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!clientId && !clientSecret) {
      toast.error(t("settings.oauth.errorEmptyFields"));
      return;
    }
    setIsSubmitting(true);
    try {
      const id = clientId || undefined;
      const secret = clientSecret || undefined;
      onSaved(
        await updateOAuthSettings(
          method === "google"
            ? { google_client_id: id, google_client_secret: secret }
            : { yandex_client_id: id, yandex_client_secret: secret },
        ),
      );
      setClientId("");
      setClientSecret("");
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <ProviderPanel
        icon={icon}
        label={label}
        isConfigured={oauthSettings[`is_${method}_configured`]}
        isEnabled={isEnabled}
        onToggle={onToggle}
        canToggle={canToggle}
        hint={t("settings.oauth.redirectHint", { path: `/login/callback/${method}` })}
        fields={[
          {
            key: `${method}_client_id`,
            label: t("settings.oauth.clientIdLabel"),
            value: clientId,
            onChange: setClientId,
          },
          {
            key: `${method}_client_secret`,
            label: t("settings.oauth.clientSecretLabel"),
            value: clientSecret,
            onChange: setClientSecret,
          },
        ]}
        footer={
          canManageOAuth && (
            <Button variant="accent" className="w-fit" type="submit" disabled={isSubmitting}>
              {isSubmitting ? t("common.saving") : t("common.save")}
            </Button>
          )
        }
      />
    </form>
  );
}
