import { Filter, Pin, PinOff, Table2, Wand2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  adjustBasePrices,
  previewPricingChange,
  pricingRowLabel,
  setAddonBasePrice,
  setAddonOverride,
  setPlanDurationBasePrice,
  setPlanDurationOverride,
  type BulkAdjustScope,
  type Currency,
  type PriceBook,
  type PriceBookRow,
  type PricingDiff,
} from "@entities/pricing/api";
import { PricingDiffList } from "@entities/pricing/PricingDiffList";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { blockNonDecimalKeys } from "@shared/lib/number-input";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { COLLAPSE_MOTION } from "@shared/ui/collapse-motion";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/EmptyState";
import { FieldHint } from "@shared/ui/FieldHint";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";
import { Button } from "@shared/ui/Button";
import { IconButton } from "@shared/ui/IconButton";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { CardHeader } from "@shared/ui/CardHeader";
import { EYEBROW_CLASS } from "@shared/ui/classes";

const CURRENCIES: Currency[] = ["USD", "XTR", "RUB"];
const BULK_SCOPES: BulkAdjustScope[] = ["ALL_PLANS", "ALL_ADDONS"];

const cellInputClassName =
  "w-24 rounded-full border px-3 py-2 text-right text-sm tabular-nums outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-50";

interface PricingMatrixProps {
  book: PriceBook;
  onChanged: () => void;
}

export function PricingMatrix({ book, onChanged }: PricingMatrixProps) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  // the dialog previews the change before applying it
  const canBulkAdjust =
    permissions.includes("PRICING_BASE_ADJUST_MANAGE") && permissions.includes("PRICING_PREVIEW_VIEW");

  const saveOverride = async (row: PriceBookRow, currency: Currency, price: string | null) => {
    try {
      if (row.kind === "addon") {
        await setAddonOverride(row.ref_id, currency, price);
      } else if (row.plan_id !== null && row.days !== null) {
        await setPlanDurationOverride(row.plan_id, row.days, currency, price);
      } else {
        toast.error(t("pricing.matrix.planNotFound"));
        return;
      }
      toast.success(t("pricing.matrix.saved"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.matrix.saveError")));
    }
  };

  const saveBasePrice = async (row: PriceBookRow, newBasePrice: string) => {
    try {
      if (row.kind === "addon") {
        await setAddonBasePrice(row.ref_id, newBasePrice);
      } else if (row.plan_id !== null && row.days !== null) {
        await setPlanDurationBasePrice(row.plan_id, row.days, newBasePrice);
      } else {
        toast.error(t("pricing.matrix.planNotFound"));
        return;
      }
      toast.success(t("pricing.matrix.saved"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.matrix.saveError")));
    }
  };

  const [collapsedSections, setCollapsedSections] = useState<ReadonlySet<Section>>(new Set());
  const toggleSection = (section: Section) =>
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (!next.delete(section)) next.add(section);
      return next;
    });

  const rows: { row: PriceBookRow }[] = [
    ...book.plans.map((row) => ({ row })),
    ...book.addons.map((row) => ({ row })),
  ];

  return (
    <Card>
      <CardHeader
        icon={Table2}
        title={
          <>
            {t("pricing.matrix.title")}
            <FieldHint text={t("pricing.matrix.titleHint")} side="bottom" />
          </>
        }
        description={t("pricing.matrix.description")}
        aside={canBulkAdjust && <BulkAdjustButton onChanged={onChanged} />}
      />

      {rows.length === 0 ? (
        <EmptyState text={t("pricing.matrix.empty")} />
      ) : (
        <div className="mt-4 overflow-x-auto">
          {/* separate borders: collapsed tables ignore border-radius on cells */}
          <table className="w-full border-separate border-spacing-0 text-sm">
            <thead>
              <tr className={`text-left ${EYEBROW_CLASS} [&>th]:border-b [&>th]:border-border [&>th]:p-2 [&>th:first-child]:pl-3 [&>th:last-child]:pr-3`}>
                <th>{t("pricing.matrix.item")}</th>
                <th>{t("pricing.matrix.basePrice")}</th>
                {CURRENCIES.map((currency) => (
                  <th key={currency}>
                    <span className="inline-flex items-center gap-1.5">
                      {currency}
                      {currency === book.settings.anchor_currency && (
                        <span className="rounded-full bg-accent px-1.5 py-px text-[10px] tracking-wide text-primary">
                          {t("pricing.anchor.badge")}
                        </span>
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {book.plans.length > 0 && (
                <SectionHeader
                  label={t("pricing.matrix.plansSection")}
                  count={book.plans.length}
                  isCollapsed={collapsedSections.has("plans")}
                  onToggle={() => toggleSection("plans")}
                />
              )}
              <AnimatePresence initial={false}>
                {!collapsedSections.has("plans") &&
                  book.plans.map((row, index) => (
                    <MatrixRow
                      key={`plan_duration-${row.ref_id}`}
                      row={row}
                      isLast={index === book.plans.length - 1}
                      anchorCurrency={book.settings.anchor_currency}
                      onSaveOverride={saveOverride}
                      onSaveBasePrice={saveBasePrice}
                    />
                  ))}
              </AnimatePresence>
              {book.addons.length > 0 && (
                <SectionHeader
                  label={t("pricing.matrix.addonsSection")}
                  count={book.addons.length}
                  isCollapsed={collapsedSections.has("addons")}
                  onToggle={() => toggleSection("addons")}
                />
              )}
              <AnimatePresence initial={false}>
                {!collapsedSections.has("addons") &&
                  book.addons.map((row, index) => (
                    <MatrixRow
                      key={`addon-${row.ref_id}`}
                      row={row}
                      isLast={index === book.addons.length - 1}
                      anchorCurrency={book.settings.anchor_currency}
                      onSaveOverride={saveOverride}
                      onSaveBasePrice={saveBasePrice}
                    />
                  ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

type Section = "plans" | "addons";

function SectionHeader({
  label,
  count,
  isCollapsed,
  onToggle,
}: {
  label: string;
  count: number;
  isCollapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <tr>
      <td colSpan={2 + CURRENCIES.length} className="pb-1 pt-3">
        <GroupToggle open={!isCollapsed} onToggle={onToggle} label={label} count={count} />
      </td>
    </tr>
  );
}

// Row height can't animate on a <tr>, so each cell's content collapses instead;
// the vertical padding lives inside it so the row shrinks to nothing.
function Cell({ className, children }: { className?: string; children?: ReactNode }) {
  return (
    <td className={className}>
      <motion.div {...COLLAPSE_MOTION} className="py-[9px]">
        {children}
      </motion.div>
    </td>
  );
}

function MatrixRow({
  row,
  isLast,
  anchorCurrency,
  onSaveOverride,
  onSaveBasePrice,
}: {
  row: PriceBookRow;
  isLast: boolean;
  anchorCurrency: Currency;
  onSaveOverride: (row: PriceBookRow, currency: Currency, price: string | null) => void;
  onSaveBasePrice: (row: PriceBookRow, newBasePrice: string) => void;
}) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const isAddon = row.kind === "addon";
  const canEditBase = permissions.includes(isAddon ? "ADDONS_PRICES_MANAGE" : "PLANS_DURATION_BASE_PRICE_MANAGE");
  const canOverride = permissions.includes(isAddon ? "ADDONS_PRICE_OVERRIDE_MANAGE" : "PLANS_PRICE_OVERRIDE_MANAGE");
  return (
    <tr
      // border on every row but the section's last, same as divide-y (which borders the bottom)
      className={`[&>td]:border-border/50 [&>td]:px-2 [&>td:first-child]:pl-3 [&>td:last-child]:pr-3 [&>td]:transition-colors hover:[&>td]:bg-white/[0.04] [&>td:first-child]:rounded-l-full [&>td:last-child]:rounded-r-full ${
        isLast ? "" : "[&>td]:border-b"
      }`}
    >
      <Cell className="text-[13px] font-medium text-foreground">{pricingRowLabel(row, t)}</Cell>
      <Cell>
        <input
          key={row.base_price}
          type="number"
          onKeyDown={blockNonDecimalKeys}
          step="0.01"
          min="0"
          defaultValue={row.base_price}
          onBlur={(event) => {
            if (event.target.value === "" || event.target.value === row.base_price) return;
            onSaveBasePrice(row, event.target.value);
          }}
          disabled={!canEditBase}
          className={`${cellInputClassName} border-border bg-input/60`}
        />
      </Cell>
      {CURRENCIES.map((currency) => {
        const cell = row.cells.find((c) => c.currency === currency);
        if (!cell) return <Cell key={currency} />;
        if (currency === anchorCurrency) {
          return (
            <Cell key={currency}>
              <div className="flex items-center gap-1">
                <input
                  type="number"
                  value={cell.amount}
                  disabled
                  className={`${cellInputClassName} cursor-not-allowed border-border bg-input/60 text-foreground opacity-50`}
                />
                {/* pin-sized gap, so the anchor column lines up with the others */}
                <span className="size-6 shrink-0" />
              </div>
            </Cell>
          );
        }
        return (
          <Cell key={currency}>
            <div className="flex items-center gap-1">
              <input
                key={cell.amount}
                type="number"
                onKeyDown={blockNonDecimalKeys}
                step="0.01"
                min="0"
                defaultValue={cell.amount}
                onBlur={(event) => {
                  if (event.target.value === "" || event.target.value === cell.amount) return;
                  onSaveOverride(row, currency, event.target.value);
                }}
                disabled={!canOverride}
                className={`${cellInputClassName} ${
                  cell.is_pinned
                    ? "border-primary/40 bg-accent font-semibold text-primary"
                    : "border-border bg-input/60 text-foreground"
                }`}
              />
              {cell.is_pinned ? (
                <IconButton
                  size="6"
                  onClick={() => onSaveOverride(row, currency, null)}
                  disabled={!canOverride}
                >
                  <Pin className="size-4 text-primary" />
                </IconButton>
              ) : (
                <IconButton
                  size="6"
                  onClick={() => onSaveOverride(row, currency, cell.amount)}
                  disabled={!canOverride}
                >
                  <PinOff className="size-4" />
                </IconButton>
              )}
            </div>
          </Cell>
        );
      })}
    </tr>
  );
}

function BulkAdjustButton({ onChanged }: { onChanged: () => void }) {
  const { t } = useTranslation();
  const [step, setStep] = useState<"closed" | "form" | "confirm">("closed");
  const [scope, setScope] = useState<BulkAdjustScope>("ALL_PLANS");
  const [factor, setFactor] = useState("1.00");
  const [diff, setDiff] = useState<PricingDiff | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const buildBody = () => ({
    scope,
    factor,
    plan_duration_ids: [],
    addon_ids: [],
  });

  const handlePreview = async () => {
    setIsLoading(true);
    try {
      const preview = await previewPricingChange({ adjust: buildBody() });
      setDiff(preview);
      setStep("confirm");
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.matrix.previewError")));
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async () => {
    // closed first: the factor multiplies current prices, a second click would apply it twice
    setStep("closed");
    setDiff(null);
    try {
      await adjustBasePrices(buildBody());
      toast.success(t("pricing.matrix.applied"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.matrix.applyError")));
    }
  };

  return (
    <>
      <Button
        variant="secondary"
        onClick={() => setStep("form")}
      >
        <Wand2 className="size-4" />
        {t("pricing.matrix.bulkAdjust")}
      </Button>

      {step === "form" && (
        <Modal onClose={() => setStep("closed")} size="sm">
          <BulkAdjustFormBody
            scope={scope}
            factor={factor}
            isLoading={isLoading}
            onScopeChange={setScope}
            onFactorChange={setFactor}
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
  scope: BulkAdjustScope;
  factor: string;
  isLoading: boolean;
  onScopeChange: (scope: BulkAdjustScope) => void;
  onFactorChange: (factor: string) => void;
  onSubmit: () => void;
}

function BulkAdjustFormBody({ scope, factor, isLoading, onScopeChange, onFactorChange, onSubmit }: BulkAdjustFormBodyProps) {
  const { t } = useTranslation();
  const close = useModalClose();
  // the backend rejects <= 0 too (factor: gt=0); 0 would zero every price
  const isFactorValid = factor.trim() !== "" && Number(factor) > 0;

  return (
    <>
      <DialogHeader icon={Wand2} title={t("pricing.matrix.bulkAdjustTitle")} />

      <form
        onSubmit={(event) => {
          event.preventDefault();
          if (isFactorValid) onSubmit();
        }}
        className="flex min-h-0 flex-1 flex-col"
      >
        <div className="flex flex-col gap-3 p-4">
          <Card variant="form">
            <Field label={t("pricing.matrix.scopeLabel")} htmlFor="pricing-bulk-scope">
              <SelectDropdown
                variant="form"
                id="pricing-bulk-scope"
                value={scope}
                onChange={(value) => onScopeChange(value as BulkAdjustScope)}
                icon={Filter}
                placeholder={t(`pricing.matrix.scope.${scope}`)}
                options={BULK_SCOPES.map((option) => ({
                  value: option,
                  label: t(`pricing.matrix.scope.${option}`),
                }))}
              />
            </Field>
            <Field
              label={t("pricing.matrix.factorLabel")}
              htmlFor="pricing-bulk-factor"
              required
              hint={t("pricing.matrix.factorHint")}
              error={factor.trim() !== "" && !isFactorValid ? t("pricing.matrix.factorPositive") : undefined}
            >
              <TextInput
                id="pricing-bulk-factor"
                type="number"
                onKeyDown={blockNonDecimalKeys}
                step="any"
                min="0"
                required
                placeholder={t("pricing.matrix.factorPlaceholder")}
                value={factor}
                onChange={(event) => onFactorChange(event.target.value)}
                aria-invalid={factor.trim() !== "" && !isFactorValid}
              />
            </Field>
          </Card>
          <div className="flex justify-end gap-2">
            <Button variant="outline" type="button" onClick={close}>
              {t("common.cancel")}
            </Button>
            <Button variant="accent" type="submit" disabled={isLoading || !isFactorValid}>
              {isLoading ? t("pricing.matrix.previewing") : t("pricing.matrix.preview")}
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}
