import { ChevronDown, FingerprintPattern, Globe, KeyRound, KeySquare, RectangleEllipsis } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ComponentType, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  getOAuthSettings,
  updateOAuthSettings,
  type OAuthSettings,
  type UpdateOAuthSettingsPayload,
} from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { PasswordInput } from "@shared/ui/PasswordInput";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { CardHeader } from "@shared/ui/CardHeader";

import { GithubOAuthGuideDialog } from "./GithubOAuthGuideDialog";
import { OidcOAuthGuideDialog } from "./OidcOAuthGuideDialog";
import { PasskeyGuideDialog } from "./PasskeyGuideDialog";
import { PasswordLoginGuideDialog } from "./PasswordLoginGuideDialog";
import { TelegramOAuthGuideDialog } from "./TelegramOAuthGuideDialog";


type Provider = "github" | "telegram" | "oidc";

export function OAuthSettingsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("OAUTH_SETTINGS_MANAGE");
  const [state, , setData] = useAsyncResource(getOAuthSettings);
  const [githubClientId, setGithubClientId] = useState("");
  const [githubClientSecret, setGithubClientSecret] = useState("");
  const [telegramClientId, setTelegramClientId] = useState("");
  const [telegramClientSecret, setTelegramClientSecret] = useState("");
  const [googleClientId, setGoogleClientId] = useState("");
  const [googleClientSecret, setGoogleClientSecret] = useState("");
  const [yandexClientId, setYandexClientId] = useState("");
  const [yandexClientSecret, setYandexClientSecret] = useState("");
  const [oidcDisplayName, setOidcDisplayName] = useState("");
  const [oidcIssuerUrl, setOidcIssuerUrl] = useState("");
  const [oidcClientId, setOidcClientId] = useState("");
  const [oidcClientSecret, setOidcClientSecret] = useState("");
  const [passkeyRpId, setPasskeyRpId] = useState("");
  const [passkeyOrigin, setPasskeyOrigin] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (
      !githubClientId &&
      !githubClientSecret &&
      !telegramClientId &&
      !telegramClientSecret &&
      !googleClientId &&
      !googleClientSecret &&
      !yandexClientId &&
      !yandexClientSecret &&
      !oidcDisplayName &&
      !oidcIssuerUrl &&
      !oidcClientId &&
      !oidcClientSecret &&
      !passkeyRpId &&
      !passkeyOrigin
    ) {
      toast.error(t("settings.oauth.errorEmptyFields"));
      return;
    }

    setIsSubmitting(true);
    try {
      const settings = await updateOAuthSettings({
        github_client_id: githubClientId || undefined,
        github_client_secret: githubClientSecret || undefined,
        telegram_client_id: telegramClientId || undefined,
        telegram_client_secret: telegramClientSecret || undefined,
        google_client_id: googleClientId || undefined,
        google_client_secret: googleClientSecret || undefined,
        yandex_client_id: yandexClientId || undefined,
        yandex_client_secret: yandexClientSecret || undefined,
        oidc_display_name: oidcDisplayName || undefined,
        oidc_issuer_url: oidcIssuerUrl || undefined,
        oidc_client_id: oidcClientId || undefined,
        oidc_client_secret: oidcClientSecret || undefined,
        passkey_rp_id: passkeyRpId || undefined,
        passkey_origin: passkeyOrigin || undefined,
      });
      setData(settings);
      setGithubClientId("");
      setGithubClientSecret("");
      setTelegramClientId("");
      setTelegramClientSecret("");
      setGoogleClientId("");
      setGoogleClientSecret("");
      setYandexClientId("");
      setYandexClientSecret("");
      setOidcDisplayName("");
      setOidcIssuerUrl("");
      setOidcClientId("");
      setOidcClientSecret("");
      setPasskeyRpId("");
      setPasskeyOrigin("");
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader
        icon={KeyRound}
        title={t("settings.oauth.title")}
        description={t("settings.oauth.description")}
      />

      {state.kind === "loading" && (
        <Spinner size="card" />
      )}
      {state.kind === "error" && (
        <ErrorState text={t("settings.oauth.loadError")} />
      )}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <div className="flex flex-col [&>:not(:last-child)>:first-child]:border-b [&>:not(:last-child)>:first-child]:border-border/50">
            <ProviderPanel
              provider="github"
              icon={GithubIcon}
              label={t("profile.oauthAccounts.github")}
              isConfigured={state.data.is_github_configured}
              isEnabled={state.data.github_enabled}
              onToggled={setData}
              guide={<GithubOAuthGuideDialog />}
              fields={[
                {
                  key: "github_client_id",
                  label: t("settings.oauth.clientIdLabel"),
                  value: githubClientId,
                  onChange: setGithubClientId,
                },
                {
                  key: "github_client_secret",
                  label: t("settings.oauth.clientSecretLabel"),
                  value: githubClientSecret,
                  onChange: setGithubClientSecret,
                },
              ]}
            />
            <ProviderPanel
              provider="telegram"
              icon={TelegramIcon}
              label={t("profile.oauthAccounts.telegram")}
              isConfigured={state.data.is_telegram_configured}
              isEnabled={state.data.telegram_enabled}
              onToggled={setData}
              guide={<TelegramOAuthGuideDialog />}
              fields={[
                {
                  key: "telegram_client_id",
                  label: t("settings.oauth.clientIdLabel"),
                  value: telegramClientId,
                  onChange: setTelegramClientId,
                },
                {
                  key: "telegram_client_secret",
                  label: t("settings.oauth.clientSecretLabel"),
                  value: telegramClientSecret,
                  onChange: setTelegramClientSecret,
                },
              ]}
            />
            <ProviderPanel
              icon={Globe}
              label={t("profile.oauthAccounts.google")}
              isConfigured={state.data.is_google_configured}
              hint={t("settings.oauth.redirectHint", { path: "/login/callback/google" })}
              fields={[
                {
                  key: "google_client_id",
                  label: t("settings.oauth.clientIdLabel"),
                  value: googleClientId,
                  onChange: setGoogleClientId,
                },
                {
                  key: "google_client_secret",
                  label: t("settings.oauth.clientSecretLabel"),
                  value: googleClientSecret,
                  onChange: setGoogleClientSecret,
                },
              ]}
            />
            <ProviderPanel
              icon={Globe}
              label={t("profile.oauthAccounts.yandex")}
              isConfigured={state.data.is_yandex_configured}
              hint={t("settings.oauth.redirectHint", { path: "/login/callback/yandex" })}
              fields={[
                {
                  key: "yandex_client_id",
                  label: t("settings.oauth.clientIdLabel"),
                  value: yandexClientId,
                  onChange: setYandexClientId,
                },
                {
                  key: "yandex_client_secret",
                  label: t("settings.oauth.clientSecretLabel"),
                  value: yandexClientSecret,
                  onChange: setYandexClientSecret,
                },
              ]}
            />
            <ProviderPanel
              provider="oidc"
              icon={KeySquare}
              label={state.data.oidc_display_name ?? t("profile.oauthAccounts.oidcFallback")}
              isConfigured={state.data.is_oidc_configured}
              isEnabled={state.data.oidc_enabled}
              onToggled={setData}
              guide={<OidcOAuthGuideDialog />}
              fields={[
                {
                  key: "oidc_display_name",
                  label: t("settings.oauth.oidcDisplayNameLabel"),
                  value: oidcDisplayName,
                  onChange: setOidcDisplayName,
                },
                {
                  key: "oidc_issuer_url",
                  label: t("settings.oauth.oidcIssuerUrlLabel"),
                  value: oidcIssuerUrl,
                  onChange: setOidcIssuerUrl,
                },
                {
                  key: "oidc_client_id",
                  label: t("settings.oauth.clientIdLabel"),
                  value: oidcClientId,
                  onChange: setOidcClientId,
                },
                {
                  key: "oidc_client_secret",
                  label: t("settings.oauth.clientSecretLabel"),
                  value: oidcClientSecret,
                  onChange: setOidcClientSecret,
                },
              ]}
            />
            <PasskeyPanel
              isConfigured={state.data.is_passkey_configured}
              isEnabled={state.data.passkey_enabled}
              rpId={passkeyRpId}
              origin={passkeyOrigin}
              onRpIdChange={setPasskeyRpId}
              onOriginChange={setPasskeyOrigin}
              onToggled={setData}
            />
          </div>

          <div className="mt-2 border-t border-white/[0.08] pt-2">
            <PasswordLoginToggle
              isEnabled={state.data.password_login_enabled}
              onToggled={setData}
            />
          </div>

          {canManage && (
            <Button
              variant="accent"
              className="mt-4 w-fit"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? t("common.saving") : t("common.save")}
            </Button>
          )}
        </form>
      )}
    </Card>
  );
}

interface ProviderField {
  key: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
}

interface ProviderPanelProps {
  /** absent for a credentials-only provider: no dashboard sign-in, so no switch */
  provider?: Provider;
  icon: ComponentType<{ className?: string }>;
  label: string;
  isConfigured: boolean;
  isEnabled?: boolean;
  onToggled?: (settings: OAuthSettings) => void;
  hint?: string;
  guide?: ReactNode;
  fields: ProviderField[];
}

function ProviderPanel({
  provider,
  icon: Icon,
  label,
  isConfigured,
  isEnabled,
  onToggled,
  hint,
  guide,
  fields,
}: ProviderPanelProps) {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("OAUTH_SETTINGS_MANAGE");
  const [isOpen, setIsOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);

  const handleToggle = async (next: boolean) => {
    if (!provider || !onToggled) return;
    setIsToggling(true);
    try {
      const payload: UpdateOAuthSettingsPayload =
        provider === "github"
          ? { github_enabled: next }
          : provider === "telegram"
            ? { telegram_enabled: next }
            : { oidc_enabled: next };
      const settings = await updateOAuthSettings(payload);
      onToggled(settings);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div>
      <motion.div
        tabIndex={0}
        onClick={() => setIsOpen((open) => !open)}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          setIsOpen((open) => !open);
        }}
        {...bounceTap(0.03)}
        className="flex cursor-pointer items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
      >
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
          <Icon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-foreground">{label}</p>
          <p className="text-[12px]">
            {isConfigured ? (
              <span className="text-success">{t("settings.oauth.configured")}</span>
            ) : (
              <span className="text-warning">{t("settings.oauth.notConfigured")}</span>
            )}
          </p>
        </div>
        <span className="flex size-6 shrink-0 items-center justify-center">
          <ChevronDown
            className={`size-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`}
          />
        </span>
        {guide}
        {provider && (
          <div className="mr-1 flex" onClick={(event) => event.stopPropagation()}>
            <Switch
              checked={isEnabled ?? false}
              onChange={(value) => void handleToggle(value)}
              disabled={!canManage || isToggling || !isConfigured}
            />
          </div>
        )}
      </motion.div>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-3 px-[12.5px] pb-2 pt-1">
              {hint && <p className="text-[12px] text-muted-foreground">{hint}</p>}
              {fields.map((field) => (
                <Field key={field.key} label={field.label} htmlFor={`oauth-${field.key}`}>
                  {field.key.endsWith("_client_secret") ? (
                    <PasswordInput
                      id={`oauth-${field.key}`}
                      value={field.value}
                      onChange={(event) => field.onChange(event.target.value)}
                      placeholder={t("settings.oauth.placeholder")}
                      disabled={!canManage}
                      // "off" is ignored on password fields: the browser would offer the admin's saved password
                      autoComplete="new-password"
                    />
                  ) : (
                    <TextInput
                      id={`oauth-${field.key}`}
                      type="text"
                      value={field.value}
                      onChange={(event) => field.onChange(event.target.value)}
                      placeholder={t("settings.oauth.placeholder")}
                      disabled={!canManage}
                      autoComplete="off"
                    />
                  )}
                </Field>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface PasskeyPanelProps {
  isConfigured: boolean;
  isEnabled: boolean;
  rpId: string;
  origin: string;
  onRpIdChange: (value: string) => void;
  onOriginChange: (value: string) => void;
  onToggled: (settings: OAuthSettings) => void;
}

function PasskeyPanel({
  isConfigured,
  isEnabled,
  rpId,
  origin,
  onRpIdChange,
  onOriginChange,
  onToggled,
}: PasskeyPanelProps) {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("OAUTH_SETTINGS_MANAGE");
  const [isOpen, setIsOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);

  const handleToggle = async (next: boolean) => {
    setIsToggling(true);
    try {
      const settings = await updateOAuthSettings({ passkey_enabled: next });
      onToggled(settings);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div>
      <motion.div
        tabIndex={0}
        onClick={() => setIsOpen((open) => !open)}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          setIsOpen((open) => !open);
        }}
        {...bounceTap(0.03)}
        className="flex cursor-pointer items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
      >
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
          <FingerprintPattern className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-foreground">
            {t("settings.oauth.passkeyTitle")}
          </p>
          <p className="text-[12px]">
            {isConfigured ? (
              <span className="text-success">{t("settings.oauth.configured")}</span>
            ) : (
              <span className="text-warning">{t("settings.oauth.notConfigured")}</span>
            )}
          </p>
        </div>
        <span className="flex size-6 shrink-0 items-center justify-center">
          <ChevronDown
            className={`size-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`}
          />
        </span>
        <PasskeyGuideDialog />
        <div className="mr-1 flex" onClick={(event) => event.stopPropagation()}>
          <Switch
            checked={isEnabled}
            onChange={(value) => void handleToggle(value)}
            disabled={!canManage || isToggling || !isConfigured}
          />
        </div>
      </motion.div>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="flex flex-col gap-3 px-[12.5px] pb-2 pt-1">
              <Field label={t("settings.oauth.passkeyRpIdLabel")}>
                <TextInput
                  type="text"
                  value={rpId}
                  onChange={(event) => onRpIdChange(event.target.value)}
                  placeholder={t("settings.oauth.placeholder")}
                  disabled={!canManage}
                  autoComplete="off"
                />
              </Field>
              <Field label={t("settings.oauth.passkeyOriginLabel")}>
                <TextInput
                  type="text"
                  value={origin}
                  onChange={(event) => onOriginChange(event.target.value)}
                  placeholder={t("settings.oauth.placeholder")}
                  disabled={!canManage}
                  autoComplete="off"
                />
              </Field>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

interface PasswordLoginToggleProps {
  isEnabled: boolean;
  onToggled: (settings: OAuthSettings) => void;
}

function PasswordLoginToggle({ isEnabled, onToggled }: PasswordLoginToggleProps) {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("OAUTH_SETTINGS_MANAGE");
  const [isToggling, setIsToggling] = useState(false);

  const handleToggle = async (next: boolean) => {
    setIsToggling(true);
    try {
      const settings = await updateOAuthSettings({ password_login_enabled: next });
      onToggled(settings);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
        <RectangleEllipsis className="size-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-foreground">
          {t("settings.oauth.passwordLoginLabel")}
        </p>
        <p className="text-[12px] text-muted-foreground">
          {t("settings.oauth.passwordLoginDescription")}
        </p>
      </div>
      <PasswordLoginGuideDialog />
      <div className="mr-1 flex">
        <Switch
          checked={isEnabled}
          onChange={(value) => void handleToggle(value)}
          disabled={!canManage || isToggling}
        />
      </div>
    </div>
  );
}
