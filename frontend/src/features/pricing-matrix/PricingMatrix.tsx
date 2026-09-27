import { Filter, Inbox, Pin, PinOff, Table2, Wand2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  adjustBasePrices,
  previewPricingChange,
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
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const CURRENCIES: Currency[] = ["USD", "XTR", "RUB"];
const BULK_SCOPES: BulkAdjustScope[] = ["ALL_PLANS", "ALL_ADDONS"];

const cellInputClassName =
  "w-24 rounded-[10px] border px-2.5 py-1.5 text-right text-sm tabular-nums outline-none focus:border-primary";

interface PricingMatrixProps {
  book: PriceBook;
  onChanged: () => void;
}

export function PricingMatrix({ book, onChanged }: PricingMatrixProps) {
  const { t } = useTranslation();

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

  const rows: { row: PriceBookRow }[] = [
    ...book.plans.map((row) => ({ row })),
    ...book.addons.map((row) => ({ row })),
  ];

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Table2 className="size-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">{t("pricing.matrix.title")}</h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("pricing.matrix.description")}</p>
          </div>
        </div>
        <BulkAdjustButton onChanged={onChanged} />
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      {rows.length === 0 ? (
        <div className="flex flex-col items-center gap-2 py-10 text-muted-foreground">
          <Inbox className="size-5" />
          <p className="text-sm">{t("pricing.matrix.empty")}</p>
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                <th className="p-2">{t("pricing.matrix.item")}</th>
                <th className="p-2">{t("pricing.matrix.basePrice")}</th>
                {CURRENCIES.map((currency) => (
                  <th key={currency} className="p-2">
                    <span className="inline-flex items-center gap-1.5">
                      {currency}
                      {currency === book.settings.anchor_currency && (
                        <span className="rounded-full bg-accent px-1.5 py-px text-[9.5px] tracking-wide text-primary">
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
                <tr>
                  <td colSpan={2 + CURRENCIES.length} className="px-2 pb-1.5 pt-4 text-[11.5px] font-bold uppercase tracking-wider text-muted-foreground">
                    {t("pricing.matrix.plansSection")}
                  </td>
                </tr>
              )}
              {book.plans.map((row) => (
                <MatrixRow
                  key={`plan_duration-${row.ref_id}`}
                  row={row}
                  anchorCurrency={book.settings.anchor_currency}
                  onSaveOverride={saveOverride}
                  onSaveBasePrice={saveBasePrice}
                />
              ))}
              {book.addons.length > 0 && (
                <tr>
                  <td colSpan={2 + CURRENCIES.length} className="px-2 pb-1.5 pt-4 text-[11.5px] font-bold uppercase tracking-wider text-muted-foreground">
                    {t("pricing.matrix.addonsSection")}
                  </td>
                </tr>
              )}
              {book.addons.map((row) => (
                <MatrixRow
                  key={`addon-${row.ref_id}`}
                  row={row}
                  anchorCurrency={book.settings.anchor_currency}
                  onSaveOverride={saveOverride}
                  onSaveBasePrice={saveBasePrice}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function MatrixRow({
  row,
  anchorCurrency,
  onSaveOverride,
  onSaveBasePrice,
}: {
  row: PriceBookRow;
  anchorCurrency: Currency;
  onSaveOverride: (row: PriceBookRow, currency: Currency, price: string | null) => void;
  onSaveBasePrice: (row: PriceBookRow, newBasePrice: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <tr className="border-t border-white/[0.06] transition-colors hover:bg-white/[0.02]">
      <td className="p-2 font-semibold text-foreground/90">{row.label}</td>
      <td className="p-2">
        <input
          key={row.base_price}
          type="number"
          step="0.01"
          min="0"
          defaultValue={row.base_price}
          onBlur={(event) => {
            if (event.target.value === "" || event.target.value === row.base_price) return;
            onSaveBasePrice(row, event.target.value);
          }}
          className={`${cellInputClassName} border-border bg-input/60`}
        />
      </td>
      {CURRENCIES.map((currency) => {
        const cell = row.cells.find((c) => c.currency === currency);
        if (!cell) return <td key={currency} className="p-2" />;
        if (currency === anchorCurrency) {
          return (
            <td key={currency} className="p-2 tabular-nums text-foreground/70">
              {cell.amount}
            </td>
          );
        }
        return (
          <td key={currency} className="p-2">
            <div className="flex items-center gap-1">
              <input
                key={cell.amount}
                type="number"
                step="0.01"
                min="0"
                defaultValue={cell.amount}
                aria-label={cell.is_pinned ? t("pricing.matrix.pinned") : undefined}
                onBlur={(event) => {
                  if (event.target.value === "" || event.target.value === cell.amount) return;
                  onSaveOverride(row, currency, event.target.value);
                }}
                className={`${cellInputClassName} ${
                  cell.is_pinned
                    ? "border-primary/40 bg-accent font-semibold text-primary"
                    : "border-border bg-input/60 text-foreground"
                }`}
              />
              {cell.is_pinned ? (
                <button
                  type="button"
                  onClick={() => onSaveOverride(row, currency, null)}
                  aria-label={t("pricing.matrix.clearPin")}
                  className="rounded-full p-1 text-primary transition-colors hover:bg-white/[0.08] hover:text-foreground"
                >
                  <Pin className="size-3" />
                </button>
              ) : (
                <PinOff className="size-3 text-muted-foreground/30" aria-hidden />
              )}
            </div>
          </td>
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
    try {
      await adjustBasePrices(buildBody());
      toast.success(t("pricing.matrix.applied"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.matrix.applyError")));
    } finally {
      setStep("closed");
      setDiff(null);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => setStep("form")}
        className="inline-flex items-center gap-2 rounded-full border border-border px-3.5 py-2 text-sm font-medium text-foreground/90 transition-colors hover:bg-white/5"
      >
        <Wand2 className="size-4" aria-hidden />
        {t("pricing.matrix.bulkAdjust")}
      </button>

      {step === "form" && (
        <ConfirmDialog
          title={t("pricing.matrix.bulkAdjustTitle")}
          icon={Wand2}
          size="md"
          message={t("pricing.matrix.bulkAdjustDescription")}
          confirmLabel={isLoading ? t("pricing.matrix.previewing") : t("pricing.matrix.preview")}
          cancelLabel={t("pricing.matrix.cancel")}
          onConfirm={() => void handlePreview()}
          onCancel={() => setStep("closed")}
        >
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-1 text-[12px] text-muted-foreground">
              <span>{t("pricing.matrix.scopeLabel")}</span>
              <SelectDropdown
                value={scope}
                onChange={(value) => setScope(value as BulkAdjustScope)}
                icon={Filter}
                placeholder={t(`pricing.matrix.scope.${scope}`)}
                options={BULK_SCOPES.map((option) => ({
                  value: option,
                  label: t(`pricing.matrix.scope.${option}`),
                }))}
              />
            </div>
            <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
              {t("pricing.matrix.factorLabel")}
              <input
                type="number"
                step="any"
                min="0"
                required
                placeholder={t("pricing.matrix.factorPlaceholder")}
                value={factor}
                onChange={(event) => setFactor(event.target.value)}
                className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
              />
            </label>
          </div>
        </ConfirmDialog>
      )}

      {step === "confirm" && diff && (
        <ConfirmDialog
          title={t("pricing.matrix.confirmTitle")}
          icon={Wand2}
          size="md"
          message={t("pricing.matrix.confirmMessage", { count: diff.affected_count })}
          confirmLabel={t("pricing.matrix.apply")}
          cancelLabel={t("pricing.matrix.cancel")}
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
