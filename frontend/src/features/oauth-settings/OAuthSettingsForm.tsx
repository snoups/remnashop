import { ChevronDown, FingerprintPattern, KeyRound, KeySquare, RectangleEllipsis } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type ComponentType, type FormEvent, type ReactNode } from "react";
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
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { PasswordInput } from "@shared/ui/PasswordInput";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { CardHeader } from "@shared/ui/CardHeader";
import { SETTINGS_ROWS_CLASS, SETTINGS_SECTION_CLASS } from "@shared/ui/classes";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { SettingsRow } from "@shared/ui/SettingsRow";

import { GithubOAuthGuideDialog } from "./GithubOAuthGuideDialog";
import { OidcOAuthGuideDialog } from "./OidcOAuthGuideDialog";
import { PasskeyGuideDialog } from "./PasskeyGuideDialog";
import { PasswordLoginGuideDialog } from "./PasswordLoginGuideDialog";
import { TelegramOAuthGuideDialog } from "./TelegramOAuthGuideDialog";
import { Pressable } from "@shared/ui/Pressable";

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
  const setFlag = (key: keyof OAuthFlags) => async (next: boolean) =>
    setFlags((prev) => (prev ? { ...prev, [key]: next } : prev));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!dirty) return;

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
        <ErrorState text={t("common.loadError")} />
      )}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <div className="flex flex-col [&>:not(:last-child)>:first-child]:border-b [&>:not(:last-child)>:first-child]:border-border/50">
            <ProviderPanel
              icon={GithubIcon}
              label={t("profile.oauthAccounts.github")}
              isConfigured={state.data.is_github_configured}
              isEnabled={flags?.github_enabled}
              onToggle={setFlag("github_enabled")}
              canToggle={canManage}
              guide={<GithubOAuthGuideDialog />}
              brightLabels
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
              icon={TelegramIcon}
              label={t("profile.oauthAccounts.telegram")}
              isConfigured={state.data.is_telegram_configured}
              isEnabled={flags?.telegram_enabled}
              onToggle={setFlag("telegram_enabled")}
              canToggle={canManage}
              guide={<TelegramOAuthGuideDialog />}
              brightLabels
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
              icon={KeySquare}
              label={state.data.oidc_display_name ?? t("profile.oauthAccounts.oidcFallback")}
              isConfigured={state.data.is_oidc_configured}
              isEnabled={flags?.oidc_enabled}
              onToggle={setFlag("oidc_enabled")}
              canToggle={canManage}
              guide={<OidcOAuthGuideDialog />}
              brightLabels
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
              isEnabled={flags?.passkey_enabled ?? false}
              onToggle={(next) => void setFlag("passkey_enabled")(next)}
              rpId={passkeyRpId}
              origin={passkeyOrigin}
              onRpIdChange={setPasskeyRpId}
              onOriginChange={setPasskeyOrigin}
            />
          </div>

          <div className={`${SETTINGS_SECTION_CLASS} ${SETTINGS_ROWS_CLASS}`}>
            <SettingsRow
              icon={RectangleEllipsis}
              label={t("settings.oauth.passwordLoginLabel")}
              description={t("settings.oauth.passwordLoginDescription")}
            >
              <PasswordLoginGuideDialog />
              <Switch
                checked={flags?.password_login_enabled ?? false}
                onChange={(value) => void setFlag("password_login_enabled")(value)}
                disabled={!canManage}
              />
            </SettingsRow>
          </div>

          {canManage && <SaveFooter dirty={dirty} saving={isSubmitting} />}
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
  secret?: boolean;
}

interface ProviderPanelProps {
  icon: ComponentType<{ className?: string }>;
  label: string;
  isConfigured: boolean;
  isEnabled?: boolean;
  /** absent: no switch */
  onToggle?: (next: boolean) => Promise<void>;
  canToggle?: boolean;
  guide?: ReactNode;
  fields: ProviderField[];
  footer?: ReactNode;
  /** present: the panel is its own form */
  onSubmit?: (event: FormEvent) => void;
  /** above the fields */
  extra?: ReactNode;
  /** defaults to the OAuth settings permission */
  canEdit?: boolean;
  /** full-white field labels (the General settings page) */
  brightLabels?: boolean;
}

export function ProviderPanel({
  icon: Icon,
  label,
  isConfigured,
  isEnabled,
  onToggle,
  canToggle = false,
  guide,
  fields,
  footer,
  onSubmit,
  extra,
  canEdit,
  brightLabels = false,
}: ProviderPanelProps) {
  const { t } = useTranslation();
  const canManageOAuth = usePermissions().includes("OAUTH_SETTINGS_MANAGE");
  const canManage = canEdit ?? canManageOAuth;
  const [isOpen, setIsOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);

  const handleToggle = async (next: boolean) => {
    if (!onToggle) return;
    setIsToggling(true);
    try {
      await onToggle(next);
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsToggling(false);
    }
  };

  const Wrapper = onSubmit ? "form" : "div";

  return (
    <Wrapper onSubmit={onSubmit}>
      <Pressable
        as="div"
        onClick={() => setIsOpen((open) => !open)}
        className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
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
        {onToggle && (
          <div className="mr-1 flex" onClick={(event) => event.stopPropagation()}>
            <Switch
              checked={isEnabled ?? false}
              onChange={(value) => void handleToggle(value)}
              disabled={!canToggle || isToggling || !isConfigured}
            />
          </div>
        )}
      </Pressable>

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
              {extra}
              {fields.map((field) => (
                <Field key={field.key} label={field.label} htmlFor={`oauth-${field.key}`} bright={brightLabels}>
                  {(field.secret ?? field.key.endsWith("_client_secret")) ? (
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
              {footer}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </Wrapper>
  );
}

interface PasskeyPanelProps {
  isConfigured: boolean;
  isEnabled: boolean;
  onToggle: (next: boolean) => void;
  rpId: string;
  origin: string;
  onRpIdChange: (value: string) => void;
  onOriginChange: (value: string) => void;
}

function PasskeyPanel({
  isConfigured,
  isEnabled,
  onToggle,
  rpId,
  origin,
  onRpIdChange,
  onOriginChange,
}: PasskeyPanelProps) {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("OAUTH_SETTINGS_MANAGE");
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div>
      <Pressable
        as="div"
        onClick={() => setIsOpen((open) => !open)}
        className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5 transition-colors hover:bg-white/[0.04]"
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
            onChange={onToggle}
            disabled={!canManage || !isConfigured}
          />
        </div>
      </Pressable>

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
              <Field bright label={t("settings.oauth.passkeyRpIdLabel")}>
                <TextInput
                  type="text"
                  value={rpId}
                  onChange={(event) => onRpIdChange(event.target.value)}
                  placeholder={t("settings.oauth.placeholder")}
                  disabled={!canManage}
                  autoComplete="off"
                />
              </Field>
              <Field bright label={t("settings.oauth.passkeyOriginLabel")}>
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
