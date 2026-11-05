import {
  CalendarClock,
  CalendarPlus,
  Filter,
  Gift,
  Globe,
  Hash,
  Info,
  Layers,
  Link2,
  Network,
  Package,
  PackagePlus,
  Pencil,
  Plug,
  RefreshCw,
  Server,
  Smartphone,
  Tag,
  Trash2,
  User,
  Wallet,
  Zap,
} from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  SUBSCRIPTION_STATUS_BADGE_TONE,
  type SubscriptionListItem,
  type TrafficLimitStrategy,
  type UpdateSubscriptionRequest,
  addonTotal,
  daysUntil,
  deleteSubscription,
  getSubscription,
  EXPIRING_SOON_DAYS,
  updateSubscription,
  updateSubscriptionSquads,
} from "@entities/subscriptions/api";
import { BrandMark } from "@entities/appearance/BrandMark";
import { listPlans, NO_PLAN_ICON } from "@entities/plans/api";
import { PlanIcon } from "@entities/plans/PlanIcon";
import { getTransactionSummary } from "@entities/transactions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useCanOpenUsers } from "@features/open-user/openable-user";
import { OpenUserButton } from "@features/open-user/OpenUserButton";
import { PlanSquadsField } from "@features/plan-edit/PlanSquadsField";
import { SubscriptionDevicesTab } from "@features/subscription-edit/SubscriptionDevicesTab";
import { SubscriptionPlanTab } from "@features/subscription-edit/SubscriptionPlanTab";
import { SubscriptionField } from "@features/subscription-edit/SubscriptionField";
import { useSquadName } from "@features/subscription-edit/use-squad-name";
import { useSubscriptionActions } from "@features/subscription-edit/use-subscription-actions";
import { getErrorMessage } from "@shared/api/http";
import { blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { formatBytes, formatMoney } from "@shared/lib/format";
import { formatDate, formatDateTime } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Button } from "@shared/ui/Button";
import { CardPill } from "@shared/ui/CardPill";
import { GLASS_DIALOG_BODY_CLASS, GLASS_DIALOG_CARD_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DateTimePickerField } from "@shared/ui/DateTimePickerField";
import { AnimatedHeight } from "@shared/ui/glass/AnimatedHeight";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { Badge } from "@shared/ui/Badge";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";

const STRATEGIES: TrafficLimitStrategy[] = ["NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"];
const QUICK_EXTEND_DAYS = [7, 30, 90] as const;
const GB_BYTES = 1024 ** 3;
const TRAFFIC_WARNING_RATIO = 0.6;
const TRAFFIC_ERROR_RATIO = 0.9;
const BAR_TONE = {
  ok: "bg-success shadow-[0_0_10px_var(--color-success)]",
  warning: "bg-warning shadow-[0_0_10px_var(--color-warning)]",
  error: "bg-error shadow-[0_0_10px_var(--color-error)]",
} as const;
const TEXT_TONE = { ok: "", warning: "text-warning", error: "text-error" } as const;

type Tab = "params" | "plan" | "devices";

// <input type="datetime-local"> takes local time without a zone
function toLocalInput(iso: string): string {
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

interface SubscriptionEditDialogProps {
  subscription: SubscriptionListItem;
  /** the owner's name when the caller already has it; the id shows otherwise */
  userName?: string | null;
  onSaved?: (updated: SubscriptionListItem) => void;
  /** deleted from the footer; the dialog closes itself */
  onDeleted?: (subscription: SubscriptionListItem) => void;
  onClose: () => void;
}

export function SubscriptionEditDialog({ onClose, ...props }: SubscriptionEditDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <SubscriptionEditDialogBody {...props} />
    </Modal>
  );
}

function SubscriptionEditDialogBody({
  subscription,
  userName,
  onSaved,
  onDeleted,
}: Omit<SubscriptionEditDialogProps, "onClose">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const permissions = usePermissions();
  const canOpenUsers = useCanOpenUsers();
  const [current, setCurrent] = useState(subscription);
  const [tab, setTab] = useState<Tab>("params");
  const [isEditing, setIsEditing] = useState(false);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);

  const canEdit = permissions.includes("SUBSCRIPTIONS_UPDATE") && current.status !== "DELETED";
  const canDelete = permissions.includes("SUBSCRIPTIONS_DELETE");

  const apply = (updated: SubscriptionListItem) => {
    setCurrent(updated);
    onSaved?.(updated);
  };
  const { items: actionItems, confirm: actionConfirm } = useSubscriptionActions(current, apply);
  const menuItems: ActionMenuItem[] = canEdit
    ? [
        {
          label: t("common.edit"),
          icon: Pencil,
          onClick: () => {
            setTab("params");
            setIsEditing(true);
          },
        },
        ...actionItems,
      ]
    : actionItems;

  const tabs: DialogTabItem<Tab>[] = [
    { key: "params", label: t("subscriptions.edit.tabs.params"), icon: Info },
    { key: "plan", label: t("subscriptions.edit.tabs.plan"), icon: Package },
    ...(permissions.includes("SUBSCRIPTIONS_DEVICES_VIEW") && current.status !== "DELETED"
      ? [{ key: "devices" as const, label: t("subscriptions.edit.tabs.devices"), icon: Smartphone }]
      : []),
  ];

  const handleDelete = async () => {
    try {
      await deleteSubscription(current.id);
      onDeleted?.(current);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.delete.error")));
    }
  };

  return (
    <>
      <DialogHeader
        icon={Layers}
        title={t("subscriptions.subscriptionLabel", { id: current.id })}
        subtitle={userName || t("subscriptions.userLabel", { id: current.user_id })}
        actions={
          <>
            {current.is_trial && (
              <Badge borderless tone="warning">
                {t("subscriptions.trial")}
              </Badge>
            )}
            <Badge borderless tone={SUBSCRIPTION_STATUS_BADGE_TONE[current.status]}>
              {t(`subscriptions.status.${current.status}`)}
            </Badge>
            {!isEditing && <ActionMenu glass size="9" items={menuItems} />}
          </>
        }
      />

      {isEditing ? (
        <SubscriptionParamsForm
          subscription={current}
          onSaved={(updated) => {
            apply(updated);
            setIsEditing(false);
          }}
          onCancel={() => setIsEditing(false)}
        />
      ) : (
        <>
          <div className="px-3 pt-3">
            <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
          </div>

          <div className={`${GLASS_DIALOG_BODY_CLASS} max-h-[440px]`}>
            <AnimatedHeight>
              {tab === "params" && <SubscriptionParamsView subscription={current} />}
              {tab === "plan" && <SubscriptionPlanTab subscription={current} onChanged={apply} />}
              {tab === "devices" && <SubscriptionDevicesTab subscriptionId={current.id} />}
            </AnimatedHeight>
          </div>

          {(canDelete || canOpenUsers) && (
            <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 items-center`}>
              {canDelete && (
                <Button variant="glassDanger" type="button" onClick={() => setIsConfirmingDelete(true)}>
                  <Trash2 className="size-4" />
                  {t("common.delete")}
                </Button>
              )}
              <span className="flex-1" />
              <OpenUserButton glass label={t("subscriptions.edit.toUser")} icon={User} user={{ id: current.user_id }} />
            </div>
          )}
        </>
      )}

      {actionConfirm}

      {isConfirmingDelete && (
        <ConfirmDialog
          title={t("subscriptions.delete.confirmTitle")}
          message={t("subscriptions.delete.confirm", { id: current.id })}
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

function SubscriptionParamsView({ subscription }: { subscription: SubscriptionListItem }) {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const canViewSummary = permissions.includes("TRANSACTIONS_SUMMARY_VIEW");
  // a plan change makes a new row, so this counts the orders since the last one
  const [summary] = useAsyncResource(
    (signal) =>
      canViewSummary ? getTransactionSummary({ subscriptionId: subscription.id }, signal) : Promise.resolve(null),
    { deps: [canViewSummary, subscription.id] },
  );
  const paid = summary.kind === "ready" ? summary.data : null;
  const squadName = useSquadName();
  const dateTime = (iso: string | null) => (iso ? formatDateTime(iso, i18n.language) : null);

  return (
    <div className="flex flex-col gap-3">
      <SubscriptionCard subscription={subscription} />
      <DialogCard title={t("subscriptions.details.subscription")} icon={Layers}>
        <SubscriptionField
          icon={Wallet}
          label={t("subscriptions.details.paidTotal")}
          value={paid && Number(paid.revenue) > 0 ? formatMoney(paid.revenue, paid.report_currency, i18n.language) : null}
        />
        <SubscriptionField
          icon={CalendarClock}
          label={t("subscriptions.edit.expireAtLabel")}
          value={formatDateTime(subscription.expire_at, i18n.language)}
          mono
        />
        <SubscriptionField
          icon={CalendarPlus}
          label={t("subscriptions.details.createdAt")}
          value={dateTime(subscription.created_at)}
          mono
        />
        <SubscriptionField
          icon={Plug}
          label={t("subscriptions.details.firstConnectedAt")}
          value={dateTime(subscription.first_connected_at)}
          mono
        />
        <SubscriptionField
          icon={RefreshCw}
          label={t("subscriptions.edit.strategyLabel")}
          value={t(`subscriptions.edit.strategy.${subscription.traffic_limit_strategy}`)}
        />
        <SubscriptionField icon={Tag} label={t("subscriptions.edit.tagLabel")} value={subscription.tag} />
        {subscription.addon_entitlements.length > 0 && (
          <SubscriptionField
            icon={PackagePlus}
            label={t("subscriptions.details.addons")}
            value={subscription.addon_entitlements
              .map(
                (item) =>
                  `+${item.type === "TRAFFIC" ? `${item.amount} GB` : t("plans.devices", { count: item.amount })} · ${formatDate(item.granted_at, i18n.language)}`,
              )
              .join(", ")}
          />
        )}
        <SubscriptionField icon={Link2} label={t("subscriptions.details.link")} value={subscription.url} mono />
      </DialogCard>
      <DialogCard title={t("subscriptions.details.panel")} icon={Server}>
        <SubscriptionField
          icon={Hash}
          label={t("subscriptions.details.remnawaveId")}
          value={String(subscription.remnawave_user_id)}
          mono
        />
        <SubscriptionField
          icon={Network}
          label={t("subscriptions.details.internalSquads")}
          value={subscription.internal_squads.map(squadName).join(", ")}
          copyValue={subscription.internal_squads.join(", ")}
        />
        <SubscriptionField
          icon={Globe}
          label={t("subscriptions.details.externalSquad")}
          value={subscription.external_squad && squadName(subscription.external_squad)}
          copyValue={subscription.external_squad}
        />
      </DialogCard>
    </div>
  );
}

function SubscriptionCard({ subscription }: { subscription: SubscriptionListItem }) {
  const { t, i18n } = useTranslation();
  const permissions = usePermissions();
  const canViewPlans = permissions.includes("PLANS_VIEW");
  const canViewDetails = permissions.includes("SUBSCRIPTIONS_DETAIL_VIEW");
  // the snapshot holds no icon; a deleted or imported plan, or no right to list plans, falls back to the glyph
  const [plans] = useAsyncResource((signal) => (canViewPlans ? listPlans(signal) : Promise.resolve([])), {
    deps: [canViewPlans],
  });
  // only the detail route asks the panel; a change to the subscription (a traffic reset) reads it again
  const [details] = useAsyncResource(
    (signal) => (canViewDetails ? getSubscription(subscription.id, signal) : Promise.resolve(null)),
    { deps: [canViewDetails, subscription], keepData: true },
  );
  const plan = plans.kind === "ready" ? plans.data.find((item) => item.id === subscription.plan_snapshot.plan_id) : undefined;
  const PlanGlyph = subscription.is_trial ? Gift : Zap;

  const used = details.kind === "ready" ? (details.data?.used_traffic ?? null) : null;
  const limitGb = subscription.effective_traffic_limit;
  const limitBytes = limitGb * GB_BYTES;
  const ratio = limitGb > 0 && used !== null ? Math.min(used / limitBytes, 1) : null;
  const trafficTone =
    subscription.status === "LIMITED" || (ratio !== null && ratio > TRAFFIC_ERROR_RATIO)
      ? "error"
      : ratio !== null && ratio >= TRAFFIC_WARNING_RATIO
        ? "warning"
        : "ok";
  const days = daysUntil(subscription.expire_at);
  const daysTone = days <= 0 ? "error" : days <= EXPIRING_SOON_DAYS ? "warning" : "ok";
  const devices = subscription.effective_device_limit;
  const limitText = formatBytes(limitBytes, i18n.language);

  return (
    <div
      className={`relative flex flex-col gap-3 overflow-hidden rounded-xl border border-white/[0.14] bg-white/[0.06] px-[18px] py-4 ${
        subscription.status === "ACTIVE" ? "text-foreground" : "text-muted-foreground"
      }`}
    >
      <BrandMark className="pointer-events-none absolute -bottom-5 -right-5 size-36 opacity-[0.04]" />

      <div className="relative flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-1.5 text-sm font-semibold">
          <PlanIcon
            icon={plan ?? NO_PLAN_ICON}
            size={16}
            fallback={plans.kind === "loading" ? <span className="size-4 shrink-0" /> : <PlanGlyph className="size-4 shrink-0" />}
          />
          <span className="truncate">{subscription.plan_snapshot.name}</span>
        </div>
        <span className="shrink-0 font-mono text-[12px] tracking-[0.12em] text-muted-foreground">#{subscription.id}</span>
      </div>

      <div className="relative flex flex-col gap-1.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className={`text-[26px] font-bold leading-[1.1] tracking-tight tabular-nums ${TEXT_TONE[trafficTone]}`}>
            {limitGb === 0
              ? "∞"
              : used === null
                ? limitText
                : formatBytes(Math.max(0, limitBytes - used), i18n.language)}
          </span>
          {used !== null && (
            <span className="min-w-0 truncate text-[13px] font-bold">
              {t("subscriptions.details.trafficUsed", { value: formatBytes(used, i18n.language) })}
            </span>
          )}
        </div>
        {ratio !== null && (
          <div className="h-2.5 overflow-hidden rounded-full glass-track">
            <div className={`h-full rounded-full ${BAR_TONE[trafficTone]}`} style={{ width: `${(1 - ratio) * 100}%` }} />
          </div>
        )}
        <div className="text-[12px] text-muted-foreground">
          {limitGb === 0
            ? t("subscriptions.details.trafficUnlimited")
            : ratio === null
              ? t("subscriptions.details.trafficLimit")
              : t("subscriptions.details.trafficLeftOf", { limit: limitText })}
        </div>
      </div>

      <div className="relative mt-1 flex gap-2">
        <CardPill
          label={t("subscriptions.details.daysLeft")}
          value={days > 0 ? t("subscriptions.duration.days", { count: days }) : t("subscriptions.status.EXPIRED")}
          valueClassName={TEXT_TONE[daysTone]}
        />
        <CardPill
          label={t("subscriptions.fields.devices")}
          value={devices === 0 ? "∞" : t("subscriptions.details.devicesUpTo", { limit: devices })}
        />
      </div>
    </div>
  );
}

function SubscriptionParamsForm({
  subscription,
  onSaved,
  onCancel,
}: {
  subscription: SubscriptionListItem;
  onSaved: (updated: SubscriptionListItem) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManageSquads =
    permissions.includes("SUBSCRIPTIONS_SQUADS_MANAGE") && permissions.includes("SUBSCRIPTIONS_PANEL_SQUADS_VIEW");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [initialSquads] = useState({
    internal_squads: subscription.internal_squads,
    external_squad: subscription.external_squad,
  });
  const [squads, setSquads] = useState(initialSquads);
  const squadsChanged = JSON.stringify(squads) !== JSON.stringify(initialSquads);
  // the fields hold the subscription's own limits; bought add-ons come on top
  const addonTraffic = addonTotal(subscription, "TRAFFIC");
  const addonDevices = addonTotal(subscription, "DEVICES");
  const withAddons = (hint: string, extra: string | 0) =>
    extra ? `${hint} · ${t("subscriptions.edit.addonsHint", { value: extra })}` : hint;
  const [tag, setTag] = useState(subscription.tag ?? "");
  const [trafficGb, setTrafficGb] = useState(String(subscription.traffic_limit));
  const [deviceLimit, setDeviceLimit] = useState(String(subscription.device_limit));
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(subscription.traffic_limit_strategy);
  const initialExpireAt = toLocalInput(subscription.expire_at);
  const [expireAt, setExpireAt] = useState(initialExpireAt);

  // calendar days, so a DST switch doesn't move the hour; a cleared field counts from the current expiry
  const addDays = (days: number) =>
    setExpireAt((value) => {
      const date = new Date(value || initialExpireAt);
      date.setDate(date.getDate() + days);
      return toLocalInput(date.toISOString());
    });

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const parsedTrafficGb = parseRequiredInt(trafficGb, 0);
    const parsedDeviceLimit = parseRequiredInt(deviceLimit, 0);
    const parsedExpireAt = new Date(expireAt);
    if (parsedTrafficGb === undefined || parsedDeviceLimit === undefined || Number.isNaN(parsedExpireAt.getTime())) {
      toast.error(t("errors.invalidNumber"));
      return;
    }
    // an untouched past expiry stays out of the request and doesn't block the rest
    const expireAtChanged = expireAt !== initialExpireAt;
    if (expireAtChanged && parsedExpireAt.getTime() <= Date.now()) {
      toast.error(t("subscriptions.edit.expireAtInPast"));
      return;
    }

    // only what changed: every field sent is written to the panel too; null empties the tag
    const nextTag = tag.trim() || null;
    const payload: UpdateSubscriptionRequest = {
      ...(nextTag !== subscription.tag && { tag: nextTag }),
      ...(parsedTrafficGb !== subscription.traffic_limit && { traffic_limit: parsedTrafficGb }),
      ...(parsedDeviceLimit !== subscription.device_limit && { device_limit: parsedDeviceLimit }),
      ...(strategy !== subscription.traffic_limit_strategy && { traffic_limit_strategy: strategy }),
      ...(expireAtChanged && { expire_at: parsedExpireAt.toISOString() }),
    };
    const fieldsChanged = Object.keys(payload).length > 0;
    if (!fieldsChanged && !squadsChanged) {
      onSaved(subscription);
      return;
    }

    setIsSubmitting(true);
    try {
      // two requests: a failed squads write leaves the fields saved, and a retry sends them again harmlessly
      let updated = fieldsChanged ? await updateSubscription(subscription.id, payload) : subscription;
      if (squadsChanged) updated = await updateSubscriptionSquads(subscription.id, squads);
      toast.success(t("subscriptions.edit.saved"));
      onSaved(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
      <div className={`${GLASS_DIALOG_BODY_CLASS} flex flex-col gap-3`}>
        <div className={GLASS_DIALOG_CARD_CLASS}>
          <div className="grid grid-cols-2 gap-3">
            <Field label={t("subscriptions.edit.trafficLabel")} htmlFor="sub-edit-traffic" hint={withAddons(t("subscriptions.edit.trafficHint"), addonTraffic && `${addonTraffic} GB`)}>
              <Input
                id="sub-edit-traffic"
                type="number"
                onKeyDown={blockNonIntegerKeys}
                min={0}
                step="1"
                value={trafficGb}
                onChange={(event) => setTrafficGb(event.target.value)}
              />
            </Field>
            <Field label={t("subscriptions.edit.deviceLabel")} htmlFor="sub-edit-devices" hint={withAddons(t("subscriptions.edit.deviceHint"), addonDevices && t("plans.devices", { count: addonDevices }))}>
              <Input
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
              variant="well"
              size="compact"
              id="sub-edit-strategy"
              value={strategy}
              onChange={(value) => setStrategy(value as TrafficLimitStrategy)}
              icon={Filter}
              placeholder={t(`subscriptions.edit.strategy.${strategy}`)}
              options={STRATEGIES.map((value) => ({ value, label: t(`subscriptions.edit.strategy.${value}`) }))}
            />
          </Field>
        </div>

        {canManageSquads && (
          <div className={GLASS_DIALOG_CARD_CLASS}>
            <PlanSquadsField value={squads} onChange={setSquads} />
          </div>
        )}

        <div className={GLASS_DIALOG_CARD_CLASS}>
          <Field label={t("subscriptions.edit.expireAtLabel")}>
            <div className="flex items-center gap-2">
              <DateTimePickerField
                value={expireAt}
                onChange={setExpireAt}
                placeholder={t("subscriptions.edit.expireAtLabel")}
                className="min-w-0 flex-1"
              />
              {QUICK_EXTEND_DAYS.map((days) => (
                <Button key={days} variant="glass" type="button" onClick={() => addDays(days)}>
                  {t("subscriptions.edit.plusDays", { days })}
                </Button>
              ))}
            </div>
          </Field>
        </div>

        <div className={GLASS_DIALOG_CARD_CLASS}>
          <Field label={t("subscriptions.edit.tagLabel")} htmlFor="sub-edit-tag">
            <Input
              id="sub-edit-tag"
              value={tag}
              onChange={(event) => setTag(event.target.value)}
              placeholder={t("subscriptions.edit.tagPlaceholder")}
            />
          </Field>
        </div>
      </div>

      <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 items-center justify-end`}>
        <Button variant="glass" type="button" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        <Button variant="glassAccent" type="submit" isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      </div>
    </form>
  );
}
