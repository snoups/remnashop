import { Mail } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getEmailSettings,
  sendTestEmail,
  updateEmailSettings,
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
import { ErrorState } from "@shared/ui/EmptyState";
import { Field } from "@shared/ui/Field";
import { PasswordInput } from "@shared/ui/PasswordInput";
import { Spinner } from "@shared/ui/Spinner";
import { TextInput } from "@shared/ui/TextInput";

const SECURITY_OPTIONS: SmtpSecurity[] = ["STARTTLS", "TLS", "NONE"];

export function EmailSettingsForm() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("EMAIL_SETTINGS_MANAGE");
  const canTest = permissions.includes("EMAIL_SETTINGS_TEST");
  const [state, , setData] = useAsyncResource(getEmailSettings);
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

  useEffect(() => {
    if (state.kind !== "ready") return;
    setHost(state.data.host ?? "");
    setPort(String(state.data.port));
    setSecurity(state.data.security);
    setUsername(state.data.username ?? "");
    setFromAddress(state.data.from_address ?? "");
    setFromName(state.data.from_name ?? "");
  }, [state]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (state.kind !== "ready") return;
    // the API can't clear these two: empty would be silently ignored
    if (!host.trim() || !fromAddress.trim()) {
      setShowRequired(true);
      return;
    }
    setShowRequired(false);
    const current = state.data;
    const changes: UpdateEmailSettingsPayload = {};
    if (host !== (current.host ?? "")) changes.host = host;
    if (port && Number(port) !== current.port) changes.port = Number(port);
    if (security !== current.security) changes.security = security;
    if (username !== (current.username ?? "")) changes.username = username;
    if (password) changes.password = password;
    if (fromAddress !== (current.from_address ?? "")) changes.from_address = fromAddress;
    if (fromName !== (current.from_name ?? "")) changes.from_name = fromName;
    if (Object.keys(changes).length === 0) return;
    setIsSubmitting(true);
    try {
      setData(await updateEmailSettings(changes));
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
      await sendTestEmail();
      toast.success(t("settings.email.testSent"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <Card>
      <CardHeader
        icon={Mail}
        title={t("settings.email.title")}
        description={t("settings.email.description")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("settings.email.loadError")} />}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <fieldset disabled={!canManage} className="contents">
            <div className="flex flex-col gap-3 px-[12.5px]">
              <Field
                label={t("settings.email.hostLabel")}
                htmlFor="email-host"
                error={showRequired && !host.trim() ? t("errors.validation.required") : undefined}
              >
                <TextInput
                  id="email-host"
                  aria-invalid={showRequired && !host.trim()}
                  value={host}
                  onChange={(event) => setHost(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field label={t("settings.email.portLabel")} htmlFor="email-port">
                <TextInput
                  id="email-port"
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
                    <ChoiceChip
                      key={option}
                      active={security === option}
                      onClick={() => setSecurity(option)}
                    >
                      {t(`settings.email.security.${option}`)}
                    </ChoiceChip>
                  ))}
                </div>
              </Field>
              <Field label={t("settings.email.usernameLabel")} htmlFor="email-username">
                <TextInput
                  id="email-username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field label={t("settings.email.passwordLabel")} htmlFor="email-password">
                <PasswordInput
                  id="email-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={
                    state.data.is_password_set
                      ? t("settings.email.passwordSet")
                      : t("settings.email.passwordUnset")
                  }
                  // "off" is ignored on password fields: the browser would offer the admin's saved password
                  autoComplete="new-password"
                />
              </Field>
              <Field
                label={t("settings.email.fromAddressLabel")}
                htmlFor="email-from-address"
                error={showRequired && !fromAddress.trim() ? t("errors.validation.required") : undefined}
              >
                <TextInput
                  id="email-from-address"
                  aria-invalid={showRequired && !fromAddress.trim()}
                  type="email"
                  value={fromAddress}
                  onChange={(event) => setFromAddress(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field label={t("settings.email.fromNameLabel")} htmlFor="email-from-name">
                <TextInput
                  id="email-from-name"
                  value={fromName}
                  onChange={(event) => setFromName(event.target.value)}
                  autoComplete="off"
                />
              </Field>
            </div>
          </fieldset>

          <div className="mt-4 flex flex-wrap gap-2">
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
                disabled={isTesting || !state.data.is_configured}
              >
                {isTesting ? t("settings.email.testSending") : t("settings.email.testButton")}
              </Button>
            )}
          </div>
        </form>
      )}
    </Card>
  );
}
