import { Filter, Wand2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  adjustBasePrices,
  previewPricingChange,
  type AdjustBasePricesBody,
  type BulkAdjustScope,
  type Currency,
  type PinnedPriceAction,
  type PriceAdjustMode,
  type PriceBookRow,
  type PricingDiff,
} from "@entities/pricing/api";
import { PricingDiffList } from "@entities/pricing/PricingDiffList";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { blockNonDecimalKeys } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { Button } from "@shared/ui/Button";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { GLASS_DIALOG_BODY_CLASS, GLASS_DIALOG_CARD_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const BULK_SCOPES = ["ALL_PLANS", "ALL_ADDONS"] as const satisfies BulkAdjustScope[];
const MODES: PriceAdjustMode[] = ["MULTIPLY", "SET", "LADDER"];
const PINNED_ACTIONS: PinnedPriceAction[] = ["KEEP", "SCALE", "RESET"];
// the ladder's base when the selection has a 30-day duration
const PREFERRED_LADDER_BASE_DAYS = 30;
// the backend's bound on a negative discount
const MAX_MARKUP = 1000;

// "ALL_PLANS", "ALL_ADDONS" or one plan's id: a plan is adjusted as its own durations
type BulkTarget = (typeof BULK_SCOPES)[number] | number;

interface BulkForm {
  target: BulkTarget;
  mode: PriceAdjustMode;
  percent: string;
  price: string;
  /** null = the default for the selection */
  ladderBaseDays: number | null;
  /** percent off by duration in days; negative is a markup */
  ladder: Record<number, string>;
  pinned: PinnedPriceAction;
}

const INITIAL_FORM: BulkForm = { target: "ALL_PLANS", mode: "MULTIPLY", percent: "", price: "", ladderBaseDays: null, ladder: {}, pinned: "KEEP" };

function isValidPercent(value: string): boolean {
  return value.trim() !== "" && Number(value) > -100;
}

function isValidDiscount(value: string | undefined): boolean {
  return value === undefined || value.trim() === "" || (Number(value) >= -MAX_MARKUP && Number(value) < 100);
}

function isFormValid(form: BulkForm): boolean {
  if (form.mode === "MULTIPLY") return isValidPercent(form.percent);
  const priceOk = form.price.trim() !== "" && Number(form.price) > 0;
  return priceOk && (form.mode !== "LADDER" || Object.values(form.ladder).every(isValidDiscount));
}

function targetRows(form: BulkForm, planGroups: PriceBookRow[][]): PriceBookRow[][] {
  return typeof form.target === "number" ? planGroups.filter((rows) => rows[0].plan_id === form.target) : planGroups;
}

function ladderDurations(form: BulkForm, planGroups: PriceBookRow[][]): number[] {
  return [...new Set(targetRows(form, planGroups).flat().map((row) => row.days))]
    // an unlimited duration has no days to price by, the backend leaves it out too
    .filter((days): days is number => days !== null && days > 0)
    .sort((a, b) => a - b);
}

function ladderBase(form: BulkForm, durations: number[]): number {
  if (form.ladderBaseDays !== null && durations.includes(form.ladderBaseDays)) return form.ladderBaseDays;
  return durations.includes(PREFERRED_LADDER_BASE_DAYS) ? PREFERRED_LADDER_BASE_DAYS : (durations[0] ?? PREFERRED_LADDER_BASE_DAYS);
}

function buildBody(form: BulkForm, planGroups: PriceBookRow[][]): AdjustBasePricesBody {
  const scope =
    typeof form.target === "number"
      ? {
          scope: "SELECTED" as const,
          plan_duration_ids: (planGroups.find((rows) => rows[0].plan_id === form.target) ?? []).map((row) => row.ref_id),
          addon_ids: [],
        }
      : { scope: form.target, plan_duration_ids: [], addon_ids: [] };
  if (form.mode === "MULTIPLY") {
    return { ...scope, mode: "MULTIPLY", factor: ((100 + Number(form.percent)) / 100).toFixed(6), pinned: form.pinned };
  }
  if (form.mode === "SET") return { ...scope, mode: "SET", price: form.price, pinned: form.pinned };
  const baseDays = ladderBase(form, ladderDurations(form, planGroups));
  return {
    ...scope,
    mode: "LADDER",
    price: form.price,
    ladder_base_days: baseDays,
    ladder_discounts: Object.fromEntries(
      Object.entries(form.ladder).filter(([days, value]) => value.trim() !== "" && Number(days) !== baseDays),
    ),
    pinned: form.pinned,
  };
}

export function BulkAdjustButton({
  planGroups,
  anchorCurrency,
  onChanged,
}: {
  planGroups: PriceBookRow[][];
  anchorCurrency: Currency;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const [step, setStep] = useState<"closed" | "form" | "confirm">("closed");
  const [form, setForm] = useState<BulkForm>(INITIAL_FORM);
  const [diff, setDiff] = useState<PricingDiff | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handlePreview = async () => {
    setIsLoading(true);
    try {
      setDiff(await previewPricingChange({ adjust: buildBody(form, planGroups) }));
      setStep("confirm");
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.matrix.previewError")));
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async () => {
    // closed first: a percent applies to current prices, a second click would apply it twice
    setStep("closed");
    setDiff(null);
    try {
      await adjustBasePrices(buildBody(form, planGroups));
      toast.success(t("pricing.matrix.applied"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.matrix.applyError")));
    }
  };

  return (
    <>
      <Button variant="glass" icon={Wand2} onClick={() => setStep("form")}>
        {t("pricing.matrix.bulkAdjust")}
      </Button>

      {step === "form" && (
        <Modal onClose={() => setStep("closed")} size="lg" scrollable>
          <BulkAdjustFormBody
            form={form}
            planGroups={planGroups}
            anchorCurrency={anchorCurrency}
            isLoading={isLoading}
            onChange={setForm}
            onSubmit={() => void handlePreview()}
          />
        </Modal>
      )}

      {step === "confirm" && diff && (
        <ConfirmDialog
          title={t("pricing.matrix.confirmTitle")}
          icon={Wand2}
          size="md"
          message={t("pricing.matrix.confirmMessage", { count: diff.affected_count })}
          confirmLabel={t("pricing.matrix.apply")}
          cancelLabel={t("common.cancel")}
          onConfirm={() => void handleConfirm()}
          onCancel={() => {
            setStep("closed");
            setDiff(null);
          }}
        >
          <PricingDiffList diff={diff} />
        </ConfirmDialog>
      )}
    </>
  );
}

interface BulkAdjustFormBodyProps {
  form: BulkForm;
  planGroups: PriceBookRow[][];
  anchorCurrency: Currency;
  isLoading: boolean;
  onChange: (form: BulkForm) => void;
  onSubmit: () => void;
}

function BulkAdjustFormBody({ form, planGroups, anchorCurrency, isLoading, onChange, onSubmit }: BulkAdjustFormBodyProps) {
  const { t } = useTranslation();
  const close = useModalClose();
  const update = (patch: Partial<BulkForm>) => onChange({ ...form, ...patch });
  const isValid = isFormValid(form);
  const currency = currencySymbol(anchorCurrency);

  const targets = [
    ...BULK_SCOPES.map((option) => ({ value: option, label: t(`pricing.matrix.scope.${option}`) })),
    ...planGroups.map((rows) => ({ value: String(rows[0].plan_id), label: rows[0].name })),
  ];
  // a ladder prices durations, which add-ons don't have
  const modes = form.target === "ALL_ADDONS" ? MODES.filter((mode) => mode !== "LADDER") : MODES;
  const durations = ladderDurations(form, planGroups);
  const baseDays = ladderBase(form, durations);
  const ladderDays = durations.filter((days) => days !== baseDays);

  const ladderPrice = (days: number): string | null => {
    const price = Number(form.price);
    const discount = Number(form.ladder[days] || 0);
    if (!(price > 0) || !isValidDiscount(form.ladder[days])) return null;
    return ((price * days) / baseDays * (100 - discount) / 100).toFixed(2);
  };

  return (
    <>
      <DialogHeader icon={Wand2} title={t("pricing.matrix.bulkAdjustTitle")} />

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (isValid) onSubmit();
        }}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className={`${GLASS_DIALOG_BODY_CLASS} flex flex-col gap-3`}>
          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field label={t("pricing.matrix.scopeLabel")} htmlFor="pricing-bulk-scope">
              <SelectDropdown
                variant="well"
                size="compact"
                id="pricing-bulk-scope"
                value={String(form.target)}
                onChange={(value) => {
                  const target = BULK_SCOPES.find((option) => option === value) ?? Number(value);
                  update({ target, mode: target === "ALL_ADDONS" && form.mode === "LADDER" ? "MULTIPLY" : form.mode });
                }}
                icon={Filter}
                placeholder={targets.find((option) => option.value === String(form.target))?.label ?? ""}
                options={targets}
              />
            </Field>
            <Field label={t("pricing.matrix.modeLabel")}>
              <div className="flex flex-wrap gap-1.5">
                {modes.map((mode) => (
                  <ChoiceChip className="h-9" key={mode} active={form.mode === mode} onClick={() => update({ mode })}>
                    {t(`pricing.matrix.mode.${mode}`)}
                  </ChoiceChip>
                ))}
              </div>
            </Field>
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            {form.mode === "MULTIPLY" ? (
              <Field
                label={t("pricing.matrix.percentLabel")}
                htmlFor="pricing-bulk-percent"
                required
                hint={t("pricing.matrix.percentHint")}
                error={form.percent.trim() !== "" && !isValidPercent(form.percent) ? t("pricing.matrix.percentInvalid") : undefined}
              >
                <Input
                  id="pricing-bulk-percent"
                  type="number"
                  step="any"
                  placeholder={t("pricing.matrix.bulkPercentPlaceholder")}
                  value={form.percent}
                  onChange={(event) => update({ percent: event.target.value })}
                  aria-invalid={form.percent.trim() !== "" && !isValidPercent(form.percent)}
                  suffix="%"
                />
              </Field>
            ) : (
              <Field
                label={
                  form.mode === "LADDER"
                    ? t("pricing.matrix.ladderPriceLabel", { duration: t("plans.daysShort", { count: baseDays }) })
                    : t("pricing.matrix.priceLabel")
                }
                htmlFor="pricing-bulk-price"
                required
                hint={form.mode === "LADDER" ? t("pricing.matrix.ladderHint") : undefined}
              >
                <Input
                  id="pricing-bulk-price"
                  type="number"
                  onKeyDown={blockNonDecimalKeys}
                  step="0.01"
                  min="0"
                  value={form.price}
                  onChange={(event) => update({ price: event.target.value })}
                  suffix={currency}
                />
              </Field>
            )}

            {form.mode === "LADDER" && durations.length > 1 && (
              <Field label={t("pricing.matrix.ladderBaseLabel")}>
                <div className="flex flex-wrap gap-1.5">
                  {durations.map((days) => (
                    <ChoiceChip
                      className="h-9"
                      key={days}
                      active={baseDays === days}
                      onClick={() => update({ ladderBaseDays: days })}
                    >
                      {t("plans.daysShort", { count: days })}
                    </ChoiceChip>
                  ))}
                </div>
              </Field>
            )}

            {form.mode === "LADDER" && ladderDays.length > 0 && (
              <Field label={t("pricing.matrix.ladderDiscountLabel")} hint={t("pricing.matrix.ladderDiscountHint")}>
                <div className="flex flex-col gap-2">
                  {ladderDays.map((days) => {
                    const price = ladderPrice(days);
                    return (
                      <div key={days} className="grid grid-cols-[72px_minmax(0,1fr)_96px] items-center gap-2">
                        <span className="text-sm text-foreground">{t("plans.daysShort", { count: days })}</span>
                        <Input
                          type="number"
                          step="any"
                          min={-MAX_MARKUP}
                          max="99.99"
                          placeholder={t("pricing.matrix.markupPlaceholder")}
                          value={form.ladder[days] ?? ""}
                          onChange={(event) => update({ ladder: { ...form.ladder, [days]: event.target.value } })}
                          aria-invalid={!isValidDiscount(form.ladder[days])}
                          suffix="%"
                        />
                        <span className="text-right text-xs tabular-nums text-muted-foreground">
                          {price === null ? "" : `${price} ${currency}`}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </Field>
            )}
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field label={t("pricing.matrix.pinnedLabel")} hint={t(`pricing.matrix.pinnedHint.${form.pinned}`)}>
              <div className="flex flex-wrap gap-1.5">
                {PINNED_ACTIONS.map((pinned) => (
                  <ChoiceChip className="h-9" key={pinned} active={form.pinned === pinned} onClick={() => update({ pinned })}>
                    {t(`pricing.matrix.pinned.${pinned}`)}
                  </ChoiceChip>
                ))}
              </div>
            </Field>
          </div>
        </div>
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
          <Button variant="glass" type="button" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" isLoading={isLoading} disabled={!isValid}>
            {isLoading ? t("pricing.matrix.previewing") : t("pricing.matrix.preview")}
          </Button>
        </div>
      </form>
    </>
  );
}
