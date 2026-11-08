import { Bot, DoorOpen, Mail, ShieldCheck, Smartphone } from "lucide-react";
import { useEffect, useState, type ComponentType, type FormEvent } from "react";
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
  type UpdateCabinetAuthSettingsPayload,
  type UpdateOAuthSettingsPayload,
} from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GoogleIcon, TelegramIcon, YandexIcon } from "@shared/ui/BrandIcons";
import { Button } from "@shared/ui/Button";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { PillTabs } from "@shared/ui/PillTabs";
import { Spinner } from "@shared/ui/Spinner";
import { ProviderRow } from "@features/oauth-settings/OAuthSettingsForm";

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
  { key: "google_enabled", label: "google", icon: GoogleIcon, oauth: "google" },
  { key: "yandex_enabled", label: "yandex", icon: YandexIcon, oauth: "yandex" },
  { key: "telegram_oauth_enabled", label: "telegramOAuth", icon: TelegramIcon, oauth: "telegram" },
  { key: "telegram_enabled", label: "telegramMiniApp", icon: Smartphone },
  { key: "telegram_deeplink_enabled", label: "telegramDeeplink", icon: Bot },
  { key: "email_enabled", label: "email", icon: Mail },
];

// what the card's Save writes to cabinet settings: every switch and the captcha choice
type Draft = Pick<CabinetAuthSettings, MethodKey | "restrict_email_domains" | "captcha_enabled" | "captcha_provider">;
const DRAFT_KEYS: (keyof Draft)[] = [
  ...METHODS.map((method) => method.key),
  "restrict_email_domains",
  "captcha_enabled",
  "captcha_provider",
];

function draftOf(settings: CabinetAuthSettings): Draft {
  return Object.fromEntries(DRAFT_KEYS.map((key) => [key, settings[key]])) as Draft;
}

type Credentials = Record<OAuthMethod, { id: string; secret: string }>;
const NO_CREDENTIALS: Credentials = {
  telegram: { id: "", secret: "" },
  google: { id: "", secret: "" },
  yandex: { id: "", secret: "" },
};

const CAPTCHA_PROVIDERS: { key: CaptchaProvider; label: string }[] = [
  { key: "TURNSTILE", label: "Cloudflare Turnstile" },
  { key: "HCAPTCHA", label: "hCaptcha" },
];

/** Cabinet sign-in: the methods, email-domain limit and captcha, all saved by the card's one Save.
 *  OAuth credentials live in OAuth settings under their own permission: Save sends them second. */
export function CabinetAuthSettingsForm({ emailVersion }: { emailVersion: number }) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("CABINET_AUTH_SETTINGS_MANAGE");
  const canManageOAuth = permissions.includes("OAUTH_SETTINGS_MANAGE");
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

  const [draft, setDraft] = useState<Draft | null>(null);
  const [credentials, setCredentials] = useState<Credentials>(NO_CREDENTIALS);
  const [captchaSiteKey, setCaptchaSiteKey] = useState("");
  const [captchaSecretKey, setCaptchaSecretKey] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDomainsOpen, setIsDomainsOpen] = useState(false);
  const [isEmailOpen, setIsEmailOpen] = useState(false);

  // filled once loaded; afterwards only this card's Save resets it, so saving the domains
  // dialog keeps unsaved switches here
  useEffect(() => {
    if (state.kind === "ready") setDraft((prev) => prev ?? draftOf(state.data));
  }, [state]);

  const saved = state.kind === "ready" ? draftOf(state.data) : null;
  const changedFlags: UpdateCabinetAuthSettingsPayload =
    draft && saved ? Object.fromEntries(DRAFT_KEYS.filter((key) => draft[key] !== saved[key]).map((key) => [key, draft[key]])) : {};
  const cabinetPatch: UpdateCabinetAuthSettingsPayload = {
    ...changedFlags,
    ...(captchaSiteKey && { captcha_site_key: captchaSiteKey }),
    ...(captchaSecretKey && { captcha_secret_key: captchaSecretKey }),
  };
  const oauthPatch: UpdateOAuthSettingsPayload = {
    ...(credentials.telegram.id && { telegram_client_id: credentials.telegram.id }),
    ...(credentials.telegram.secret && { telegram_client_secret: credentials.telegram.secret }),
    ...(credentials.google.id && { google_client_id: credentials.google.id }),
    ...(credentials.google.secret && { google_client_secret: credentials.google.secret }),
    ...(credentials.yandex.id && { yandex_client_id: credentials.yandex.id }),
    ...(credentials.yandex.secret && { yandex_client_secret: credentials.yandex.secret }),
  };
  const hasCabinetChanges = Object.keys(cabinetPatch).length > 0;
  const hasOAuthChanges = Object.keys(oauthPatch).length > 0;
  const dirty = hasCabinetChanges || hasOAuthChanges;

  const setFlag = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  const setCredential = (method: OAuthMethod, field: "id" | "secret", value: string) =>
    setCredentials((prev) => ({ ...prev, [method]: { ...prev[method], [field]: value } }));

  const validation = useFieldValidation<"siteKey" | "secretKey">();
  // switched on with no keys stored: both have to come with this save
  const needsCaptchaKeys = draft?.captcha_enabled === true && state.kind === "ready" && !state.data.is_captcha_configured;
  const captchaErrors = {
    siteKey: needsCaptchaKeys && !captchaSiteKey ? t("errors.validation.required") : null,
    secretKey: needsCaptchaKeys && !captchaSecretKey ? t("errors.validation.required") : null,
  };
  const captchaShown = (name: keyof typeof captchaErrors) => validation.visible(name, captchaErrors[name]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!dirty) return;
    validation.submit();
    if (captchaErrors.siteKey !== null || captchaErrors.secretKey !== null) {
      return;
    }
    setIsSubmitting(true);
    try {
      if (hasCabinetChanges) {
        const settings = await updateCabinetAuthSettings(cabinetPatch);
        setData(settings);
        setDraft(draftOf(settings));
        setCaptchaSiteKey("");
        setCaptchaSecretKey("");
      }
      // second: a failure here leaves the switches saved and the credentials in the fields
      if (hasOAuthChanges && canManageOAuth) {
        setOAuthData(await updateOAuthSettings(oauthPatch));
        setCredentials(NO_CREDENTIALS);
      }
      validation.reset();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const renderMethod = ({ key, label, icon: Icon, oauth }: (typeof METHODS)[number], current: Draft) => {
    if (oauth && oauthSettings) {
      return (
        <ProviderRow
          key={key}
          icon={Icon}
          label={t(`settings.cabinetAuth.methods.${label}`)}
          guide={<CabinetMethodGuideDialog method={label} />}
          isConfigured={oauthSettings[`is_${oauth}_configured`]}
          enabled={current[key]}
          onEnabledChange={(next) => setFlag(key, next)}
          canToggle={canManage}
          canEdit={canManageOAuth}
          fields={[
            {
              key: `${oauth}_client_id`,
              label: t("settings.oauth.clientIdLabel"),
              value: credentials[oauth].id,
              onChange: (value) => setCredential(oauth, "id", value),
            },
            {
              key: `${oauth}_client_secret`,
              label: t("settings.oauth.clientSecretLabel"),
              value: credentials[oauth].secret,
              onChange: (value) => setCredential(oauth, "secret", value),
            },
          ]}
        />
      );
    }
    const isConfigured =
      label === "telegramMiniApp" || label === "telegramDeeplink"
        ? isBotConfigured
        : label === "email"
          ? isEmailConfigured
          : undefined;
    const isEmail = label === "email";
    return (
      <Row
        key={key}
        icon={Icon}
        label={t(`settings.cabinetAuth.methods.${label}`)}
        // the email sign-in's domain limit folds out under it
        expanded={isEmail ? isEmailOpen : undefined}
        onClick={isEmail ? () => setIsEmailOpen((open) => !open) : undefined}
        panel={
          isEmail && (
            // 2px past the panel's 14px: the switch under the row's own (16px in)
            <div className="flex items-center gap-3 pr-0.5">
              <span className="min-w-0 flex-1 text-[13px] font-medium text-foreground">
                {t("settings.cabinetAuth.restrictDomains")}
              </span>
              <Button variant="glass" size="sm" onClick={() => setIsDomainsOpen(true)}>
                {t("settings.cabinetAuth.domainsList")}
              </Button>
              <Switch
                checked={current.restrict_email_domains}
                onChange={(value) => setFlag("restrict_email_domains", value)}
                disabled={!canManage}
              />
            </div>
          )
        }
        description={
          isConfigured !== undefined ? (
            <span className={`flex items-center gap-1.5 ${isConfigured ? "text-success" : "text-warning"}`}>
              <span className="size-1.5 rounded-full bg-current" />
              {t(isConfigured ? "settings.oauth.configured" : "settings.oauth.notConfigured")}
            </span>
          ) : oauth ? (
            t("settings.oauth.redirectHint", { path: `/login/callback/${oauth}` })
          ) : label === "telegramMiniApp" ? (
            t("settings.cabinetAuth.telegramMiniAppHint")
          ) : label === "telegramDeeplink" ? (
            t("settings.cabinetAuth.telegramDeeplinkHint")
          ) : (
            t("settings.cabinetAuth.emailHint")
          )
        }
      >
        <CabinetMethodGuideDialog method={label} />
        <Switch
          checked={current[key]}
          onChange={(value) => setFlag(key, value)}
          // switching off stays possible after the bot token or SMTP is removed
          disabled={!canManage || (isConfigured === false && !current[key])}
        />
      </Row>
    );
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={DoorOpen}
        title={t("settings.cabinetAuth.title")}
        description={t("settings.cabinetAuth.description")}
        footer={
          state.kind === "ready" &&
          (canManage || canManageOAuth) && <SaveFooter dirty={dirty} saving={isSubmitting} />
        }
      >
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && draft && (
          <>
            <SectionRows>
              {METHODS.filter((method) => method.label !== "email").map((method) => renderMethod(method, draft))}
            </SectionRows>

            {/* the email sign-in and what guards it: one group */}
            <SectionRows divided>
              {METHODS.filter((method) => method.label === "email").map((method) => renderMethod(method, draft))}
              <ProviderRow
                icon={ShieldCheck}
                label={t("settings.cabinetAuth.captcha.title")}
                guide={<CabinetMethodGuideDialog method="captcha" />}
                isConfigured={state.data.is_captcha_configured}
                enabled={draft.captcha_enabled}
                onEnabledChange={(next) => setFlag("captcha_enabled", next)}
                canToggle={canManage}
                canEdit={canManage}
                extra={
                  <Field label={t("settings.cabinetAuth.captcha.provider")}>
                    <PillTabs
                      items={CAPTCHA_PROVIDERS}
                      activeKey={draft.captcha_provider}
                      onSelect={(value) => setFlag("captcha_provider", value)}
                      disabled={!canManage}
                    />
                  </Field>
                }
                fields={[
                  {
                    key: "captcha_site_key",
                    label: t("settings.cabinetAuth.captcha.siteKey"),
                    value: captchaSiteKey,
                    onChange: setCaptchaSiteKey,
                    error: captchaShown("siteKey"),
                    onBlur: validation.touch("siteKey"),
                  },
                  {
                    key: "captcha_secret_key",
                    label: t("settings.cabinetAuth.captcha.secretKey"),
                    value: captchaSecretKey,
                    onChange: setCaptchaSecretKey,
                    secret: true,
                    error: captchaShown("secretKey"),
                    onBlur: validation.touch("secretKey"),
                  },
                ]}
              />
            </SectionRows>

            {isDomainsOpen && (
              <AllowedDomainsDialog
                domains={state.data.allowed_email_domains}
                canManage={canManage}
                onSaved={setData}
                onClose={() => setIsDomainsOpen(false)}
              />
            )}
          </>
        )}
      </Section>
    </form>
  );
}
