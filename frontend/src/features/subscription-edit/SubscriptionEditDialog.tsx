import { Filter, Layers, SlidersHorizontal, Smartphone, Trash2, User } from "lucide-react";
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
import { SubscriptionDevicesTab } from "@features/subscription-edit/SubscriptionDevicesTab";
import { SubscriptionPlanTab } from "@features/subscription-edit/SubscriptionPlanTab";
import { useSubscriptionActions } from "@features/subscription-edit/use-subscription-actions";
import { getErrorMessage } from "@shared/api/http";
import { blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { ActionMenu } from "@shared/ui/ActionMenu";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { Badge } from "@shared/ui/Badge";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Field } from "@shared/ui/Field";

const STRATEGIES: TrafficLimitStrategy[] = ["NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"];
const QUICK_EXTEND_DAYS = [7, 30, 90] as const;
const DAY_MS = 86_400_000;

type Tab = "params" | "plan" | "devices";

// <input type="datetime-local"> takes local time without a zone
function toLocalInput(iso: string): string {
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

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
  const permissions = usePermissions();
  const [current, setCurrent] = useState(subscription);
  // remounts the settings form on every server update, so its fields show the new values
  const [version, setVersion] = useState(0);
  const [tab, setTab] = useState<Tab>("params");

  const apply = (updated: SubscriptionListItem) => {
    setCurrent(updated);
    setVersion((value) => value + 1);
    onSaved?.(updated);
  };
  const { items: actionItems, confirm: actionConfirm } = useSubscriptionActions(current, apply);

  const tabs: DialogTabItem<Tab>[] = [
    { key: "params", label: t("subscriptions.edit.tabs.params"), icon: SlidersHorizontal },
    { key: "plan", label: t("subscriptions.edit.tabs.plan"), icon: Layers },
    ...(permissions.includes("SUBSCRIPTIONS_DEVICES_VIEW") && current.status !== "DELETED"
      ? [{ key: "devices" as const, label: t("subscriptions.edit.tabs.devices"), icon: Smartphone }]
      : []),
  ];

  return (
    <>
      <DialogHeader
        icon={Layers}
        tone={current.status === "ACTIVE" ? "primary" : "muted"}
        title={t("subscriptions.subscriptionLabel", { id: current.id })}
        badges={
          <>
            <Badge tone={SUBSCRIPTION_STATUS_BADGE_TONE[current.status]}>
              {t(`subscriptions.status.${current.status}`)}
            </Badge>
            {current.is_trial && (
              <Badge tone="warning">
                {t("subscriptions.trial")}
              </Badge>
            )}
          </>
        }
        subtitle={<span className="font-mono">{t("subscriptions.userLabel", { id: current.user_id })}</span>}
        actions={
          <>
            <OpenUserButton label={t("subscriptions.edit.toUser")} icon={User} user={{ id: current.user_id }} size="sm" />
            {actionItems.length > 0 && <ActionMenu items={actionItems} />}
          </>
        }
      />

      <div className="px-4 pt-1">
        <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
      </div>

      {tab === "params" && (
        <SubscriptionParamsForm key={`${current.id}-${version}`} subscription={current} onSaved={apply} onDeleted={onDeleted} />
      )}
      {tab === "plan" && (
        <div className="scroll-fade-y min-h-0 flex-1 overflow-y-auto p-4">
          <SubscriptionPlanTab subscription={current} onChanged={apply} />
        </div>
      )}
      {tab === "devices" && (
        <div className="scroll-fade-y min-h-0 flex-1 overflow-y-auto p-4">
          <SubscriptionDevicesTab subscriptionId={current.id} />
        </div>
      )}

      {actionConfirm}
    </>
  );
}

function SubscriptionParamsForm({ subscription, onSaved, onDeleted }: Omit<SubscriptionEditDialogProps, "onClose">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const permissions = usePermissions();
  const canEdit = permissions.includes("SUBSCRIPTIONS_UPDATE") && subscription.status !== "DELETED";
  const canDelete = permissions.includes("SUBSCRIPTIONS_DELETE");
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [tag, setTag] = useState(subscription.tag ?? "");
  const [trafficGb, setTrafficGb] = useState(String(subscription.traffic_limit));
  const [deviceLimit, setDeviceLimit] = useState(String(subscription.device_limit));
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(subscription.traffic_limit_strategy);
  const initialExpireAt = toLocalInput(subscription.expire_at);
  const [expireAt, setExpireAt] = useState(initialExpireAt);

  const addDays = (days: number) =>
    setExpireAt((value) => toLocalInput(new Date(new Date(value).getTime() + days * DAY_MS).toISOString()));

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const parsedTrafficGb = parseRequiredInt(trafficGb, 0);
    const parsedDeviceLimit = parseRequiredInt(deviceLimit, 0);
    const parsedExpireAt = new Date(expireAt);
    if (parsedTrafficGb === undefined || parsedDeviceLimit === undefined || Number.isNaN(parsedExpireAt.getTime())) {
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
        // untouched expiry stays out of the request, so the panel isn't written for nothing
        ...(expireAt !== initialExpireAt && { expire_at: parsedExpireAt.toISOString() }),
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
      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <fieldset disabled={!canEdit} className="scroll-fade-y flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
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
            <Field label={t("subscriptions.edit.expireAtLabel")} htmlFor="sub-edit-expire">
              <div className="flex items-center gap-2">
                <TextInput
                  id="sub-edit-expire"
                  type="datetime-local"
                  value={expireAt}
                  onChange={(event) => setExpireAt(event.target.value)}
                />
                {QUICK_EXTEND_DAYS.map((days) => (
                  <Button key={days} variant="secondary" size="field" type="button" onClick={() => addDays(days)}>
                    {t("subscriptions.edit.plusDays", { days })}
                  </Button>
                ))}
              </div>
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
              {t("common.delete")}
            </Button>
          )}
          <span className="flex-1" />
          <Button
            variant="outline"
            type="button"
            onClick={close}
          >
            {t("common.cancel")}
          </Button>
          {canEdit && (
            <Button
              variant="accent"
              type="submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? t("common.saving") : t("common.save")}
            </Button>
          )}
        </div>
      </form>

      {isConfirmingDelete && (
        <ConfirmDialog
          title={t("subscriptions.delete.confirmTitle")}
          message={t("subscriptions.delete.confirm", { id: subscription.id })}
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
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
