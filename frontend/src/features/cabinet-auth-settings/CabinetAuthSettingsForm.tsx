import { DoorOpen, Globe, Mail, MailX } from "lucide-react";
import { useState, type ComponentType, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  getBotSettings,
  getCabinetAuthSettings,
  getEmailSettings,
  getOAuthSettings,
  updateCabinetAuthSettings,
  updateOAuthSettings,
  type CabinetAuthSettings,
  type OAuthSettings,
  type UpdateOAuthSettingsPayload,
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
import { Switch } from "@shared/ui/Switch";
import { ProviderPanel } from "@features/oauth-settings/OAuthSettingsForm";

import { AllowedDomainsDialog } from "./AllowedDomainsDialog";
import { CabinetMethodGuideDialog, type GuideMethod } from "./CabinetMethodGuideDialog";

type MethodKey =
  | "telegram_enabled"
  | "telegram_oauth_enabled"
  | "google_enabled"
  | "yandex_enabled"
  | "email_enabled";

type OAuthMethod = "telegram" | "google" | "yandex";

const METHODS: { key: MethodKey; label: GuideMethod; icon: ComponentType<{ className?: string }>; oauth?: OAuthMethod }[] = [
  { key: "telegram_enabled", label: "telegramBot", icon: TelegramIcon },
  { key: "telegram_oauth_enabled", label: "telegramOAuth", icon: TelegramIcon, oauth: "telegram" },
  { key: "google_enabled", label: "google", icon: Globe, oauth: "google" },
  { key: "yandex_enabled", label: "yandex", icon: Globe, oauth: "yandex" },
  { key: "email_enabled", label: "email", icon: Mail },
];

export function CabinetAuthSettingsForm({ emailVersion }: { emailVersion: number }) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("CABINET_AUTH_SETTINGS_MANAGE");
  const canViewOAuth = permissions.includes("OAUTH_SETTINGS_VIEW");
  const canViewBot = permissions.includes("BOT_SETTINGS_VIEW");
  const canViewEmail = permissions.includes("EMAIL_SETTINGS_VIEW");
  const [state, , setData] = useAsyncResource(getCabinetAuthSettings);
  // OAuth credentials live in OAuth settings; without that permission only the switches show
  const [oauthState, , setOAuthData] = useAsyncResource((signal) =>
    canViewOAuth ? getOAuthSettings(signal) : Promise.resolve(null),
  );
  const oauthSettings = oauthState.kind === "ready" ? oauthState.data : null;
  const [botState] = useAsyncResource((signal) =>
    canViewBot ? getBotSettings(signal) : Promise.resolve(null),
  );
  const isBotConfigured = botState.kind === "ready" ? botState.data?.is_configured : undefined;
  const [emailState] = useAsyncResource(
    (signal) => (canViewEmail ? getEmailSettings(signal) : Promise.resolve(null)),
    { deps: [emailVersion], keepData: true },
  );
  const isEmailConfigured = emailState.kind === "ready" ? emailState.data?.is_configured : undefined;
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

  const [isDomainsOpen, setIsDomainsOpen] = useState(false);

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
        <div className="mt-4">
          <div className="flex flex-col [&>:not(:last-child)>:first-child]:border-b [&>:not(:last-child)>:first-child]:border-border/50">
            {METHODS.map(({ key, label, icon: Icon, oauth }) => {
              const isConfigured =
                label === "telegramBot" ? isBotConfigured : label === "email" ? isEmailConfigured : undefined;
              return oauth && oauthSettings ? (
                <OAuthMethodPanel
                  key={key}
                  method={oauth}
                  icon={Icon}
                  label={t(`settings.cabinetAuth.methods.${label}`)}
                  guide={<CabinetMethodGuideDialog method={label} />}
                  oauthSettings={oauthSettings}
                  onSaved={setOAuthData}
                  isEnabled={state.data[key]}
                  onToggle={async (next) => setData(await updateCabinetAuthSettings({ [key]: next }))}
                  canToggle={canManage && pendingKey === null}
                />
              ) : (
                <div key={key}>
                  <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                      <Icon className="size-4" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] font-medium text-foreground">
                        {t(`settings.cabinetAuth.methods.${label}`)}
                      </p>
                      {isConfigured !== undefined ? (
                        <p className="text-[12px]">
                          {isConfigured ? (
                            <span className="text-success">{t("settings.oauth.configured")}</span>
                          ) : (
                            <span className="text-warning">{t("settings.oauth.notConfigured")}</span>
                          )}
                        </p>
                      ) : (
                        <p className="text-[12px] text-muted-foreground">
                          {oauth
                            ? t("settings.oauth.redirectHint", { path: `/login/callback/${oauth}` })
                            : label === "telegramBot"
                              ? t("settings.cabinetAuth.telegramBotHint")
                              : t("settings.cabinetAuth.emailHint")}
                        </p>
                      )}
                    </div>
                    <CabinetMethodGuideDialog method={label} />
                    <div className="mr-1 flex">
                      <Switch
                        checked={state.data[key]}
                        onChange={(value) => void handleToggle(key, value)}
                        // switching off stays possible after the bot token or SMTP is removed
                        disabled={
                          !canManage || pendingKey !== null || (isConfigured === false && !state.data[key])
                        }
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-2 border-t border-white/[0.08] pt-2">
            <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
                <MailX className="size-4" />
              </div>
              <p className="min-w-0 flex-1 text-[13px] font-medium text-foreground">
                {t("settings.cabinetAuth.restrictDomains")}
              </p>
              <Button variant="secondary" size="sm" type="button" onClick={() => setIsDomainsOpen(true)}>
                {t("settings.cabinetAuth.domainsList")}
              </Button>
              <div className="mr-1 flex">
                <Switch
                  checked={state.data.restrict_email_domains}
                  onChange={(value) => void saveDomains({ restrict_email_domains: value })}
                  disabled={!canManage || pendingKey !== null}
                />
              </div>
            </div>
          </div>
          {isDomainsOpen && (
            <AllowedDomainsDialog
              domains={state.data.allowed_email_domains}
              canManage={canManage}
              onSaved={setData}
              onClose={() => setIsDomainsOpen(false)}
            />
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
  guide: ReactNode;
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
  guide,
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
      const payloads: Record<OAuthMethod, UpdateOAuthSettingsPayload> = {
        telegram: { telegram_client_id: id, telegram_client_secret: secret },
        google: { google_client_id: id, google_client_secret: secret },
        yandex: { yandex_client_id: id, yandex_client_secret: secret },
      };
      onSaved(await updateOAuthSettings(payloads[method]));
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
    <ProviderPanel
      icon={icon}
      label={label}
      guide={guide}
      isConfigured={oauthSettings[`is_${method}_configured`]}
      isEnabled={isEnabled}
      onToggle={onToggle}
      canToggle={canToggle}
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
      onSubmit={(event) => void handleSubmit(event)}
    />
  );
}
