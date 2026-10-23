import { Mail } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getEmailSettings,
  resetBulkEmailSettings,
  sendTestEmail,
  updateEmailSettings,
  type EmailSettings,
  type SmtpSecurity,
  type UpdateEmailSettingsPayload,
} from "@entities/settings/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/EmptyState";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { Field } from "@shared/ui/Field";
import { PasswordInput } from "@shared/ui/PasswordInput";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { TextInput } from "@shared/ui/TextInput";

const MIN_RATE = 1;
const MAX_RATE = 1000;
const SECURITY_OPTIONS: SmtpSecurity[] = ["STARTTLS", "TLS", "NONE"];

type Profile = "main" | "bulk";

interface SmtpProfile {
  host: string | null;
  port: number;
  security: SmtpSecurity;
  username: string | null;
  isPasswordSet: boolean;
  fromAddress: string | null;
  fromName: string | null;
  isConfigured: boolean;
}

function readProfile(settings: EmailSettings, profile: Profile): SmtpProfile {
  return profile === "main"
    ? {
        host: settings.host,
        port: settings.port,
        security: settings.security,
        username: settings.username,
        isPasswordSet: settings.is_password_set,
        fromAddress: settings.from_address,
        fromName: settings.from_name,
        isConfigured: settings.is_configured,
      }
    : {
        host: settings.bulk_host,
        port: settings.bulk_port,
        security: settings.bulk_security,
        username: settings.bulk_username,
        isPasswordSet: settings.is_bulk_password_set,
        fromAddress: settings.bulk_from_address,
        fromName: settings.bulk_from_name,
        isConfigured: settings.is_bulk_configured,
      };
}

type ProfileChanges = Partial<{
  host: string;
  port: number;
  security: SmtpSecurity;
  username: string;
  password: string;
  fromAddress: string;
  fromName: string;
}>;

function toPayload(profile: Profile, changes: ProfileChanges): UpdateEmailSettingsPayload {
  return profile === "main"
    ? {
        host: changes.host,
        port: changes.port,
        security: changes.security,
        username: changes.username,
        password: changes.password,
        from_address: changes.fromAddress,
        from_name: changes.fromName,
      }
    : {
        bulk_host: changes.host,
        bulk_port: changes.port,
        bulk_security: changes.security,
        bulk_username: changes.username,
        bulk_password: changes.password,
        bulk_from_address: changes.fromAddress,
        bulk_from_name: changes.fromName,
      };
}

export function EmailSettingsForm({ onSaved }: { onSaved?: () => void }) {
  const { t } = useTranslation();
  const [state, , setData] = useAsyncResource(getEmailSettings);

  const handleSaved = (settings: EmailSettings) => {
    setData(settings);
    onSaved?.();
  };

  return (
    <Card>
      <CardHeader icon={Mail} title={t("settings.email.title")} description={t("settings.email.description")} />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <div className="mt-4 flex flex-col gap-4">
          <SmtpProfileForm profile="main" settings={state.data} onSaved={handleSaved} />
          <BroadcastsSection settings={state.data} onSaved={handleSaved} />
        </div>
      )}
    </Card>
  );
}

interface SectionProps {
  settings: EmailSettings;
  onSaved: (settings: EmailSettings) => void;
}

function SmtpProfileForm({ profile, settings, onSaved }: SectionProps & { profile: Profile }) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("EMAIL_SETTINGS_MANAGE");
  const canTest = permissions.includes("EMAIL_SETTINGS_TEST");
  const current = readProfile(settings, profile);
  const [host, setHost] = useState("");
  const [port, setPort] = useState("");
  const [security, setSecurity] = useState<SmtpSecurity>("STARTTLS");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [fromAddress, setFromAddress] = useState("");
  const [fromName, setFromName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [showRequired, setShowRequired] = useState(false);

  // only this profile's own values: saving the other profile or the rate keeps unsaved edits here
  useEffect(() => {
    setHost(current.host ?? "");
    setPort(String(current.port));
    setSecurity(current.security);
    setUsername(current.username ?? "");
    setFromAddress(current.fromAddress ?? "");
    setFromName(current.fromName ?? "");
  }, [current.host, current.port, current.security, current.username, current.fromAddress, current.fromName]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    // the API can't clear these two: empty would be silently ignored
    if (!host.trim() || !fromAddress.trim()) {
      setShowRequired(true);
      return;
    }
    setShowRequired(false);
    const changes: ProfileChanges = {};
    if (host !== (current.host ?? "")) changes.host = host;
    if (port && Number(port) !== current.port) changes.port = Number(port);
    if (security !== current.security) changes.security = security;
    if (username !== (current.username ?? "")) changes.username = username;
    if (password) changes.password = password;
    if (fromAddress !== (current.fromAddress ?? "")) changes.fromAddress = fromAddress;
    if (fromName !== (current.fromName ?? "")) changes.fromName = fromName;
    if (Object.keys(changes).length === 0) return;
    setIsSubmitting(true);
    try {
      onSaved(await updateEmailSettings(toPayload(profile, changes)));
      setPassword("");
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    try {
      await sendTestEmail(profile === "bulk");
      toast.success(t(profile === "bulk" ? "settings.emailBulk.testSent" : "settings.email.testSent"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsTesting(false);
    }
  };

  const id = (name: string) => `${profile}-email-${name}`;

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <fieldset disabled={!canManage} className="contents">
        <div className="flex flex-col gap-3 px-[12.5px]">
          <Field
            label={t("settings.email.hostLabel")}
            htmlFor={id("host")}
            error={showRequired && !host.trim() ? t("errors.validation.required") : undefined}
          >
            <TextInput
              id={id("host")}
              aria-invalid={showRequired && !host.trim()}
              value={host}
              onChange={(event) => setHost(event.target.value)}
              autoComplete="off"
            />
          </Field>
          <Field label={t("settings.email.portLabel")} htmlFor={id("port")}>
            <TextInput
              id={id("port")}
              type="number"
              min={1}
              max={65535}
              value={port}
              onChange={(event) => setPort(event.target.value)}
            />
          </Field>
          <Field label={t("settings.email.securityLabel")}>
            <div className="flex flex-wrap gap-2">
              {SECURITY_OPTIONS.map((option) => (
                <ChoiceChip key={option} active={security === option} onClick={() => setSecurity(option)}>
                  {t(`settings.email.security.${option}`)}
                </ChoiceChip>
              ))}
            </div>
          </Field>
          <Field label={t("settings.email.usernameLabel")} htmlFor={id("username")}>
            <TextInput
              id={id("username")}
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="off"
            />
          </Field>
          <Field label={t("settings.email.passwordLabel")} htmlFor={id("password")}>
            <PasswordInput
              id={id("password")}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder={current.isPasswordSet ? t("settings.email.passwordSet") : t("settings.email.passwordUnset")}
              // "off" is ignored on password fields: the browser would offer the admin's saved password
              autoComplete="new-password"
            />
          </Field>
          <Field
            label={t("settings.email.fromAddressLabel")}
            htmlFor={id("from-address")}
            error={showRequired && !fromAddress.trim() ? t("errors.validation.required") : undefined}
          >
            <TextInput
              id={id("from-address")}
              aria-invalid={showRequired && !fromAddress.trim()}
              type="email"
              value={fromAddress}
              onChange={(event) => setFromAddress(event.target.value)}
              autoComplete="off"
            />
          </Field>
          <Field label={t("settings.email.fromNameLabel")} htmlFor={id("from-name")}>
            <TextInput
              id={id("from-name")}
              value={fromName}
              onChange={(event) => setFromName(event.target.value)}
              autoComplete="off"
            />
          </Field>
        </div>
      </fieldset>

      <div className="mt-4 flex flex-wrap gap-2 px-[12.5px]">
        {canManage && (
          <Button variant="accent" type="submit" disabled={isSubmitting}>
            {isSubmitting ? t("common.saving") : t("common.save")}
          </Button>
        )}
        {canTest && (
          <Button
            variant="secondary"
            type="button"
            onClick={() => void handleTest()}
            disabled={isTesting || !current.isConfigured}
          >
            {isTesting ? t("settings.email.testSending") : t("settings.email.testButton")}
          </Button>
        )}
      </div>
    </form>
  );
}

function BroadcastsSection({ settings, onSaved }: SectionProps) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("EMAIL_SETTINGS_MANAGE");
  const canReset = permissions.includes("EMAIL_SETTINGS_BULK_RESET");
  const [rate, setRate] = useState(String(settings.bulk_rate_per_minute));
  // on without a saved server: the fields are open, nothing is stored until Save
  const [isDraftOpen, setIsDraftOpen] = useState(false);
  const [isResetOpen, setIsResetOpen] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const isBulkOn = settings.is_bulk_configured || isDraftOpen;

  useEffect(() => {
    setRate(String(settings.bulk_rate_per_minute));
  }, [settings.bulk_rate_per_minute]);

  const rateError = !/^\d+$/.test(rate) || Number(rate) < MIN_RATE || Number(rate) > MAX_RATE;

  const saveRate = async () => {
    if (rateError || Number(rate) === settings.bulk_rate_per_minute) return;
    setIsPending(true);
    try {
      onSaved(await updateEmailSettings({ bulk_rate_per_minute: Number(rate) }));
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsPending(false);
    }
  };

  const handleToggle = (next: boolean) => {
    if (next) setIsDraftOpen(true);
    else if (settings.is_bulk_configured) setIsResetOpen(true);
    else setIsDraftOpen(false);
  };

  const handleReset = async () => {
    setIsResetOpen(false);
    setIsPending(true);
    try {
      onSaved(await resetBulkEmailSettings());
      setIsDraftOpen(false);
      toast.success(t("settings.emailBulk.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsPending(false);
    }
  };

  return (
    <div className="flex flex-col gap-1 border-t border-white/[0.08] pt-4">
      <span className={`px-[12.5px] ${EYEBROW_CLASS}`}>{t("settings.emailBulk.sectionTitle")}</span>

      <div className="flex items-center gap-3 px-[12.5px] py-2.5">
        <label htmlFor="bulk-email-rate" className="min-w-0 flex-1">
          <span className="block text-[13px] font-medium text-foreground">{t("settings.emailBulk.rateLabel")}</span>
          <span className="block text-[12px] text-muted-foreground">
            {rateError ? t("settings.emailBulk.rateInvalid") : t("settings.emailBulk.rateHint")}
          </span>
        </label>
        <TextInput
          id="bulk-email-rate"
          type="number"
          min={MIN_RATE}
          step={1}
          max={MAX_RATE}
          value={rate}
          onChange={(event) => setRate(event.target.value)}
          onBlur={() => void saveRate()}
          aria-invalid={rateError}
          disabled={!canManage || isPending}
          className="w-24"
        />
      </div>

      <div className="flex items-center gap-3 px-[12.5px] py-2.5">
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-medium text-foreground">{t("settings.emailBulk.toggleLabel")}</p>
          <p className="text-[12px]">
            {settings.is_bulk_configured ? (
              <span className="text-success">{t("settings.oauth.configured")}</span>
            ) : isDraftOpen ? (
              <span className="text-warning">{t("settings.oauth.notConfigured")}</span>
            ) : (
              <span className="text-muted-foreground">{t("settings.emailBulk.viaMain")}</span>
            )}
          </p>
        </div>
        <div className="mr-1 flex">
          <Switch
            checked={isBulkOn}
            onChange={handleToggle}
            disabled={isPending || (isBulkOn && settings.is_bulk_configured ? !canReset : !canManage)}
          />
        </div>
      </div>

      {isBulkOn && (
        <Card variant="bare" className="mx-[12.5px] mt-1 py-3.5">
          <SmtpProfileForm profile="bulk" settings={settings} onSaved={onSaved} />
        </Card>
      )}

      {isResetOpen && (
        <ConfirmDialog
          title={t("settings.emailBulk.resetTitle")}
          message={t("settings.emailBulk.resetMessage")}
          confirmLabel={t("settings.emailBulk.resetConfirm")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleReset()}
          onCancel={() => setIsResetOpen(false)}
        />
      )}
    </div>
  );
}
