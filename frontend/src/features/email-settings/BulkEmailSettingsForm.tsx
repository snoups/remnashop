import { MailPlus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  getEmailSettings,
  resetBulkEmailSettings,
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
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/EmptyState";
import { Field } from "@shared/ui/Field";
import { PasswordInput } from "@shared/ui/PasswordInput";
import { Spinner } from "@shared/ui/Spinner";
import { TextInput } from "@shared/ui/TextInput";

const MIN_RATE = 1;
const MAX_RATE = 1000;
const SECURITY_OPTIONS: SmtpSecurity[] = ["STARTTLS", "TLS", "NONE"];

export function BulkEmailSettingsForm() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("EMAIL_SETTINGS_MANAGE");
  const canReset = permissions.includes("EMAIL_SETTINGS_BULK_RESET");
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
  const [rate, setRate] = useState("");
  const [isResetOpen, setIsResetOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const rateError = !/^\d+$/.test(rate) || Number(rate) < MIN_RATE || Number(rate) > MAX_RATE;

  useEffect(() => {
    if (state.kind !== "ready") return;
    setHost(state.data.bulk_host ?? "");
    setPort(String(state.data.bulk_port));
    setSecurity(state.data.bulk_security);
    setUsername(state.data.bulk_username ?? "");
    setFromAddress(state.data.bulk_from_address ?? "");
    setFromName(state.data.bulk_from_name ?? "");
    setRate(String(state.data.bulk_rate_per_minute));
  }, [state]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (state.kind !== "ready" || rateError) return;
    const current = state.data;
    const changes: UpdateEmailSettingsPayload = {};
    // the API can't clear these two: empty is ignored, so use Reset
    if (host.trim() && host !== (current.bulk_host ?? "")) changes.bulk_host = host;
    if (port && Number(port) !== current.bulk_port) changes.bulk_port = Number(port);
    if (security !== current.bulk_security) changes.bulk_security = security;
    if (username !== (current.bulk_username ?? "")) changes.bulk_username = username;
    if (Number(rate) !== current.bulk_rate_per_minute) changes.bulk_rate_per_minute = Number(rate);
    if (password) changes.bulk_password = password;
    if (fromAddress.trim() && fromAddress !== (current.bulk_from_address ?? "")) changes.bulk_from_address = fromAddress;
    if (fromName !== (current.bulk_from_name ?? "")) changes.bulk_from_name = fromName;
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

  const handleReset = async () => {
    setIsResetOpen(false);
    setIsResetting(true);
    try {
      setData(await resetBulkEmailSettings());
      setPassword("");
      toast.success(t("settings.emailBulk.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsResetting(false);
    }
  };

  const handleTest = async () => {
    setIsTesting(true);
    try {
      await sendTestEmail(true);
      toast.success(t("settings.emailBulk.testSent"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <Card>
      <CardHeader
        icon={MailPlus}
        title={t("settings.emailBulk.title")}
        description={t("settings.emailBulk.description")}
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("settings.emailBulk.loadError")} />}
      {state.kind === "ready" && (
        <form onSubmit={(event) => void handleSubmit(event)} className="mt-4">
          <fieldset disabled={!canManage} className="contents">
            <div className="flex flex-col gap-3 px-[12.5px]">
              <Field
                label={t("settings.emailBulk.hostLabel")}
                htmlFor="bulk-email-host"
              >
                <TextInput
                  id="bulk-email-host"
                  value={host}
                  onChange={(event) => setHost(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field label={t("settings.emailBulk.portLabel")} htmlFor="bulk-email-port">
                <TextInput
                  id="bulk-email-port"
                  type="number"
                  min={1}
                  max={65535}
                  value={port}
                  onChange={(event) => setPort(event.target.value)}
                />
              </Field>
              <Field label={t("settings.emailBulk.securityLabel")}>
                <div className="flex flex-wrap gap-2">
                  {SECURITY_OPTIONS.map((option) => (
                    <ChoiceChip
                      key={option}
                      active={security === option}
                      onClick={() => setSecurity(option)}
                    >
                      {t(`settings.emailBulk.security.${option}`)}
                    </ChoiceChip>
                  ))}
                </div>
              </Field>
              <Field label={t("settings.emailBulk.usernameLabel")} htmlFor="bulk-email-username">
                <TextInput
                  id="bulk-email-username"
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field label={t("settings.emailBulk.passwordLabel")} htmlFor="bulk-email-password">
                <PasswordInput
                  id="bulk-email-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={
                    state.data.is_bulk_password_set
                      ? t("settings.emailBulk.passwordSet")
                      : t("settings.emailBulk.passwordUnset")
                  }
                  // "off" is ignored on password fields: the browser would offer the admin's saved password
                  autoComplete="new-password"
                />
              </Field>
              <Field
                label={t("settings.emailBulk.fromAddressLabel")}
                htmlFor="bulk-email-from-address"
              >
                <TextInput
                  id="bulk-email-from-address"
                  type="email"
                  value={fromAddress}
                  onChange={(event) => setFromAddress(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field label={t("settings.emailBulk.fromNameLabel")} htmlFor="bulk-email-from-name">
                <TextInput
                  id="bulk-email-from-name"
                  value={fromName}
                  onChange={(event) => setFromName(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field
                label={t("settings.emailBulk.rateLabel")}
                htmlFor="bulk-email-rate"
                hint={t("settings.emailBulk.rateHint")}
                error={rateError ? t("settings.emailBulk.rateInvalid") : undefined}
              >
                <TextInput
                  id="bulk-email-rate"
                  type="number"
                  min={MIN_RATE}
                  step={1}
                  max={MAX_RATE}
                  value={rate}
                  onChange={(event) => setRate(event.target.value)}
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
                disabled={isTesting || !state.data.is_bulk_configured}
              >
                {isTesting ? t("settings.emailBulk.testSending") : t("settings.emailBulk.testButton")}
              </Button>
            )}
            {canReset && (
              <Button
                variant="secondary"
                type="button"
                onClick={() => setIsResetOpen(true)}
                disabled={isResetting || !state.data.is_bulk_configured}
              >
                {t("common.reset")}
              </Button>
            )}
          </div>
        </form>
      )}
      {isResetOpen && (
        <ConfirmDialog
          title={t("settings.emailBulk.resetTitle")}
          message={t("settings.emailBulk.resetMessage")}
          confirmLabel={t("common.reset")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleReset()}
          onCancel={() => setIsResetOpen(false)}
        />
      )}
    </Card>
  );
}
