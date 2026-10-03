import { Filter, Layers, Trash2, User } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  SUBSCRIPTION_STATUS_BADGE_TONE,
  type SubscriptionListItem,
  type TrafficLimitStrategy,
  deleteSubscription,
  updateSubscription,
} from "@entities/subscriptions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { OpenUserButton } from "@features/open-user/OpenUserButton";
import { getErrorMessage } from "@shared/api/http";
import { blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Badge } from "@shared/ui/Badge";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Field } from "@shared/ui/Field";

const STRATEGIES: TrafficLimitStrategy[] = ["NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"];


interface SubscriptionEditDialogProps {
  subscription: SubscriptionListItem;
  onSaved?: (updated: SubscriptionListItem) => void;
  /** deleted from the footer; the dialog closes itself */
  onDeleted?: (subscription: SubscriptionListItem) => void;
  onClose: () => void;
}

export function SubscriptionEditDialog({ onClose, ...props }: SubscriptionEditDialogProps) {
  return (
    <Modal onClose={onClose} size="lg">
      <SubscriptionEditDialogBody {...props} />
    </Modal>
  );
}

function SubscriptionEditDialogBody({ subscription, onSaved, onDeleted }: Omit<SubscriptionEditDialogProps, "onClose">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const permissions = usePermissions();
  const canEdit = permissions.includes("SUBSCRIPTIONS_UPDATE");
  const canDelete = permissions.includes("SUBSCRIPTIONS_DELETE");
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tag, setTag] = useState(subscription.tag ?? "");
  const [trafficGb, setTrafficGb] = useState(String(subscription.traffic_limit));
  const [deviceLimit, setDeviceLimit] = useState(String(subscription.device_limit));
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(subscription.traffic_limit_strategy);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const parsedTrafficGb = parseRequiredInt(trafficGb, 0);
    const parsedDeviceLimit = parseRequiredInt(deviceLimit, 0);
    if (parsedTrafficGb === undefined || parsedDeviceLimit === undefined) {
      toast.error(t("errors.invalidNumber"));
      return;
    }

    setIsSubmitting(true);
    try {
      const updated = await updateSubscription(subscription.id, {
        tag: tag.trim() || null,
        traffic_limit: parsedTrafficGb,
        device_limit: parsedDeviceLimit,
        traffic_limit_strategy: strategy,
      });
      toast.success(t("subscriptions.edit.saved"));
      onSaved?.(updated);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };


  const handleDelete = async () => {
    try {
      await deleteSubscription(subscription.id);
      onDeleted?.(subscription);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.delete.error")));
    }
  };

  return (
    <>
      <DialogHeader
        icon={Layers}
        tone={subscription.status === "ACTIVE" ? "primary" : "muted"}
        title={t("subscriptions.subscriptionLabel", { id: subscription.id })}
        badges={
          <>
            <Badge tone={SUBSCRIPTION_STATUS_BADGE_TONE[subscription.status]}>
              {t(`subscriptions.status.${subscription.status}`)}
            </Badge>
            {subscription.is_trial && (
              <Badge tone="warning">
                {t("subscriptions.trial")}
              </Badge>
            )}
          </>
        }
        subtitle={<span className="font-mono">{t("subscriptions.userLabel", { id: subscription.user_id })}</span>}
        actions={
          <OpenUserButton label={t("subscriptions.edit.toUser")} icon={User} user={{ id: subscription.user_id }} size="sm" />
        }
      />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <fieldset disabled={!canEdit} className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <Card variant="form">
            <div className="grid grid-cols-2 gap-3">
              <Field label={t("subscriptions.edit.trafficLabel")} htmlFor="sub-edit-traffic" hint={t("subscriptions.edit.trafficHint")}>
                <TextInput
                  id="sub-edit-traffic"
                  type="number"
                  onKeyDown={blockNonIntegerKeys}
                  min={0}
                  step="1"
                  value={trafficGb}
                  onChange={(event) => setTrafficGb(event.target.value)}
                />
              </Field>
              <Field label={t("subscriptions.edit.deviceLabel")} htmlFor="sub-edit-devices" hint={t("subscriptions.edit.deviceHint")}>
                <TextInput
                  id="sub-edit-devices"
                  type="number"
                  onKeyDown={blockNonIntegerKeys}
                  min={0}
                  step="1"
                  value={deviceLimit}
                  onChange={(event) => setDeviceLimit(event.target.value)}
                />
              </Field>
            </div>
            <Field label={t("subscriptions.edit.strategyLabel")} htmlFor="sub-edit-strategy">
              <SelectDropdown
                variant="form"
                id="sub-edit-strategy"
                value={strategy}
                onChange={(value) => setStrategy(value as TrafficLimitStrategy)}
                icon={Filter}
                placeholder={t(`subscriptions.edit.strategy.${strategy}`)}
                options={STRATEGIES.map((value) => ({ value, label: t(`subscriptions.edit.strategy.${value}`) }))}
              />
            </Field>
          </Card>

          <Card variant="form">
            <Field label={t("subscriptions.edit.tagLabel")} htmlFor="sub-edit-tag">
              <TextInput
                id="sub-edit-tag"
                value={tag}
                onChange={(event) => setTag(event.target.value)}
                placeholder={t("subscriptions.edit.tagPlaceholder")}
              />
            </Field>
          </Card>
        </fieldset>

        <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.07] px-5 py-3.5">
          {canDelete && (
            <Button
              variant="danger"
              type="button"
              onClick={() => setIsConfirmingDelete(true)}
            >
              <Trash2 className="size-3.5" />
              {t("subscriptions.delete.confirmButton")}
            </Button>
          )}
          <span className="flex-1" />
          <Button
            variant="outline"
            type="button"
            onClick={close}
          >
            {t("subscriptions.edit.cancel")}
          </Button>
          {canEdit && (
            <Button
              variant="accent"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? t("subscriptions.edit.saving") : t("subscriptions.edit.save")}
            </Button>
          )}
        </div>
      </form>

      {isConfirmingDelete && (
        <ConfirmDialog
          title={t("subscriptions.delete.confirmTitle")}
          message={t("subscriptions.delete.confirm", { id: subscription.id })}
          confirmLabel={t("subscriptions.delete.confirmButton")}
          cancelLabel={t("subscriptions.delete.cancelButton")}
          danger
          onConfirm={() => {
            setIsConfirmingDelete(false);
            void handleDelete();
          }}
          onCancel={() => setIsConfirmingDelete(false)}
        />
      )}
    </>
  );
}
