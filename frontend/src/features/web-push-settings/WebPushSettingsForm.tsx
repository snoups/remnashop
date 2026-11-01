import { BellRing } from "lucide-react";
import { useState } from "react";
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
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { ErrorState } from "@shared/ui/EmptyState";
import { Field } from "@shared/ui/Field";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Spinner } from "@shared/ui/Spinner";
import { StatusPill } from "@shared/ui/StatusPill";
import { TextInput } from "@shared/ui/TextInput";

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

  const configured = state.kind === "ready" && state.data.is_push_configured;
  const savedContact = state.kind === "ready" ? shownContact(state.data.vapid_contact) : "";
  const contactChanged = contact.trim() !== savedContact;
  const contactValid = EMAIL.test(contact.trim());
  // the first save also creates the keys, so a fresh shop needs one button
  const generatesKeys = state.kind === "ready" && !configured && canGenerate;

  const save = async () => {
    setIsSaving(true);
    try {
      if (contactChanged && canManage) {
        const updated = await updateNotificationSettings({ vapid_contact: contact.trim() });
        setData(updated);
        setContact(shownContact(updated.vapid_contact));
      }
      if (generatesKeys) setData(await generateVapidKeys());
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
    <Card>
      <CardHeader
        icon={BellRing}
        title={t("settings.webPush.title")}
        description={t("settings.webPush.description")}
        aside={
          state.kind === "ready" && (
            <>
              {configured && (
                <Button variant="outline" onClick={() => void test()}>
                  {t("settings.webPush.test")}
                </Button>
              )}
              <StatusPill tone={configured ? "success" : "warning"}>
                {t(configured ? "settings.webPush.configured" : "settings.webPush.notConfigured")}
              </StatusPill>
            </>
          )
        }
      />

      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <>
          <div className="mt-4 flex flex-col gap-3 px-[12.5px]">
            {canManage && (
              <Field bright label={t("settings.webPush.contact")} required>
                <TextInput
                  type="email"
                  aria-invalid={contact.trim() !== "" && !contactValid}
                  value={contact}
                  onChange={(event) => setContact(event.target.value)}
                  placeholder={t("settings.webPush.contactPlaceholder")}
                />
              </Field>
            )}
            {state.data.vapid_public_key && (
              <Field bright label={t("settings.webPush.publicKey")}>
                <CopyableValue value={state.data.vapid_public_key} />
              </Field>
            )}
          </div>
          {(canManage || canGenerate) && (
            <SaveFooter
              dirty={contactChanged}
              hasWork={generatesKeys}
              saving={isSaving}
              // keys need a contact, and a set contact can't be cleared
              disabled={!contactValid}
              onSave={() => void save()}
              beside={
                configured &&
                canGenerate && (
                  <Button variant="danger" onClick={() => setIsConfirming(true)}>
                    {t("settings.webPush.regenerate")}
                  </Button>
                )
              }
            />
          )}
        </>
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
    </Card>
  );
}

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

// stored as the mailto: subject, typed as a plain email
function shownContact(contact: string | null): string {
  return contact?.replace(/^mailto:/, "") ?? "";
}
