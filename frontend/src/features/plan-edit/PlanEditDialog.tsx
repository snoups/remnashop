import { closestCenter, DndContext, type DragEndEvent, KeyboardSensor, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowDownUp, Columns2, GripVertical, Infinity as InfinityIcon, Layers, Plus, Smartphone, Sparkles, Trash2 } from "lucide-react";
import { type ComponentType, type FormEvent, type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type CreatePlanRequest,
  createPlan,
  type Plan,
  type PlanBadge,
  type PlanType,
  setPlanDurations,
  type TrafficLimitStrategy,
  updatePlan,
} from "@entities/plans/api";
import { usePermissions } from "@entities/user/use-current-user";
import { PlanShareLinks } from "@features/plan-edit/PlanShareLinks";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { blockNonDecimalKeys, blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { randomId } from "@shared/lib/random-string";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { SuffixInput, TextInput, TextArea } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { Field } from "@shared/ui/Field";
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

const labelClassName = "text-sm font-medium text-foreground/80";
const hintClassName = "text-[12px] text-muted-foreground";

export function PlanEditDialog({ plan, anchorCurrency, onClose, onSaved }: PlanEditDialogProps) {
  return (
    <Modal onClose={onClose} size="xl" scrollable>
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
  const close = useModalClose();
  const isCreate = plan === null;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState(plan?.name ?? "");
  const [description, setDescription] = useState(plan?.description ?? "");
  const [tag, setTag] = useState(plan?.tag ?? "");
  const [badge, setBadge] = useState<PlanBadge | "">(plan?.badge ?? "");
  const [type, setType] = useState<PlanType>(plan?.type ?? "BOTH");
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(plan?.traffic_limit_strategy ?? "NO_RESET");
  const [trafficLimit, setTrafficLimit] = useState(String(plan?.traffic_limit ?? 0));
  const [deviceLimit, setDeviceLimit] = useState(String(plan?.device_limit ?? 0));
  const [isTrial, setIsTrial] = useState(plan?.is_trial ?? false);
  const [allowBonusDays, setAllowBonusDays] = useState(plan?.allow_bonus_days ?? true);
  const [allowPromocodes, setAllowPromocodes] = useState(plan?.allow_promocodes ?? true);
  const [isActive, setIsActive] = useState(plan?.is_active ?? true);
  const [initialDurations] = useState<DurationRow[]>(() =>
    (plan?.durations ?? [])
      .slice()
      .sort((a, b) => a.order_index - b.order_index)
      .map((d) => ({ id: randomId(), days: String(d.days), base_price: d.base_price })),
  );
  const [durations, setDurations] = useState(initialDurations);
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
    if (checked) setDurations((rows) => rows.slice(0, 1));
  };
  const currencySuffix = anchorCurrency ? currencySymbol(anchorCurrency) : null;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const parsedTrafficLimit = parseRequiredInt(trafficLimit, 0);
    const parsedDeviceLimit = parseRequiredInt(deviceLimit, 0);
    const parsedDurations = durations.map((row) => ({
      ...row,
      parsedDays: parseRequiredInt(row.days, 1),
    }));
    if (
      parsedTrafficLimit === undefined ||
      parsedDeviceLimit === undefined ||
      (!isCreate && parsedDurations.some((row) => row.parsedDays === undefined))
    ) {
      toast.error(t("errors.invalidNumber"));
      return;
    }

    setIsSubmitting(true);
    try {
      if (isCreate) {
        const payload: CreatePlanRequest = {
          name: name.trim(),
          description: description.trim() || null,
          tag: tag.trim() || null,
          badge: badge || null,
          type,
          traffic_limit_strategy: strategy,
          traffic_limit: parsedTrafficLimit,
          device_limit: parsedDeviceLimit,
          is_trial: isTrial,
          allow_bonus_days: allowBonusDays,
          allow_promocodes: allowPromocodes,
        };
        const created = await createPlan(payload);
        toast.success(t("plans.edit.saved"));
        onSaved(created);
      } else {
        // two requests, not atomic: a failed second one leaves the fields saved without the durations
        let updated = await updatePlan(plan.id, {
          name: name.trim(),
          description: description.trim() || null,
          tag: tag.trim() || null,
          badge: badge || null,
          type,
          traffic_limit_strategy: strategy,
          traffic_limit: parsedTrafficLimit,
          device_limit: parsedDeviceLimit,
          is_active: isActive,
          is_trial: isTrial,
          allow_bonus_days: allowBonusDays,
          allow_promocodes: allowPromocodes,
        });
        if (durationsKey(durations) !== durationsKey(initialDurations)) {
          try {
            updated = await setPlanDurations(
              plan.id,
              parsedDurations.map((row, index) => ({
                days: row.parsedDays!,
                order_index: index,
                base_price: row.base_price,
              })),
            );
          } catch (err) {
            // the fields are already saved: the list shows them, the dialog stays open for another try
            onSaved(updated);
            toast.error(
              t("plans.edit.durationsError", { error: getErrorMessage(err, t("common.errors.generic")) }),
            );
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
        icon={Layers}
        title={isCreate ? t("plans.edit.createTitle") : t("plans.edit.editTitle")}
      />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="scroll-fade-y flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <Card variant="form">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {plan && (
                <Field label={t("plans.edit.publicCodeLabel")} hint={t("plans.edit.publicCodeHint")}>
                  <CopyableValue value={plan.public_code} />
                </Field>
              )}
              {plan && canShare && <PlanShareLinks planId={plan.id} />}
              <Field label={t("plans.edit.nameLabel")} htmlFor="plan-name" required>
                <TextInput
                  id="plan-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </Field>
            </div>
            <Field label={t("plans.edit.descriptionLabel")} htmlFor="plan-description">
              <TextArea
                id="plan-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={2}
              />
            </Field>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label={t("plans.edit.badgeLabel")} htmlFor="plan-badge">
                <SelectDropdown
                  variant="form"
                  id="plan-badge"
                  value={badge}
                  onChange={(value) => setBadge(value as PlanBadge | "")}
                  icon={Sparkles}
                  placeholder={badge ? t(`plans.edit.badges.${badge}`) : t("plans.edit.badges.none")}
                  options={[
                    { value: "", label: t("plans.edit.badges.none") },
                    ...PLAN_BADGES.map((value) => ({ value, label: t(`plans.edit.badges.${value}`) })),
                  ]}
                />
                <span className={hintClassName}>{t("plans.edit.badgeHint")}</span>
              </Field>
              <Field label={t("plans.edit.tagLabel")} htmlFor="plan-tag">
                {/* Remnawave takes only these characters in a user tag */}
                <TextInput
                  id="plan-tag"
                  value={tag}
                  maxLength={16}
                  onChange={(event) => setTag(event.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, ""))}
                />
                <span className={hintClassName}>{t("plans.edit.tagHint")}</span>
              </Field>
            </div>
          </Card>

          <Card variant="form">
            <Field label={t("plans.edit.typeLabel")}>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {PLAN_TYPES.map((value) => {
                  const Icon = PLAN_TYPE_ICON[value];
                  const isSelected = type === value;
                  return (
                    <Pressable
                      key={value}
                      type="button"
                      onClick={() => setType(value)}
                      className={`flex flex-col items-start gap-2 rounded-[14px] border p-3 text-left transition-colors ${
                        isSelected
                          ? "border-primary/50 bg-accent text-primary"
                          : "border-border bg-white/[0.02] text-foreground hover:bg-white/[0.06]"
                      }`}
                    >
                      <Icon className={`size-[18px] ${isSelected ? "" : "text-muted-foreground"}`} />
                      <span className="text-[12.5px] font-semibold">{t(`plans.edit.type.${value}`)}</span>
                    </Pressable>
                  );
                })}
              </div>
            </Field>
          </Card>

          <Card variant="form">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <LimitField
                id="plan-traffic"
                label={t("plans.edit.trafficShortLabel")}
                suffix={t("plans.edit.trafficSuffix")}
                value={trafficLimit}
                onChange={setTrafficLimit}
                hint={t("plans.edit.limitHint")}
              />
              <LimitField
                id="plan-devices"
                label={t("plans.edit.deviceShortLabel")}
                suffix={t("plans.edit.deviceSuffix")}
                value={deviceLimit}
                onChange={setDeviceLimit}
                hint={t("plans.edit.limitHint")}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <span className={labelClassName}>{t("plans.edit.strategyLabel")}</span>
              <div className="flex flex-wrap gap-1.5">
                {STRATEGIES.map((value) => (
                  <ChoiceChip
                    key={value}
                    onClick={() => setStrategy(value)}
                    active={strategy === value}
                  >
                    {t(`plans.edit.strategy.${value}`)}
                  </ChoiceChip>
                ))}
              </div>
            </div>
          </Card>

          <Card variant="form">
            <Field
              label={t("plans.edit.sections.durations")}
              hint={isTrial ? t("plans.edit.trialDurationHint") : t("plans.edit.durationsHint")}
            >
              {isCreate ? (
                <p className="text-[12.5px] text-muted-foreground">{t("plans.edit.durationsAfterCreate")}</p>
              ) : (
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
              )}
            </Field>
          </Card>

          <Card variant="form">
            {!isCreate && (
              <ToggleRow
                label={t("plans.edit.isActiveLabel")}
                hint={t("plans.edit.isActiveHint")}
                checked={isActive}
                onChange={setIsActive}
              />
            )}
            <ToggleRow
              label={t("plans.edit.isTrialLabel")}
              hint={t("plans.edit.isTrialHint")}
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
          </Card>
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-white/[0.08] px-5 py-3.5">
          <Button
            variant="outline"
            type="button"
            onClick={close}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant="accent"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? t("common.saving") : t("common.save")}
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
  hint,
}: {
  id: string;
  label: string;
  suffix: string;
  value: string;
  onChange: (value: string) => void;
  hint: string;
}) {
  return (
    <Field label={label} htmlFor={id}>
      <SuffixInput
        id={id}
        type="number"
        onKeyDown={blockNonIntegerKeys}
        min={0}
        step="1"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        suffix={suffix}
      />
      <span className={hintClassName}>{hint}</span>
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
      <SuffixInput
        type="number"
        onKeyDown={blockNonIntegerKeys}
        min={1}
        step="1"
        value={row.days}
        disabled={disabled}
        onChange={(event) => onChange({ days: event.target.value })}
        suffix={t("plans.edit.daysSuffix")}
      />
      <SuffixInput
        type="number"
        onKeyDown={blockNonDecimalKeys}
        min={0}
        step="0.01"
        value={row.base_price}
        disabled={disabled}
        onChange={(event) => onChange({ base_price: event.target.value })}
        suffix={currencySuffix}
      />
      <IconButton size="9.5" tone="danger" disabled={disabled} onClick={onRemove}>
        <Trash2 className="size-4" />
      </IconButton>
    </div>
  );
}

function PresetButton({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <Button
      variant="outline"
      size="sm"
      onClick={onClick}
    >
      <Plus className="size-3" />
      {children}
    </Button>
  );
}

function ToggleRow({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <div className="flex items-center gap-3 rounded-[14px] border border-border bg-white/[0.02] px-3 py-2.5">
      <span className="min-w-0 flex-1">
        <span className="block text-[13px] font-semibold text-foreground">{label}</span>
        <span className={hintClassName}>{hint}</span>
      </span>
      <Switch checked={checked} onChange={onChange} />
    </div>
  );
}
