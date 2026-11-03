import { BellRing, Send } from "lucide-react";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  generateVapidKeys,
  getNotificationSettings,
  sendTestPush,
  updateNotificationSettings,
} from "@entities/notifications/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useFieldValidation } from "@shared/lib/use-field-validation";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { CopyInput, Input } from "@shared/ui/glass/Input";
import { Section, SectionFields } from "@shared/ui/glass/Section";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Spinner } from "@shared/ui/Spinner";
import { StatusPill } from "@shared/ui/glass/StatusPill";

export function WebPushSettingsForm() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("NOTIFICATION_SETTINGS_MANAGE");
  const canGenerate = permissions.includes("NOTIFICATION_VAPID_KEYS_GENERATE");
  const [state, , setData] = useAsyncResource(getNotificationSettings, {
    onSuccess: (data) => setContact(shownContact(data.vapid_contact)),
  });
  const [contact, setContact] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);
  const id = useId();

  const configured = state.kind === "ready" && state.data.is_push_configured;
  const savedContact = state.kind === "ready" ? shownContact(state.data.vapid_contact) : "";
  const contactChanged = contact.trim() !== savedContact;
  const contactValid = EMAIL.test(contact.trim());
  // the first save also creates the keys, so a fresh shop needs one button
  const generatesKeys = state.kind === "ready" && !configured && canGenerate;

  const validation = useFieldValidation<"contact">();
  // keys need a contact, and a set contact can't be cleared
  const contactError =
    contact.trim() === "" ? t("errors.validation.required") : !contactValid ? t("errors.validation.email") : null;
  const contactShown = validation.visible("contact", canManage ? contactError : null);

  const save = async () => {
    validation.submit();
    if (canManage && contactError !== null) return;
    setIsSaving(true);
    try {
      if (contactChanged && canManage) {
        const updated = await updateNotificationSettings({ vapid_contact: contact.trim() });
        setData(updated);
        setContact(shownContact(updated.vapid_contact));
      }
      if (generatesKeys) setData(await generateVapidKeys());
      validation.reset();
      toast.success(t(generatesKeys ? "settings.webPush.generated" : "common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSaving(false);
    }
  };

  const test = async () => {
    try {
      await sendTestPush();
      toast.success(t("profile.notifications.push.testSent"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  const regenerate = async () => {
    setIsConfirming(false);
    try {
      setData(await generateVapidKeys());
      toast.success(t("settings.webPush.generated"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    }
  };

  return (
    <Section
      icon={BellRing}
      title={t("settings.webPush.title")}
      description={t("settings.webPush.description")}
      aside={
        state.kind === "ready" &&
        (configured ? (
          <Button variant="glass" icon={Send} onClick={() => void test()}>
            {t("settings.webPush.test")}
          </Button>
        ) : (
          <StatusPill tone="warning">{t("settings.webPush.notConfigured")}</StatusPill>
        ))
      }
      footer={
        state.kind === "ready" &&
        (canManage || canGenerate) && (
          <SaveFooter
            variant="glassAccent"
            dirty={contactChanged}
            hasWork={generatesKeys}
            saving={isSaving}
            onSave={() => void save()}
            beside={
              configured &&
              canGenerate && (
                <Button variant="glassDanger" onClick={() => setIsConfirming(true)}>
                  {t("settings.webPush.regenerate")}
                </Button>
              )
            }
          />
        )
      }
    >
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (canManage || state.data.vapid_public_key) && (
        <SectionFields>
          {canManage && (
            <Field label={t("settings.webPush.contact")} htmlFor={`${id}-contact`} required error={contactShown}>
              <Input
                id={`${id}-contact`}
                type="email"
                onBlur={validation.touch("contact")}
                aria-invalid={contactShown !== undefined}
                value={contact}
                onChange={(event) => setContact(event.target.value)}
                placeholder={t("settings.webPush.contactPlaceholder")}
              />
            </Field>
          )}
          {state.data.vapid_public_key && (
            <Field label={t("settings.webPush.publicKey")} htmlFor={`${id}-key`}>
              <CopyInput id={`${id}-key`} value={state.data.vapid_public_key} />
            </Field>
          )}
        </SectionFields>
      )}

      {isConfirming && (
        <ConfirmDialog
          title={t("settings.webPush.confirmTitle")}
          message={t("settings.webPush.confirm")}
          confirmLabel={t("settings.webPush.confirmAction")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void regenerate()}
          onCancel={() => setIsConfirming(false)}
        />
      )}
    </Section>
  );
}

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// stored as the mailto: subject, typed as a plain email
function shownContact(contact: string | null): string {
  return contact?.replace(/^mailto:/, "") ?? "";
}
