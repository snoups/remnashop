import { FingerprintPattern, KeyRound, KeySquare, RectangleEllipsis } from "lucide-react";
import {
  useEffect,
  useId,
  useState,
  type ChangeEvent,
  type ComponentType,
  type FormEvent,
  type ReactNode,
} from "react";
import { useTranslation } from "react-i18next";

import {
  getOAuthSettings,
  updateOAuthSettings,
  type OAuthSettings,
  type UpdateOAuthSettingsPayload,
} from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field as GlassField } from "@shared/ui/glass/Field";
import { Input, PasswordInput as GlassPasswordInput } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { Switch as GlassSwitch } from "@shared/ui/glass/Switch";
import { Spinner } from "@shared/ui/Spinner";
import { SaveFooter } from "@shared/ui/SaveFooter";

import { GithubOAuthGuideDialog } from "./GithubOAuthGuideDialog";
import { OidcOAuthGuideDialog } from "./OidcOAuthGuideDialog";
import { PasskeyGuideDialog } from "./PasskeyGuideDialog";
import { PasswordLoginGuideDialog } from "./PasswordLoginGuideDialog";
import { TelegramOAuthGuideDialog } from "./TelegramOAuthGuideDialog";

export function OAuthSettingsForm() {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("OAUTH_SETTINGS_MANAGE");
  const [state, , setData] = useAsyncResource(getOAuthSettings);
  const [githubClientId, setGithubClientId] = useState("");
  const [githubClientSecret, setGithubClientSecret] = useState("");
  const [telegramClientId, setTelegramClientId] = useState("");
  const [telegramClientSecret, setTelegramClientSecret] = useState("");
  const [oidcDisplayName, setOidcDisplayName] = useState("");
  const [oidcIssuerUrl, setOidcIssuerUrl] = useState("");
  const [oidcClientId, setOidcClientId] = useState("");
  const [oidcClientSecret, setOidcClientSecret] = useState("");
  const [passkeyRpId, setPasskeyRpId] = useState("");
  const [passkeyOrigin, setPasskeyOrigin] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [flags, setFlags] = useState<OAuthFlags | null>(null);

  useEffect(() => {
    if (state.kind === "ready") setFlags(pickFlags(state.data));
  }, [state]);

  const saved = state.kind === "ready" ? pickFlags(state.data) : null;
  const changedFlags: UpdateOAuthSettingsPayload =
    flags && saved
      ? Object.fromEntries(FLAG_KEYS.filter((key) => flags[key] !== saved[key]).map((key) => [key, flags[key]]))
      : {};
  const hasCredentials = [
    githubClientId,
    githubClientSecret,
    telegramClientId,
    telegramClientSecret,
    oidcDisplayName,
    oidcIssuerUrl,
    oidcClientId,
    oidcClientSecret,
    passkeyRpId,
    passkeyOrigin,
  ].some(Boolean);
  const dirty = hasCredentials || Object.keys(changedFlags).length > 0;
  const setFlag = (key: keyof OAuthFlags) => (next: boolean) =>
    setFlags((prev) => (prev ? { ...prev, [key]: next } : prev));

  const validation = useFieldValidation<"oidcIssuerUrl">();
  // the backend takes only an https issuer
  const issuerError =
    oidcIssuerUrl.trim() !== "" && !oidcIssuerUrl.trim().startsWith("https://")
      ? t("settings.oauth.issuerUrlInvalid")
      : null;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!dirty) return;
    validation.submit();
    if (issuerError !== null) return;

    setIsSubmitting(true);
    try {
      const settings = await updateOAuthSettings({
        ...changedFlags,
        github_client_id: githubClientId || undefined,
        github_client_secret: githubClientSecret || undefined,
        telegram_client_id: telegramClientId || undefined,
        telegram_client_secret: telegramClientSecret || undefined,
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
      setOidcDisplayName("");
      setOidcIssuerUrl("");
      setOidcClientId("");
      setOidcClientSecret("");
      setPasskeyRpId("");
      setPasskeyOrigin("");
      validation.reset();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={KeyRound}
        title={t("settings.oauth.title")}
        description={t("settings.oauth.description")}
        footer={state.kind === "ready" && canManage && <SaveFooter variant="glassAccent" dirty={dirty} saving={isSubmitting} />}
      >
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <SectionRows>
            <ProviderRow
              icon={GithubIcon}
              label={t("profile.oauthAccounts.github")}
              isConfigured={state.data.is_github_configured}
              guide={<GithubOAuthGuideDialog />}
              enabled={flags?.github_enabled ?? false}
              onEnabledChange={setFlag("github_enabled")}
              canToggle={canManage}
              canEdit={canManage}
              fields={[
                { key: "github_client_id", label: t("settings.oauth.clientIdLabel"), value: githubClientId, onChange: setGithubClientId },
                { key: "github_client_secret", label: t("settings.oauth.clientSecretLabel"), value: githubClientSecret, onChange: setGithubClientSecret, secret: true },
              ]}
            />
            <ProviderRow
              icon={TelegramIcon}
              label={t("profile.oauthAccounts.telegram")}
              isConfigured={state.data.is_telegram_configured}
              guide={<TelegramOAuthGuideDialog />}
              enabled={flags?.telegram_enabled ?? false}
              onEnabledChange={setFlag("telegram_enabled")}
              canToggle={canManage}
              canEdit={canManage}
              fields={[
                { key: "telegram_client_id", label: t("settings.oauth.clientIdLabel"), value: telegramClientId, onChange: setTelegramClientId },
                { key: "telegram_client_secret", label: t("settings.oauth.clientSecretLabel"), value: telegramClientSecret, onChange: setTelegramClientSecret, secret: true },
              ]}
            />
            <ProviderRow
              icon={KeySquare}
              label={state.data.oidc_display_name ?? t("profile.oauthAccounts.oidcFallback")}
              isConfigured={state.data.is_oidc_configured}
              guide={<OidcOAuthGuideDialog />}
              enabled={flags?.oidc_enabled ?? false}
              onEnabledChange={setFlag("oidc_enabled")}
              canToggle={canManage}
              canEdit={canManage}
              fields={[
                { key: "oidc_display_name", label: t("settings.oauth.oidcDisplayNameLabel"), value: oidcDisplayName, onChange: setOidcDisplayName },
                {
                  key: "oidc_issuer_url",
                  label: t("settings.oauth.oidcIssuerUrlLabel"),
                  value: oidcIssuerUrl,
                  onChange: setOidcIssuerUrl,
                  error: validation.visible("oidcIssuerUrl", issuerError),
                  onBlur: validation.touch("oidcIssuerUrl"),
                },
                { key: "oidc_client_id", label: t("settings.oauth.clientIdLabel"), value: oidcClientId, onChange: setOidcClientId },
                { key: "oidc_client_secret", label: t("settings.oauth.clientSecretLabel"), value: oidcClientSecret, onChange: setOidcClientSecret, secret: true },
              ]}
            />
            <ProviderRow
              icon={FingerprintPattern}
              label={t("settings.oauth.passkeyTitle")}
              isConfigured={state.data.is_passkey_configured}
              guide={<PasskeyGuideDialog />}
              enabled={flags?.passkey_enabled ?? false}
              onEnabledChange={setFlag("passkey_enabled")}
              canToggle={canManage}
              canEdit={canManage}
              fields={[
                { key: "passkey_rp_id", label: t("settings.oauth.passkeyRpIdLabel"), value: passkeyRpId, onChange: setPasskeyRpId },
                { key: "passkey_origin", label: t("settings.oauth.passkeyOriginLabel"), value: passkeyOrigin, onChange: setPasskeyOrigin },
              ]}
            />
            <Row
              icon={RectangleEllipsis}
              label={t("settings.oauth.passwordLoginLabel")}
              description={t("settings.oauth.passwordLoginDescription")}
            >
              <PasswordLoginGuideDialog />
              <GlassSwitch
                checked={flags?.password_login_enabled ?? false}
                onChange={setFlag("password_login_enabled")}
                disabled={!canManage}
              />
            </Row>
          </SectionRows>
        )}
      </Section>
    </form>
  );
}

interface ProviderRowProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  isConfigured: boolean;
  guide: ReactNode;
  enabled: boolean;
  /** a promise shows the switch busy and a failure as a toast */
  onEnabledChange: (next: boolean) => void | Promise<void>;
  canToggle: boolean;
  /** the credential fields (OAuth settings' own permission) */
  canEdit: boolean;
  fields: ProviderField[];
  /** above the fields: a provider choice */
  extra?: ReactNode;
  /** under the fields: the row's own Save, when it is its own form */
  footer?: ReactNode;
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
}

/** A sign-in provider in a glass card: status under the name, credentials folding out. The switch
 *  waits for credentials, but one already on can always be switched off. */
export function ProviderRow({
  icon,
  label,
  isConfigured,
  guide,
  enabled,
  onEnabledChange,
  canToggle,
  canEdit,
  fields,
  extra,
  footer,
  onSubmit,
}: ProviderRowProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const id = useId();

  const toggle = async (next: boolean) => {
    setIsToggling(true);
    try {
      await onEnabledChange(next);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <Row
      icon={icon}
      label={label}
      description={
        <span className={`flex items-center gap-1.5 ${isConfigured ? "text-success" : "text-warning"}`}>
          <span className="size-1.5 rounded-full bg-current" />
          {t(isConfigured ? "settings.oauth.configured" : "settings.oauth.notConfigured")}
        </span>
      }
      // a field error opens the row: a failed save must not hide what's wrong
      expanded={isOpen || fields.some((field) => field.error !== undefined)}
      onClick={() => setIsOpen((open) => !open)}
      onSubmit={onSubmit}
      panel={
        <>
          {extra}
          {fields.map((field) => {
            const inputId = `${id}-${field.key}`;
            const common = {
              id: inputId,
              value: field.value,
              onChange: (event: ChangeEvent<HTMLInputElement>) => field.onChange(event.target.value),
              onBlur: field.onBlur,
              "aria-invalid": field.error !== undefined,
              placeholder: t("settings.oauth.placeholder"),
              disabled: !canEdit,
            };
            return (
              <GlassField key={field.key} label={field.label} htmlFor={inputId} error={field.error}>
                {(field.secret ?? field.key.endsWith("_client_secret")) ? (
                  // "off" is ignored on password fields: the browser would offer the admin's saved password
                  <GlassPasswordInput {...common} autoComplete="new-password" />
                ) : (
                  <Input {...common} autoComplete="off" />
                )}
              </GlassField>
            );
          })}
          {footer}
        </>
      }
    >
      {guide}
      <GlassSwitch
        checked={enabled}
        onChange={(next) => void toggle(next)}
        disabled={!canToggle || isToggling || (!isConfigured && !enabled)}
      />
    </Row>
  );
}

interface ProviderField {
  key: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  secret?: boolean;
  /** shown under the field */
  error?: string;
  onBlur?: () => void;
}

const FLAG_KEYS = [
  "github_enabled",
  "telegram_enabled",
  "oidc_enabled",
  "passkey_enabled",
  "password_login_enabled",
] as const;

type OAuthFlags = Pick<OAuthSettings, (typeof FLAG_KEYS)[number]>;

function pickFlags(settings: OAuthSettings): OAuthFlags {
  return Object.fromEntries(FLAG_KEYS.map((key) => [key, settings[key]])) as OAuthFlags;
}
