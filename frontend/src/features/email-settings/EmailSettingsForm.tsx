import { Gauge, Mail, MailPlus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";

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
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { Input, PasswordInput } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { PillTabs } from "@shared/ui/PillTabs";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Spinner } from "@shared/ui/Spinner";

const MIN_RATE = 1;
const MAX_RATE = 1000;
const SECURITY_OPTIONS: SmtpSecurity[] = ["STARTTLS", "TLS", "NONE"];
const MAX_PORT = 65535;
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const PROFILES = ["main", "bulk"] as const;

type Profile = (typeof PROFILES)[number];

interface SmtpProfile {
  host: string | null;
  port: number;
  security: SmtpSecurity;
  username: string | null;
  isPasswordSet: boolean;
  fromAddress: string | null;
  fromName: string | null;
  rate: number;
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
        rate: settings.rate_per_minute,
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
        rate: settings.bulk_rate_per_minute,
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
  rate: number;
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
        rate_per_minute: changes.rate,
      }
    : {
        bulk_host: changes.host,
        bulk_port: changes.port,
        bulk_security: changes.security,
        bulk_username: changes.username,
        bulk_password: changes.password,
        bulk_from_address: changes.fromAddress,
        bulk_from_name: changes.fromName,
        bulk_rate_per_minute: changes.rate,
      };
}

interface ProfileDraft {
  host: string;
  port: string;
  security: SmtpSecurity;
  username: string;
  password: string;
  fromAddress: string;
  fromName: string;
  rate: string;
}

function toDraft(current: SmtpProfile): ProfileDraft {
  return {
    host: current.host ?? "",
    port: String(current.port),
    security: current.security,
    username: current.username ?? "",
    password: "",
    fromAddress: current.fromAddress ?? "",
    fromName: current.fromName ?? "",
    rate: String(current.rate),
  };
}

function changesOf(draft: ProfileDraft, current: SmtpProfile): ProfileChanges {
  const changes: ProfileChanges = {};
  if (draft.host !== (current.host ?? "")) changes.host = draft.host;
  if (draft.port && Number(draft.port) !== current.port) changes.port = Number(draft.port);
  if (draft.security !== current.security) changes.security = draft.security;
  if (draft.username !== (current.username ?? "")) changes.username = draft.username;
  if (draft.password) changes.password = draft.password;
  if (draft.fromAddress !== (current.fromAddress ?? "")) changes.fromAddress = draft.fromAddress;
  if (draft.fromName !== (current.fromName ?? "")) changes.fromName = draft.fromName;
  if (draft.rate !== String(current.rate)) changes.rate = Number(draft.rate);
  return changes;
}

type ValidatedField = "host" | "port" | "fromAddress" | "rate";
type FieldErrors = Record<ValidatedField, string | null>;

// the API can't clear host and sender: empty would be silently ignored
function errorsOf(draft: ProfileDraft, t: TFunction): FieldErrors {
  return {
    host: draft.host.trim() === "" ? t("errors.validation.required") : null,
    port:
      !/^\d+$/.test(draft.port) || Number(draft.port) < 1 || Number(draft.port) > MAX_PORT
        ? t("settings.email.portInvalid", { max: MAX_PORT })
        : null,
    fromAddress:
      draft.fromAddress.trim() === ""
        ? t("errors.validation.required")
        : !EMAIL.test(draft.fromAddress.trim())
          ? t("errors.validation.email")
          : null,
    rate:
      !/^\d+$/.test(draft.rate) || Number(draft.rate) < MIN_RATE || Number(draft.rate) > MAX_RATE
        ? t("settings.emailBulk.rateInvalid")
        : null,
  };
}

const hasErrors = (errors: FieldErrors) => Object.values(errors).some((error) => error !== null);

export function EmailSettingsForm({ onSaved }: { onSaved?: () => void }) {
  const { t } = useTranslation();
  const [state, , setData] = useAsyncResource(getEmailSettings);

  const handleSaved = (settings: EmailSettings) => {
    setData(settings);
    onSaved?.();
  };

  if (state.kind === "ready") return <EmailSettingsBody settings={state.data} onSaved={handleSaved} />;
  return (
    <Section icon={Mail} title={t("settings.email.title")} description={t("settings.email.description")}>
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
    </Section>
  );
}

/** Both SMTP servers under one Save, a tab each; switching the broadcast server off resets it at once. */
function EmailSettingsBody({ settings, onSaved }: { settings: EmailSettings; onSaved: (settings: EmailSettings) => void }) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("EMAIL_SETTINGS_MANAGE");
  const canReset = permissions.includes("EMAIL_SETTINGS_BULK_RESET");
  const canTest = permissions.includes("EMAIL_SETTINGS_TEST");
  const main = readProfile(settings, "main");
  const bulk = readProfile(settings, "bulk");
  const [tab, setTab] = useState<Profile>("main");
  const [mainDraft, setMainDraft] = useState(() => toDraft(main));
  const [bulkDraft, setBulkDraft] = useState(() => toDraft(bulk));
  // on without a saved server: the fields are open, nothing is stored until Save
  const [isDraftOpen, setIsDraftOpen] = useState(false);
  const [isResetOpen, setIsResetOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const mainValidation = useFieldValidation<ValidatedField>();
  const bulkValidation = useFieldValidation<ValidatedField>();
  const isBulkOn = settings.is_bulk_configured || isDraftOpen;

  const mainChanges = changesOf(mainDraft, main);
  const bulkChanges = isBulkOn ? changesOf(bulkDraft, bulk) : {};
  const hasMainChanges = Object.keys(mainChanges).length > 0;
  const hasBulkChanges = Object.keys(bulkChanges).length > 0;
  const mainErrors = errorsOf(mainDraft, t);
  const bulkErrors = errorsOf(bulkDraft, t);
  // a server left untouched isn't checked
  const mainInvalid = hasMainChanges && hasErrors(mainErrors);
  const bulkInvalid = hasBulkChanges && hasErrors(bulkErrors);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (hasMainChanges) mainValidation.submit();
    if (hasBulkChanges) bulkValidation.submit();
    if (mainInvalid || bulkInvalid) {
      setTab(mainInvalid ? "main" : "bulk");
      return;
    }
    setIsSaving(true);
    try {
      const saved = await updateEmailSettings({ ...toPayload("main", mainChanges), ...toPayload("bulk", bulkChanges) });
      onSaved(saved);
      setMainDraft(toDraft(readProfile(saved, "main")));
      setBulkDraft(toDraft(readProfile(saved, "bulk")));
      mainValidation.reset();
      bulkValidation.reset();
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggle = (next: boolean) => {
    if (next) setIsDraftOpen(true);
    else if (settings.is_bulk_configured) setIsResetOpen(true);
    else {
      setIsDraftOpen(false);
      setBulkDraft(toDraft(bulk));
      bulkValidation.reset();
    }
  };

  const handleReset = async () => {
    setIsResetOpen(false);
    setIsResetting(true);
    try {
      const saved = await resetBulkEmailSettings();
      onSaved(saved);
      setBulkDraft(toDraft(readProfile(saved, "bulk")));
      bulkValidation.reset();
      setIsDraftOpen(false);
      toast.success(t("settings.emailBulk.resetDone"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsResetting(false);
    }
  };

  const showsBulk = tab === "bulk";
  const showsFields = !showsBulk || isBulkOn;

  return (
    <>
      <form onSubmit={(event) => void handleSubmit(event)}>
        <Section
          icon={Mail}
          title={t("settings.email.title")}
          description={t("settings.email.description")}
          aside={
            <PillTabs
              items={PROFILES.map((profile) => ({ key: profile, label: t(`settings.email.tabs.${profile}`) }))}
              activeKey={tab}
              onSelect={setTab}
            />
          }
          footer={
            (canManage || canTest) && (
              <SaveFooter
                variant="glassAccent"
                dirty={canManage && (hasMainChanges || hasBulkChanges)}
                saving={isSaving}
                beside={
                  canTest &&
                  showsFields && <TestButton profile={tab} disabled={!(showsBulk ? bulk : main).isConfigured} />
                }
              />
            )
          }
        >
          <SectionRows>
            {showsBulk && (
              <Row
                icon={MailPlus}
                label={t("settings.emailBulk.toggleLabel")}
                description={
                  settings.is_bulk_configured ? (
                    <span className="flex items-center gap-1.5 text-success">
                      <span className="size-1.5 rounded-full bg-current" />
                      {t("settings.oauth.configured")}
                    </span>
                  ) : isDraftOpen ? (
                    <span className="flex items-center gap-1.5 text-warning">
                      <span className="size-1.5 rounded-full bg-current" />
                      {t("settings.oauth.notConfigured")}
                    </span>
                  ) : (
                    t("settings.emailBulk.viaMain")
                  )
                }
              >
                <Switch
                  checked={isBulkOn}
                  onChange={handleToggle}
                  disabled={isResetting || (isBulkOn && settings.is_bulk_configured ? !canReset : !canManage)}
                />
              </Row>
            )}
            {showsFields && (
              <RateRow
                profile={tab}
                value={(showsBulk ? bulkDraft : mainDraft).rate}
                error={(showsBulk ? bulkErrors : mainErrors).rate}
                onChange={(rate) => (showsBulk ? setBulkDraft : setMainDraft)((draft) => ({ ...draft, rate }))}
              />
            )}
          </SectionRows>
          {showsFields && (
            <SmtpFields
              key={tab}
              profile={tab}
              draft={showsBulk ? bulkDraft : mainDraft}
              current={showsBulk ? bulk : main}
              errors={showsBulk ? bulkErrors : mainErrors}
              validation={showsBulk ? bulkValidation : mainValidation}
              onChange={(patch) => (showsBulk ? setBulkDraft : setMainDraft)((draft) => ({ ...draft, ...patch }))}
            />
          )}
        </Section>
      </form>

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
    </>
  );
}

interface RateRowProps {
  profile: Profile;
  value: string;
  error: string | null;
  onChange: (value: string) => void;
}

function RateRow({ profile, value, error, onChange }: RateRowProps) {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("EMAIL_SETTINGS_MANAGE");
  return (
    <Row
      icon={Gauge}
      label={t("settings.emailBulk.rateLabel")}
      description={error ? <span className="text-error">{error}</span> : t("settings.emailBulk.rateHint")}
    >
      <Input
        id={`${profile}-email-rate`}
        size="sm"
        className="w-24"
        type="number"
        min={MIN_RATE}
        step={1}
        max={MAX_RATE}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error !== null}
        disabled={!canManage}
      />
    </Row>
  );
}

/** Sends with the saved settings, not the draft. */
function TestButton({ profile, disabled }: { profile: Profile; disabled: boolean }) {
  const { t } = useTranslation();
  const [isTesting, setIsTesting] = useState(false);

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

  return (
    <Button variant="glass" onClick={() => void handleTest()} isLoading={isTesting} disabled={disabled}>
      {t("settings.email.testButton")}
    </Button>
  );
}

interface SmtpFieldsProps {
  profile: Profile;
  draft: ProfileDraft;
  current: SmtpProfile;
  errors: FieldErrors;
  validation: ReturnType<typeof useFieldValidation<ValidatedField>>;
  onChange: (patch: Partial<ProfileDraft>) => void;
}

/** One SMTP server's fields. */
function SmtpFields({ profile, draft, current, errors, validation, onChange }: SmtpFieldsProps) {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("EMAIL_SETTINGS_MANAGE");

  const shown = (name: ValidatedField) => validation.visible(name, errors[name]);
  const watch = (name: ValidatedField) => ({
    onBlur: validation.touch(name),
    "aria-invalid": shown(name) !== undefined,
  });
  const id = (name: string) => `${profile}-email-${name}`;

  return (
    <SectionFields divided>
      <fieldset disabled={!canManage} className="contents">
        <Field label={t("settings.email.hostLabel")} htmlFor={id("host")} error={shown("host")}>
          <Input
            id={id("host")}
            value={draft.host}
            onChange={(event) => onChange({ host: event.target.value })}
            autoComplete="off"
            {...watch("host")}
          />
        </Field>
        <Field label={t("settings.email.portLabel")} htmlFor={id("port")} error={shown("port")}>
          <Input
            id={id("port")}
            type="number"
            min={1}
            max={MAX_PORT}
            value={draft.port}
            onChange={(event) => onChange({ port: event.target.value })}
            {...watch("port")}
          />
        </Field>
        <Field label={t("settings.email.securityLabel")}>
          <PillTabs
            items={SECURITY_OPTIONS.map((option) => ({ key: option, label: t(`settings.email.security.${option}`) }))}
            activeKey={draft.security}
            onSelect={(security) => onChange({ security })}
            disabled={!canManage}
          />
        </Field>
        <Field label={t("settings.email.usernameLabel")} htmlFor={id("username")}>
          <Input
            id={id("username")}
            value={draft.username}
            onChange={(event) => onChange({ username: event.target.value })}
            autoComplete="off"
          />
        </Field>
        <Field label={t("settings.email.passwordLabel")} htmlFor={id("password")}>
          <PasswordInput
            id={id("password")}
            value={draft.password}
            onChange={(event) => onChange({ password: event.target.value })}
            placeholder={current.isPasswordSet ? t("settings.email.passwordSet") : t("settings.email.passwordUnset")}
            // "off" is ignored on password fields: the browser would offer the admin's saved password
            autoComplete="new-password"
          />
        </Field>
        <Field label={t("settings.email.fromAddressLabel")} htmlFor={id("from-address")} error={shown("fromAddress")}>
          <Input
            id={id("from-address")}
            type="email"
            value={draft.fromAddress}
            onChange={(event) => onChange({ fromAddress: event.target.value })}
            autoComplete="off"
            {...watch("fromAddress")}
          />
        </Field>
        <Field label={t("settings.email.fromNameLabel")} htmlFor={id("from-name")}>
          <Input
            id={id("from-name")}
            value={draft.fromName}
            onChange={(event) => onChange({ fromName: event.target.value })}
            autoComplete="off"
          />
        </Field>
      </fieldset>
    </SectionFields>
  );
}
