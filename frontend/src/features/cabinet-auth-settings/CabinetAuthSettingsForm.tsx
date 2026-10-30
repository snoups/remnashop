import { Bot, DoorOpen, Mail, MailCheck, ShieldCheck, Smartphone } from "lucide-react";
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
  type CaptchaProvider,
  type OAuthSettings,
  type UpdateCabinetAuthSettingsPayload,
  type UpdateOAuthSettingsPayload,
} from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GoogleIcon, TelegramIcon, YandexIcon } from "@shared/ui/BrandIcons";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ErrorState } from "@shared/ui/EmptyState";
import { Field } from "@shared/ui/Field";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { ProviderPanel } from "@features/oauth-settings/OAuthSettingsForm";

import { AllowedDomainsDialog } from "./AllowedDomainsDialog";
import { CabinetMethodGuideDialog, type GuideMethod } from "./CabinetMethodGuideDialog";

type MethodKey =
  | "telegram_enabled"
  | "telegram_deeplink_enabled"
  | "telegram_oauth_enabled"
  | "google_enabled"
  | "yandex_enabled"
  | "email_enabled";

type OAuthMethod = "telegram" | "google" | "yandex";

const METHODS: { key: MethodKey; label: Exclude<GuideMethod, "captcha">; icon: ComponentType<{ className?: string }>; oauth?: OAuthMethod }[] = [
  { key: "telegram_enabled", label: "telegramMiniApp", icon: Smartphone },
  { key: "telegram_deeplink_enabled", label: "telegramDeeplink", icon: Bot },
  { key: "telegram_oauth_enabled", label: "telegramOAuth", icon: TelegramIcon, oauth: "telegram" },
  { key: "google_enabled", label: "google", icon: GoogleIcon, oauth: "google" },
  { key: "yandex_enabled", label: "yandex", icon: YandexIcon, oauth: "yandex" },
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

  const saveDomains = async (patch: UpdateCabinetAuthSettingsPayload) => {
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
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <div className="mt-4">
          <div className="flex flex-col [&>:not(:last-child)>:first-child]:border-b [&>:not(:last-child)>:first-child]:border-border/50">
            {METHODS.map(({ key, label, icon: Icon, oauth }) => {
              const isConfigured =
                label === "telegramMiniApp" || label === "telegramDeeplink"
                  ? isBotConfigured
                  : label === "email"
                    ? isEmailConfigured
                    : undefined;
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
                            : label === "telegramMiniApp"
                              ? t("settings.cabinetAuth.telegramMiniAppHint")
                              : label === "telegramDeeplink"
                                ? t("settings.cabinetAuth.telegramDeeplinkHint")
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
                <MailCheck className="size-4" />
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
          <div className="mt-2 border-t border-white/[0.08] pt-2">
            <CaptchaPanel settings={state.data} canManage={canManage} onSaved={setData} />
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

const CAPTCHA_PROVIDERS: { value: CaptchaProvider; label: string }[] = [
  { value: "TURNSTILE", label: "Cloudflare Turnstile" },
  { value: "HCAPTCHA", label: "hCaptcha" },
];

function CaptchaPanel({
  settings,
  canManage,
  onSaved,
}: {
  settings: CabinetAuthSettings;
  canManage: boolean;
  onSaved: (settings: CabinetAuthSettings) => void;
}) {
  const { t } = useTranslation();
  const [provider, setProvider] = useState(settings.captcha_provider);
  const [siteKey, setSiteKey] = useState("");
  const [secretKey, setSecretKey] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      onSaved(
        await updateCabinetAuthSettings({
          captcha_provider: provider,
          ...(siteKey && { captcha_site_key: siteKey }),
          ...(secretKey && { captcha_secret_key: secretKey }),
        }),
      );
      setSiteKey("");
      setSecretKey("");
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <ProviderPanel
      icon={ShieldCheck}
      label={t("settings.cabinetAuth.captcha.title")}
      guide={<CabinetMethodGuideDialog method="captcha" />}
      isConfigured={settings.is_captcha_configured}
      isEnabled={settings.captcha_enabled}
      onToggle={async (next) => onSaved(await updateCabinetAuthSettings({ captcha_enabled: next }))}
      canToggle={canManage}
      canEdit={canManage}
      extra={
        <Field label={t("settings.cabinetAuth.captcha.provider")}>
          <SegmentedPills value={provider} onChange={setProvider} options={CAPTCHA_PROVIDERS} disabled={!canManage} stretch />
        </Field>
      }
      fields={[
        {
          key: "captcha_site_key",
          label: t("settings.cabinetAuth.captcha.siteKey"),
          value: siteKey,
          onChange: setSiteKey,
        },
        {
          key: "captcha_secret_key",
          label: t("settings.cabinetAuth.captcha.secretKey"),
          value: secretKey,
          onChange: setSecretKey,
          secret: true,
        },
      ]}
      footer={
        canManage && (
          <Button variant="accent" className="w-fit" type="submit" disabled={isSubmitting}>
            {isSubmitting ? t("common.saving") : t("common.save")}
          </Button>
        )
      }
      onSubmit={(event) => void handleSubmit(event)}
    />
  );
}
