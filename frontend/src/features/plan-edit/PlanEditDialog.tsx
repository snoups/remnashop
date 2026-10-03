import { closestCenter, DndContext, type DragEndEvent, KeyboardSensor, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowDownUp, Columns2, GripVertical, Infinity as InfinityIcon, Layers, Plus, Smartphone, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { type ComponentType, type FormEvent, type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type CreatePlanRequest,
  createPlan,
  type Plan,
  type PlanType,
  setPlanDurations,
  type TrafficLimitStrategy,
  updatePlan,
} from "@entities/plans/api";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { bounceTap } from "@shared/lib/bounceState";
import { blockNonDecimalKeys, blockNonIntegerKeys, parseRequiredInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Switch } from "@shared/ui/Switch";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { SuffixInput, TextInput, TextArea } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { Field } from "@shared/ui/Field";
import { IconButton } from "@shared/ui/IconButton";
import { ChoiceChip } from "@shared/ui/ChoiceChip";

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
  const close = useModalClose();
  const isCreate = plan === null;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState(plan?.name ?? "");
  const [description, setDescription] = useState(plan?.description ?? "");
  const [tag, setTag] = useState(plan?.tag ?? "");
  const [type, setType] = useState<PlanType>(plan?.type ?? "BOTH");
  const [strategy, setStrategy] = useState<TrafficLimitStrategy>(plan?.traffic_limit_strategy ?? "NO_RESET");
  const [trafficLimit, setTrafficLimit] = useState(String(plan?.traffic_limit ?? 0));
  const [deviceLimit, setDeviceLimit] = useState(String(plan?.device_limit ?? 0));
  const [isTrial, setIsTrial] = useState(plan?.is_trial ?? false);
  const [isActive, setIsActive] = useState(plan?.is_active ?? true);
  const [durations, setDurations] = useState<DurationRow[]>(
    (plan?.durations ?? [])
      .slice()
      .sort((a, b) => a.order_index - b.order_index)
      .map((d) => ({ id: crypto.randomUUID(), days: String(d.days), base_price: d.base_price })),
  );
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const addDuration = (days: string) =>
    setDurations((rows) => [...rows, { id: crypto.randomUUID(), days, base_price: "0" }]);
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
  const presets = DURATION_PRESETS.filter((days) => !usedDays.has(days));
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
          type,
          traffic_limit_strategy: strategy,
          traffic_limit: parsedTrafficLimit,
          device_limit: parsedDeviceLimit,
          is_trial: isTrial,
        };
        const created = await createPlan(payload);
        toast.success(t("plans.edit.saved"));
        onSaved(created);
      } else {
        // two PUTs, not atomic: a failed second one leaves the fields saved without the durations
        let updated = await updatePlan(plan.id, {
          name: name.trim(),
          description: description.trim() || null,
          tag: tag.trim() || null,
          type,
          traffic_limit_strategy: strategy,
          traffic_limit: parsedTrafficLimit,
          device_limit: parsedDeviceLimit,
          is_active: isActive,
          is_trial: isTrial,
        });
        updated = await setPlanDurations(
          plan.id,
          parsedDurations.map((row, index) => ({
            days: row.parsedDays!,
            order_index: index,
            base_price: row.base_price,
          })),
        );
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
            <Field label={t("plans.edit.tagLabel")} htmlFor="plan-tag">
              <TextInput id="plan-tag" value={tag} onChange={(event) => setTag(event.target.value)}  />
              <span className={hintClassName}>{t("plans.edit.tagHint")}</span>
            </Field>
          </Card>

          <Card variant="form">
            <Field label={t("plans.edit.typeLabel")}>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {PLAN_TYPES.map((value) => {
                  const Icon = PLAN_TYPE_ICON[value];
                  const isSelected = type === value;
                  return (
                    <motion.button
                      key={value}
                      type="button"
                      onClick={() => setType(value)}
                      {...bounceTap(0.03)}
                      className={`flex flex-col items-start gap-2 rounded-[14px] border p-3 text-left transition-colors ${
                        isSelected
                          ? "border-primary/50 bg-accent text-primary"
                          : "border-border bg-white/[0.02] text-foreground hover:bg-white/[0.05]"
                      }`}
                    >
                      <Icon className={`size-[18px] ${isSelected ? "" : "text-muted-foreground"}`} />
                      <span className="text-[12.5px] font-semibold">{t(`plans.edit.type.${value}`)}</span>
                    </motion.button>
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
            <Field label={t("plans.edit.sections.durations")} hint={t("plans.edit.durationsHint")}>
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
                              onChange={(patch) => updateDuration(row.id, patch)}
                              onRemove={() => removeDuration(row.id)}
                            />
                          ))}
                        </SortableContext>
                      </DndContext>
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="mr-0.5 text-[12px] text-muted-foreground">{t("plans.edit.addPresetLabel")}</span>
                    {presets.map((days) => (
                      <PresetButton key={days} onClick={() => addDuration(String(days))}>
                        {days}
                      </PresetButton>
                    ))}
                    <PresetButton onClick={() => addDuration("")}>{t("plans.edit.customDuration")}</PresetButton>
                  </div>
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
              onChange={setIsTrial}
            />
          </Card>
        </div>

        <div className="flex shrink-0 items-center justify-end gap-2 border-t border-white/[0.07] px-5 py-3.5">
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
  onChange,
  onRemove,
}: {
  row: DurationRow;
  currencySuffix: string | null;
  onChange: (patch: Partial<DurationRow>) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id: row.id,
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
        className="flex h-9 cursor-grab touch-none items-center justify-center text-muted-foreground transition-colors hover:text-foreground active:cursor-grabbing"
      >
        <GripVertical className="size-3.5" />
      </button>
      <SuffixInput
        type="number"
        onKeyDown={blockNonIntegerKeys}
        min={1}
        step="1"
        value={row.days}
        onChange={(event) => onChange({ days: event.target.value })}
        suffix={t("plans.edit.daysSuffix")}
      />
      <SuffixInput
        type="number"
        onKeyDown={blockNonDecimalKeys}
        min={0}
        step="0.01"
        value={row.base_price}
        onChange={(event) => onChange({ base_price: event.target.value })}
        suffix={currencySuffix}
      />
      <IconButton size="9.5" tone="danger"
        onClick={onRemove}
      >
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
        <span className="block text-[13.5px] font-semibold text-foreground">{label}</span>
        <span className={hintClassName}>{hint}</span>
      </span>
      <Switch checked={checked} onChange={onChange} />
    </div>
  );
}
