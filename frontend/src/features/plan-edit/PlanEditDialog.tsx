import { closestCenter, DndContext, type DragEndEvent, KeyboardSensor, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  ArrowDownUp,
  Columns2,
  GripVertical,
  Infinity as InfinityIcon,
  Package,
  Plus,
  Smartphone,
  Sparkles,
  Trash2,
} from "lucide-react";
import { type ComponentType, type FormEvent, type ReactNode, useState } from "react";
import type { ParseKeys } from "i18next";
import { useTranslation } from "react-i18next";

import {
  type CreatePlanRequest,
  createPlan,
  NO_PLAN_ICON,
  type Plan,
  type PlanIconValue,
  type PlanSquads,
  type PlanBadge,
  type PlanType,
  setPlanDurations,
  type TrafficLimitStrategy,
  updatePlan,
  updatePlanAccess,
  updatePlanSquads,
} from "@entities/plans/api";
import { usePermissions } from "@entities/user/use-current-user";
import { PlanAccessFields } from "@features/plan-access/PlanAccessDialog";
import { planAccessPayload, planAccessValue } from "@features/plan-access/access-value";
import { PlanIconPicker } from "@features/plan-edit/PlanIconPicker";
import { PlanShareLinks } from "@features/plan-edit/PlanShareLinks";
import { PlanSquadsField } from "@features/plan-edit/PlanSquadsField";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { blockNonDecimalKeys, blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { randomId } from "@shared/lib/random-string";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_CARD_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { CopyInput, Input, TextArea } from "@shared/ui/glass/Input";
import { Switch } from "@shared/ui/glass/Switch";
import { IconButton } from "@shared/ui/IconButton";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { Pressable } from "@shared/ui/Pressable";

const PLAN_BADGES: PlanBadge[] = ["POPULAR", "BEST_VALUE"];
const PLAN_TYPES: PlanType[] = ["TRAFFIC", "DEVICES", "BOTH", "UNLIMITED"];
const PLAN_TYPE_ICON: Record<PlanType, ComponentType<{ className?: string }>> = {
  TRAFFIC: ArrowDownUp,
  DEVICES: Smartphone,
  BOTH: Columns2,
  UNLIMITED: InfinityIcon,
};
const STRATEGIES: TrafficLimitStrategy[] = ["NO_RESET", "DAY", "WEEK", "MONTH", "MONTH_ROLLING"];
const DURATION_PRESETS = [7, 30, 60, 90, 180, 365];

interface DurationRow {
  id: string;
  days: string;
  base_price: string;
}

interface PlanEditDialogProps {
  plan: Plan | null;
  anchorCurrency: string | null;
  onClose: () => void;
  onSaved: (plan: Plan) => void;
}

// what setPlanDurations would change; unchanged durations aren't sent
function durationsKey(rows: DurationRow[]): string {
  return JSON.stringify(rows.map((row) => [row.days, row.base_price]));
}

const hintClassName = "text-[12px] text-muted-foreground";

export function PlanEditDialog({ plan, anchorCurrency, onClose, onSaved }: PlanEditDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <PlanEditDialogBody plan={plan} anchorCurrency={anchorCurrency} onSaved={onSaved} />
    </Modal>
  );
}

function PlanEditDialogBody({
  plan,
  anchorCurrency,
  onSaved,
}: Pick<PlanEditDialogProps, "plan" | "anchorCurrency" | "onSaved">) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canShare = permissions.includes("PLANS_SHARE_VIEW");
  const canManageDurations = permissions.includes("PLANS_DURATIONS_MANAGE");
  const canManageSquads =
    permissions.includes("PLANS_SQUADS_MANAGE") && permissions.includes("SUBSCRIPTIONS_PANEL_SQUADS_VIEW");
  const canManageAccess = permissions.includes("PLANS_ACCESS_MANAGE");
  const close = useModalClose();
  const isCreate = plan === null;
  // durations and squads have their own permissions, the plan's own fields need PLANS_UPDATE
  const canEditFields = isCreate || permissions.includes("PLANS_UPDATE");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState(plan?.name ?? "");
  const [icon, setIcon] = useState<PlanIconValue>(
    plan
      ? { icon_emoji_id: plan.icon_emoji_id, icon_emoji_fallback: plan.icon_emoji_fallback }
      : NO_PLAN_ICON,
  );
  const [description, setDescription] = useState(plan?.description ?? "");
  const [tag, setTag] = useState(plan?.tag ?? "");
  const [badge, setBadge] = useState<PlanBadge | "">(plan?.badge ?? "");
  const [type, setType] = useState<PlanType>(plan?.type ?? "BOTH");
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(plan?.traffic_limit_strategy ?? "NO_RESET");
  // 0 (unlimited) is the type's to say: a limited type starts from an empty field
  const [trafficLimit, setTrafficLimit] = useState(plan?.traffic_limit ? String(plan.traffic_limit) : "");
  const [deviceLimit, setDeviceLimit] = useState(plan?.device_limit ? String(plan.device_limit) : "");
  const [isTrial, setIsTrial] = useState(plan?.is_trial ?? false);
  const [allowBonusDays, setAllowBonusDays] = useState(plan?.allow_bonus_days ?? true);
  const [allowPromocodes, setAllowPromocodes] = useState(plan?.allow_promocodes ?? true);
  const [initialDurations] = useState<DurationRow[]>(() =>
    (plan?.durations ?? [])
      .slice()
      .sort((a, b) => a.order_index - b.order_index)
      .map((d) => ({ id: randomId(), days: String(d.days), base_price: d.base_price })),
  );
  const [durations, setDurations] = useState(initialDurations);
  const [initialSquads] = useState<PlanSquads>({
    internal_squads: plan?.internal_squads ?? [],
    external_squad: plan?.external_squad ?? null,
  });
  const [squads, setSquads] = useState(initialSquads);
  const squadsChanged = JSON.stringify(squads) !== JSON.stringify(initialSquads);
  const fieldsKey = JSON.stringify([
    name, icon, description, tag, badge, type, strategy, trafficLimit, deviceLimit, isTrial, allowBonusDays,
    allowPromocodes,
  ]);
  const [initialFieldsKey] = useState(fieldsKey);
  // set here only while creating; an existing plan has its own access dialog
  const [access, setAccess] = useState(() => planAccessValue(null));
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const addDuration = (days: string) =>
    setDurations((rows) => [...rows, { id: randomId(), days, base_price: "0" }]);
  const removeDuration = (id: string) => setDurations((rows) => rows.filter((row) => row.id !== id));
  const updateDuration = (id: string, patch: Partial<DurationRow>) =>
    setDurations((rows) => rows.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  const handleDurationDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over || active.id === over.id) return;
    setDurations((rows) =>
      arrayMove(
        rows,
        rows.findIndex((row) => row.id === active.id),
        rows.findIndex((row) => row.id === over.id),
      ),
    );
  };

  const usedDays = new Set(durations.map((row) => Number(row.days)));
  // a trial plan has exactly one duration
  const presets = isTrial && durations.length > 0 ? [] : DURATION_PRESETS.filter((days) => !usedDays.has(days));
  const canAddDuration = canManageDurations && (!isTrial || durations.length === 0);
  const handleTrialChange = (checked: boolean) => {
    setIsTrial(checked);
    if (checked) {
      setDurations((rows) => rows.slice(0, 1));
      setBadge("");
      if (access.availability === "EXISTING") setAccess({ ...access, availability: "ALL" });
    }
  };
  // an existing plan's access is set in its own dialog; a trial can't stay EXISTING
  const isTrialBlocked = !isTrial && plan?.availability === "EXISTING";
  const currencySuffix = anchorCurrency ? currencySymbol(anchorCurrency) : null;
  const hasTraffic = type === "TRAFFIC" || type === "BOTH";
  const hasDevices = type === "DEVICES" || type === "BOTH";

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    // a limit the type hides is zeroed by the server; its stale field mustn't block the save
    const parsedTrafficLimit = hasTraffic ? parseRequiredInt(trafficLimit, 1) : 0;
    const parsedDeviceLimit = hasDevices ? parseRequiredInt(deviceLimit, 1) : 0;
    const parsedDurations = durations.map((row) => ({
      ...row,
      parsedDays: parseRequiredInt(row.days, 1),
    }));
    if (
      parsedTrafficLimit === undefined ||
      parsedDeviceLimit === undefined ||
      parsedDurations.some((row) => row.parsedDays === undefined)
    ) {
      toast.error(t("errors.invalidNumber"));
      return;
    }

    const durationsPayload = parsedDurations.map((row, index) => ({
      days: row.parsedDays!,
      order_index: index,
      base_price: row.base_price,
    }));

    setIsSubmitting(true);
    try {
      if (isCreate) {
        const payload: CreatePlanRequest = {
          name: name.trim(),
          description: description.trim() || null,
          tag: tag.trim() || null,
          badge: isTrial ? null : badge || null,
          ...icon,
          type,
          traffic_limit_strategy: strategy,
          traffic_limit: parsedTrafficLimit,
          device_limit: parsedDeviceLimit,
          is_trial: isTrial,
          allow_bonus_days: allowBonusDays,
          allow_promocodes: allowPromocodes,
        };
        let created = await createPlan(payload);
        const steps: [() => Promise<Plan>, ParseKeys][] = [];
        if (durationsPayload.length > 0) {
          steps.push([() => setPlanDurations(created.id, durationsPayload), "plans.edit.durationsError"]);
        }
        if (squadsChanged) steps.push([() => updatePlanSquads(created.id, squads), "plans.edit.squadsError"]);
        if (canManageAccess && access.availability !== "ALL") {
          steps.push([() => updatePlanAccess(created.id, planAccessPayload(access)), "plans.edit.accessError"]);
        }
        for (const [step, errorKey] of steps) {
          try {
            created = await step();
          } catch (err) {
            // the plan exists now: another submit would create a second one, so the rest is left to editing
            onSaved(created);
            toast.error(t(errorKey, { error: getErrorMessage(err, t("common.errors.generic")) }));
            close();
            return;
          }
        }
        toast.success(t("plans.edit.saved"));
        onSaved(created);
      } else {
        // separate requests, not atomic: a failed later one leaves the fields saved without it
        let updated = plan;
        if (fieldsKey !== initialFieldsKey) {
          updated = await updatePlan(plan.id, {
            name: name.trim(),
            description: description.trim() || null,
            tag: tag.trim() || null,
            badge: isTrial ? null : badge || null,
            ...icon,
            type,
            traffic_limit_strategy: strategy,
            traffic_limit: parsedTrafficLimit,
            device_limit: parsedDeviceLimit,
            is_trial: isTrial,
            allow_bonus_days: allowBonusDays,
            allow_promocodes: allowPromocodes,
          });
        }
        if (durationsKey(durations) !== durationsKey(initialDurations)) {
          try {
            updated = await setPlanDurations(plan.id, durationsPayload);
          } catch (err) {
            // the fields are already saved: the list shows them, the dialog stays open for another try
            onSaved(updated);
            toast.error(
              t("plans.edit.durationsError", { error: getErrorMessage(err, t("common.errors.generic")) }),
            );
            return;
          }
        }
        if (squadsChanged) {
          try {
            updated = await updatePlanSquads(plan.id, squads);
          } catch (err) {
            onSaved(updated);
            toast.error(t("plans.edit.squadsError", { error: getErrorMessage(err, t("common.errors.generic")) }));
            return;
          }
        }
        toast.success(t("plans.edit.saved"));
        onSaved(updated);
      }
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("plans.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader
        icon={Package}
        title={isCreate ? t("plans.edit.createTitle") : t("plans.edit.editTitle")}
      />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="scroll-fade-y flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3 [--dialog-pad:0.75rem]">
          {plan && (
            <div className={GLASS_DIALOG_CARD_CLASS}>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <Field label={t("plans.edit.publicCodeLabel")} hint={t("plans.edit.publicCodeHint")}>
                  <CopyInput value={plan.public_code} />
                </Field>
                {canShare && <PlanShareLinks planId={plan.id} />}
              </div>
            </div>
          )}

          <fieldset disabled={!canEditFields} className="contents">
          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field label={t("plans.edit.nameLabel")} htmlFor="plan-name" required>
              <Input
                id="plan-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={32}
                end={<PlanIconPicker value={icon} onChange={setIcon} />}
              />
            </Field>
            <Field label={t("plans.edit.descriptionLabel")} htmlFor="plan-description">
              <TextArea
                id="plan-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                maxLength={1024}
                rows={2}
              />
            </Field>
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field label={t("plans.edit.typeLabel")}>
              <div className="grid auto-rows-fr grid-cols-2 gap-2 sm:grid-cols-4">
                {PLAN_TYPES.map((value) => {
                  const Icon = PLAN_TYPE_ICON[value];
                  const isSelected = type === value;
                  return (
                    <Pressable
                      key={value}
                      type="button"
                      onClick={() => setType(value)}
                      className={`flex flex-col items-start gap-2 rounded-[10px] border p-3 text-left transition-colors ${
                        isSelected
                          ? "border-primary/35 bg-primary/15 text-primary"
                          : "border-glass-border bg-white/[0.03] text-foreground hover:bg-white/[0.06]"
                      }`}
                    >
                      <Icon className={`size-4 ${isSelected ? "" : "text-muted-foreground"}`} />
                      <span className="text-[13px] font-medium">{t(`plans.edit.type.${value}`)}</span>
                    </Pressable>
                  );
                })}
              </div>
            </Field>

            {/* the type decides which limit applies; the server zeroes the other */}
            {(hasTraffic || hasDevices) && (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                {hasTraffic && (
                  <LimitField
                    id="plan-traffic"
                    label={t("plans.edit.trafficShortLabel")}
                    suffix={t("plans.edit.trafficSuffix")}
                    value={trafficLimit}
                    onChange={setTrafficLimit}
                  />
                )}
                {hasDevices && (
                  <LimitField
                    id="plan-devices"
                    label={t("plans.edit.deviceShortLabel")}
                    suffix={t("plans.edit.deviceSuffix")}
                    value={deviceLimit}
                    onChange={setDeviceLimit}
                  />
                )}
              </div>
            )}

            {hasTraffic && (
              <Field label={t("plans.edit.strategyLabel")}>
                <div className="flex flex-wrap gap-1.5">
                  {STRATEGIES.map((value) => (
                    <ChoiceChip
                      glass
                      // 36px, the fields' height above
                      className="h-9"
                      key={value}
                      onClick={() => setStrategy(value)}
                      active={strategy === value}
                    >
                      {t(`plans.edit.strategy.${value}`)}
                    </ChoiceChip>
                  ))}
                </div>
              </Field>
            )}
          </div>
          </fieldset>

          {canManageSquads && (
            <div className={GLASS_DIALOG_CARD_CLASS}>
              <PlanSquadsField value={squads} onChange={setSquads} />
            </div>
          )}

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field
              label={t("plans.edit.sections.durations")}
              hint={isTrial ? t("plans.edit.trialDurationHint") : undefined}
            >
              <>
                {durations.length > 0 && (
                  <div className="flex flex-col gap-2">
                    <div className="grid grid-cols-[20px_minmax(0,1fr)_minmax(0,1fr)_36px] gap-2 text-[11px] text-muted-foreground">
                      <span />
                      <span>{t("plans.edit.daysLabel")}</span>
                      <span>{t("plans.edit.basePriceLabel")}</span>
                      <span />
                    </div>
                    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDurationDragEnd}>
                      <SortableContext items={durations.map((row) => row.id)} strategy={verticalListSortingStrategy}>
                        {durations.map((row) => (
                          <DurationRowItem
                            key={row.id}
                            row={row}
                            currencySuffix={currencySuffix}
                            disabled={!canManageDurations}
                            onChange={(patch) => updateDuration(row.id, patch)}
                            onRemove={() => removeDuration(row.id)}
                          />
                        ))}
                      </SortableContext>
                    </DndContext>
                  </div>
                )}
                {canAddDuration && (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="mr-0.5 text-[12px] text-muted-foreground">{t("plans.edit.addPresetLabel")}</span>
                    {presets.map((days) => (
                      <PresetButton key={days} onClick={() => addDuration(String(days))}>
                        {days}
                      </PresetButton>
                    ))}
                    <PresetButton onClick={() => addDuration("")}>{t("plans.edit.customDuration")}</PresetButton>
                  </div>
                )}
              </>
            </Field>
          </div>

          {isCreate && canManageAccess && <PlanAccessFields value={access} onChange={setAccess} isTrial={isTrial} />}

          <fieldset disabled={!canEditFields} className="contents">
          <div className={GLASS_DIALOG_CARD_CLASS}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label={t("plans.edit.badgeLabel")} htmlFor="plan-badge" hint={t("plans.edit.badgeHint")}>
                <SelectDropdown
                  variant="well"
                  size="compact"
                  id="plan-badge"
                  disabled={isTrial}
                  value={badge}
                  onChange={(value) => setBadge(value as PlanBadge | "")}
                  icon={Sparkles}
                  placeholder={badge ? t(`plans.edit.badges.${badge}`) : t("plans.edit.badges.none")}
                  options={[
                    { value: "", label: t("plans.edit.badges.none") },
                    ...PLAN_BADGES.map((value) => ({ value, label: t(`plans.edit.badges.${value}`) })),
                  ]}
                />
              </Field>
              <Field label={t("plans.edit.tagLabel")} htmlFor="plan-tag" hint={t("plans.edit.tagHint")}>
                {/* Remnawave takes only these characters in a user tag */}
                <Input
                  id="plan-tag"
                  value={tag}
                  maxLength={16}
                  mono
                  onChange={(event) => setTag(event.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ""))}
                />
              </Field>
            </div>
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <ToggleRow
              label={t("plans.edit.isTrialLabel")}
              hint={isTrialBlocked ? t("plans.edit.isTrialUnavailableHint") : t("plans.edit.isTrialHint")}
              disabled={isTrialBlocked}
              checked={isTrial}
              onChange={handleTrialChange}
            />
            <ToggleRow
              label={t("plans.edit.allowBonusDaysLabel")}
              hint={t("plans.edit.allowBonusDaysHint")}
              checked={allowBonusDays}
              onChange={setAllowBonusDays}
            />
            <ToggleRow
              label={t("plans.edit.allowPromocodesLabel")}
              hint={t("plans.edit.allowPromocodesHint")}
              checked={allowPromocodes}
              onChange={setAllowPromocodes}
            />
          </div>
          </fieldset>
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-white/[0.08] p-4">
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" isLoading={isSubmitting}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </>
  );
}

function LimitField({
  id,
  label,
  suffix,
  value,
  onChange,
}: {
  id: string;
  label: string;
  suffix: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label} htmlFor={id} required>
      <Input
        id={id}
        type="number"
        onKeyDown={blockNonIntegerKeys}
        min={1}
        step="1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        suffix={suffix}
      />
    </Field>
  );
}

function DurationRowItem({
  row,
  currencySuffix,
  disabled,
  onChange,
  onRemove,
}: {
  row: DurationRow;
  currencySuffix: string | null;
  disabled: boolean;
  onChange: (patch: Partial<DurationRow>) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: row.id,
    disabled,
  });

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`grid grid-cols-[20px_minmax(0,1fr)_minmax(0,1fr)_36px] items-center gap-2 ${isDragging ? "relative z-10" : ""}`}
    >
      <button
        ref={setActivatorNodeRef}
        type="button"
        {...attributes}
        {...listeners}
        disabled={disabled}
        className="flex h-9 cursor-grab touch-none disabled:cursor-not-allowed disabled:opacity-50 items-center justify-center text-muted-foreground transition-colors hover:text-foreground active:cursor-grabbing"
      >
        <GripVertical className="size-3.5" />
      </button>
      <Input
        type="number"
        onKeyDown={blockNonIntegerKeys}
        min={1}
        step="1"
        value={row.days}
        disabled={disabled}
        onChange={(event) => onChange({ days: event.target.value })}
        suffix={t("plans.edit.daysSuffix")}
      />
      <Input
        type="number"
        onKeyDown={blockNonDecimalKeys}
        min={0}
        step="0.01"
        value={row.base_price}
        disabled={disabled}
        onChange={(event) => onChange({ base_price: event.target.value })}
        suffix={currencySuffix}
      />
      <IconButton size="9" tone="danger" disabled={disabled} onClick={onRemove}>
        <Trash2 className="size-4" />
      </IconButton>
    </div>
  );
}

function PresetButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <Button variant="glass" size="sm" onClick={onClick}>
      <Plus className="size-3" />
      {children}
    </Button>
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="min-w-0 flex-1">
        <span className="block text-[13px] font-medium text-foreground">{label}</span>
        <span className={hintClassName}>{hint}</span>
      </span>
      <Switch checked={checked} onChange={onChange} disabled={disabled} />
    </div>
  );
}
