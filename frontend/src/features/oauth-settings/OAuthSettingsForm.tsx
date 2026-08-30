import { ChevronDown, KeyRound, Lock } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ComponentType, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  getOAuthSettings,
  updateOAuthSettings,
  type OAuthSettings,
  type UpdateOAuthSettingsPayload,
} from "@entities/settings/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { Switch } from "@shared/ui/Switch";

import { GithubOAuthGuideDialog } from "./GithubOAuthGuideDialog";
import { OidcOAuthGuideDialog } from "./OidcOAuthGuideDialog";
import { PasswordLoginGuideDialog } from "./PasswordLoginGuideDialog";
import { TelegramOAuthGuideDialog } from "./TelegramOAuthGuideDialog";

type Provider = "github" | "telegram" | "oidc";

export function OAuthSettingsForm() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [state, , setData] = useAsyncResource(getOAuthSettings);
  const [githubClientId, setGithubClientId] = useState("");
  const [githubClientSecret, setGithubClientSecret] = useState("");
  const [telegramClientId, setTelegramClientId] = useState("");
  const [telegramClientSecret, setTelegramClientSecret] = useState("");
  const [oidcDisplayName, setOidcDisplayName] = useState("");
  const [oidcIssuerUrl, setOidcIssuerUrl] = useState("");
  const [oidcClientId, setOidcClientId] = useState("");
  const [oidcClientSecret, setOidcClientSecret] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    if (
      !githubClientId &&
      !githubClientSecret &&
      !telegramClientId &&
      !telegramClientSecret &&
      !oidcDisplayName &&
      !oidcIssuerUrl &&
      !oidcClientId &&
      !oidcClientSecret
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
        oidc_display_name: oidcDisplayName || undefined,
        oidc_issuer_url: oidcIssuerUrl || undefined,
        oidc_client_id: oidcClientId || undefined,
        oidc_client_secret: oidcClientSecret || undefined,
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
      toast.success(t("settings.oauth.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <KeyRound className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("settings.oauth.title")}</h2>
          <p className="text-[12.5px] text-muted-foreground">{t("settings.oauth.description")}</p>
        </div>
      </div>

      {state.kind === "loading" && (
        <p className="mt-4 text-sm text-muted-foreground">{t("settings.oauth.loading")}</p>
      )}
      {state.kind === "error" && (
        <p className="mt-4 text-sm text-error">{t("settings.oauth.loadError")}</p>
      )}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <div className="flex flex-col">
            <ProviderPanel
              provider="github"
              icon={GithubIcon}
              label={t("profile.oauthAccounts.github")}
              isConfigured={state.data.is_github_configured}
              isEnabled={state.data.is_github_enabled}
              onToggled={setData}
              guide={<GithubOAuthGuideDialog />}
              fields={[
                {
                  key: "github_client_id",
                  label: t("settings.oauth.githubClientIdLabel"),
                  value: githubClientId,
                  onChange: setGithubClientId,
                },
                {
                  key: "github_client_secret",
                  label: t("settings.oauth.githubClientSecretLabel"),
                  value: githubClientSecret,
                  onChange: setGithubClientSecret,
                  type: "password",
                },
              ]}
            />
            <ProviderPanel
              provider="telegram"
              icon={TelegramIcon}
              label={t("profile.oauthAccounts.telegram")}
              isConfigured={state.data.is_telegram_configured}
              isEnabled={state.data.is_telegram_enabled}
              onToggled={setData}
              guide={<TelegramOAuthGuideDialog />}
              fields={[
                {
                  key: "telegram_client_id",
                  label: t("settings.oauth.telegramClientIdLabel"),
                  value: telegramClientId,
                  onChange: setTelegramClientId,
                },
                {
                  key: "telegram_client_secret",
                  label: t("settings.oauth.telegramClientSecretLabel"),
                  value: telegramClientSecret,
                  onChange: setTelegramClientSecret,
                  type: "password",
                },
              ]}
            />
            <ProviderPanel
              provider="oidc"
              icon={KeyRound}
              label={state.data.oidc_display_name ?? t("profile.oauthAccounts.oidcFallback")}
              isConfigured={state.data.is_oidc_configured}
              isEnabled={state.data.is_oidc_enabled}
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
                  label: t("settings.oauth.oidcClientIdLabel"),
                  value: oidcClientId,
                  onChange: setOidcClientId,
                },
                {
                  key: "oidc_client_secret",
                  label: t("settings.oauth.oidcClientSecretLabel"),
                  value: oidcClientSecret,
                  onChange: setOidcClientSecret,
                  type: "password",
                },
              ]}
            />
          </div>

          <div className="mt-2 border-t border-white/[0.08] pt-2">
            <PasswordLoginToggle
              isEnabled={state.data.is_password_login_enabled}
              onToggled={setData}
            />
          </div>

          <motion.button
            type="submit"
            disabled={isSubmitting}
            {...bounceTap(bounceStrength)}
            className="mt-4 w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("settings.oauth.saving") : t("settings.oauth.save")}
          </motion.button>
        </form>
      )}
    </div>
  );
}

interface ProviderField {
  key: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "password";
}

interface ProviderPanelProps {
  provider: Provider;
  icon: ComponentType<{ className?: string }>;
  label: string;
  isConfigured: boolean;
  isEnabled: boolean;
  onToggled: (settings: OAuthSettings) => void;
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
  guide,
  fields,
}: ProviderPanelProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [isToggling, setIsToggling] = useState(false);

  const handleToggle = async (next: boolean) => {
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
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => setIsOpen((open) => !open)}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          setIsOpen((open) => !open);
        }}
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
        <div className="flex" onClick={(event) => event.stopPropagation()}>
          <Switch
            checked={isEnabled}
            onChange={(value) => void handleToggle(value)}
            disabled={isToggling || !isConfigured}
            ariaLabel={t("settings.oauth.enableAria", { provider: label })}
          />
        </div>
      </div>

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
              {fields.map((field) => (
                <div key={field.key} className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-foreground/80">{field.label}</label>
                  <input
                    type={field.type ?? "text"}
                    value={field.value}
                    onChange={(event) => field.onChange(event.target.value)}
                    placeholder={t("settings.oauth.placeholder")}
                    autoComplete="off"
                    className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                  />
                </div>
              ))}
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
  const [isToggling, setIsToggling] = useState(false);

  const handleToggle = async (next: boolean) => {
    setIsToggling(true);
    try {
      const settings = await updateOAuthSettings({ password_login_enabled: next });
      onToggled(settings);
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className="flex items-center gap-3 rounded-full px-[12.5px] py-2.5">
      <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.06] text-foreground">
        <Lock className="size-4" />
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
      <Switch
        checked={isEnabled}
        onChange={(value) => void handleToggle(value)}
        disabled={isToggling}
        ariaLabel={t("settings.oauth.passwordLoginLabel")}
      />
    </div>
  );
}
