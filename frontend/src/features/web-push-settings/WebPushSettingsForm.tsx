import { BellRing } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { generateVapidKeys, getNotificationSettings, updateNotificationSettings } from "@entities/notifications/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { ErrorState } from "@shared/ui/EmptyState";
import { Field } from "@shared/ui/Field";
import { Spinner } from "@shared/ui/Spinner";
import { TextInput } from "@shared/ui/TextInput";

export function WebPushSettingsForm() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("NOTIFICATION_SETTINGS_MANAGE");
  const canGenerate = permissions.includes("NOTIFICATION_VAPID_KEYS_GENERATE");
  const [state, , setData] = useAsyncResource(getNotificationSettings, {
    onSuccess: (data) => setContact(data.vapid_contact ?? ""),
  });
  const [contact, setContact] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isConfirming, setIsConfirming] = useState(false);

  const saveContact = async () => {
    setIsSaving(true);
    try {
      const updated = await updateNotificationSettings({ vapid_contact: contact.trim() });
      setData(updated);
      setContact(updated.vapid_contact ?? "");
      toast.success(t("common.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsSaving(false);
    }
  };

  const generate = async () => {
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
            <Badge tone={state.data.is_push_configured ? "success" : "neutral"}>
              {t(state.data.is_push_configured ? "settings.webPush.configured" : "settings.webPush.notConfigured")}
            </Badge>
          )
        }
      />

      <div className="mt-4 flex flex-col gap-3">
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {state.kind === "ready" && (
          <>
            {state.data.vapid_public_key && (
              <CopyableValue label={t("settings.webPush.publicKey")} value={state.data.vapid_public_key} />
            )}
            {canManage && (
              <Field label={t("settings.webPush.contact")} hint={t("settings.webPush.contactHint")}>
                <div className="flex gap-2">
                  <TextInput
                    value={contact}
                    onChange={(event) => setContact(event.target.value)}
                    placeholder={t("settings.webPush.contactPlaceholder")}
                    className="flex-1"
                  />
                  <Button
                    variant="secondary"
                    size="field"
                    disabled={isSaving || contact.trim() === (state.data.vapid_contact ?? "")}
                    onClick={() => void saveContact()}
                  >
                    {t("common.save")}
                  </Button>
                </div>
              </Field>
            )}
            {canGenerate && (
              <div className="flex justify-end">
                <Button
                  variant={state.data.is_push_configured ? "danger" : "accent"}
                  onClick={() => (state.data.is_push_configured ? setIsConfirming(true) : void generate())}
                >
                  {t(state.data.is_push_configured ? "settings.webPush.regenerate" : "settings.webPush.generate")}
                </Button>
              </div>
            )}
          </>
        )}
      </div>

      {isConfirming && (
        <ConfirmDialog
          title={t("settings.webPush.confirmTitle")}
          message={t("settings.webPush.confirm")}
          confirmLabel={t("settings.webPush.regenerate")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void generate()}
          onCancel={() => setIsConfirming(false)}
        />
      )}
    </Card>
  );
}
