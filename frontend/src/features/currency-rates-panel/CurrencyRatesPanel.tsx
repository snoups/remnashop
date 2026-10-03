import { Anchor, Coins, Filter, Gauge, Info } from "lucide-react";
import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  previewPricingChange,
  switchAnchorCurrency,
  updateCurrencyRate,
  updatePricingSettings,
  type Currency,
  type CurrencyRate,
  type PriceBook,
  type PricingDiff,
  type RoundingMode,
} from "@entities/pricing/api";
import { PricingDiffList } from "@entities/pricing/PricingDiffList";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { blockNonDecimalKeys, blockNonIntegerKeys, parseOptionalInt, toTwoDecimals } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Button } from "@shared/ui/Button";
import { Badge } from "@shared/ui/Badge";
import { SuffixInput, TextInput } from "@shared/ui/TextInput";
import { Card } from "@shared/ui/Card";
import { Field } from "@shared/ui/Field";

const CURRENCIES: Currency[] = ["USD", "RUB", "XTR"];
const ANCHOR_CURRENCIES: Currency[] = ["USD", "RUB"];
const ROUNDING_MODES: RoundingMode[] = ["INTEGER", "DECIMAL_2"];


interface CurrencyRatesPanelProps {
  book: PriceBook;
  onChanged: () => void;
}

export function CurrencyRatesPanel({ book, onChanged }: CurrencyRatesPanelProps) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManageRates = permissions.includes("PRICING_RATES_MANAGE");
  const canSwitchAnchor = permissions.includes("PRICING_ANCHOR_MANAGE");

  return (
    <>
      {(canManageRates || canSwitchAnchor) && (
      <Card>
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Coins className="size-4" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-foreground">{t("pricing.rates.title")}</h2>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("pricing.rates.description")}</p>
          </div>
        </div>

        <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

        {canSwitchAnchor && (
          <div className="mt-4 grid items-center gap-3 md:grid-cols-2 xl:grid-cols-3">
            <p className="flex items-center gap-1.5 text-[12.5px] text-muted-foreground xl:col-span-2">
              <Info className="size-3.5 shrink-0" />
              {t("pricing.anchor.description")}
            </p>
            <AnchorSwitcher anchorCurrency={book.settings.anchor_currency} onChanged={onChanged} />
          </div>
        )}

        {canManageRates && (
          <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {CURRENCIES.map((currency) => {
              const rate = book.rate_table.find((row) => row.currency === currency);
              if (!rate) return null;
              return (
                <RateRow
                  key={currency}
                  rate={rate}
                  isAnchor={currency === book.settings.anchor_currency}
                  onChanged={onChanged}
                />
              );
            })}
          </div>
        )}

      </Card>
      )}

      <GlobalSettings
        anchorCurrency={book.settings.anchor_currency}
        pricePerDay={book.settings.price_per_day}
        pricePerGb={book.settings.price_per_gb}
        onChanged={onChanged}
      />
    </>
  );
}

interface RateRowState {
  rate: string;
  rounding_mode: RoundingMode;
  charm_ending: string;
}

function toRowState(rate: CurrencyRate): RateRowState {
  return {
    rate: toTwoDecimals(rate.rate),
    rounding_mode: rate.rounding_mode,
    charm_ending: rate.charm_ending === null ? "" : String(rate.charm_ending),
  };
}

function RateRow({
  rate,
  isAnchor,
  onChanged,
}: {
  rate: CurrencyRate;
  isAnchor: boolean;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const idPrefix = useId();
  const [form, setForm] = useState<RateRowState>(() => toRowState(rate));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [diff, setDiff] = useState<PricingDiff | null>(null);

  useEffect(() => setForm(toRowState(rate)), [rate]);

  const initial = toRowState(rate);
  const isDirty =
    form.rate !== initial.rate ||
    form.rounding_mode !== initial.rounding_mode ||
    form.charm_ending !== initial.charm_ending;
  // mirrors the backend's rate > 0; the input's min="0" would let 0 through
  const isRateInvalid = form.rate.trim() !== "" && !(Number(form.rate) > 0);

  // undefined means the charm-ending field holds something that isn't a
  // valid optional integer -- callers reject the submit instead of sending it.
  const buildBody = () => {
    const charmEnding = parseOptionalInt(form.charm_ending, 0);
    if (charmEnding === undefined) return undefined;
    return {
      // the field shows the rate rounded; untouched, the stored precision goes back as-is
      rate: form.rate === initial.rate ? rate.rate : form.rate,
      rounding_mode: form.rounding_mode,
      charm_ending: charmEnding,
      min_amount: rate.min_amount,
    };
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const body = buildBody();
    if (!body) {
      toast.error(t("errors.invalidNumber"));
      return;
    }
    setIsSubmitting(true);
    try {
      const preview = await previewPricingChange({ rate: { currency: rate.currency, ...body } });
      setDiff(preview);
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.rates.previewError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleConfirm = async () => {
    setDiff(null);
    // form hasn't changed since the (already-validated) preview in handleSubmit
    const body = buildBody();
    if (!body) return;
    try {
      await updateCurrencyRate(rate.currency, body);
      toast.success(t("pricing.rates.saved"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.rates.saveError")));
    }
  };

  return (
    <div
      className={`flex flex-col gap-3.5 rounded-xl border p-3.5 transition-colors ${
        isDirty ? "border-primary/35 bg-primary/[0.04]" : "border-border bg-white/[0.02]"
      }`}
    >
      <div className="flex items-center gap-2.5">
        <span className="flex size-[34px] items-center justify-center rounded-[10px] border border-glass-border bg-white/[0.05] text-base font-bold text-foreground">
          {currencySymbol(rate.currency)}
        </span>
        <span className="text-[15px] font-bold tracking-wide text-foreground">{rate.currency}</span>
        {isAnchor && (
          <Badge tone="accent" className="ml-auto">
            <Anchor className="size-2.5" />
            {t("pricing.anchor.badge")}
          </Badge>
        )}
      </div>
      <form onSubmit={(event) => void handleSubmit(event)} className="grid grid-cols-2 gap-3">
        <Field
          label={t("pricing.rates.rateLabel")}
          htmlFor={`${idPrefix}-rate`}
          error={isRateInvalid ? t("pricing.rates.rateInvalid") : undefined}
          className="col-span-2"
        >
          <TextInput
            id={`${idPrefix}-rate`}
            type="number"
            onKeyDown={blockNonDecimalKeys}
            step="any"
            min="0"
            required
            disabled={isAnchor}
            aria-invalid={isRateInvalid}
            value={form.rate}
            onChange={(event) => setForm((prev) => ({ ...prev, rate: event.target.value }))}
          />
        </Field>
        <Field label={t("pricing.rates.charmEndingLabel")} htmlFor={`${idPrefix}-charm`} info={t("pricing.rates.charmEndingHint")} className="col-span-2">
          <TextInput
            id={`${idPrefix}-charm`}
            type="number"
            onKeyDown={blockNonIntegerKeys}
            step="1"
            min="0"
            max="99"
            placeholder={t("pricing.rates.charmEndingPlaceholder")}
            value={form.charm_ending}
            onChange={(event) => setForm((prev) => ({ ...prev, charm_ending: event.target.value }))}
          />
        </Field>
        <Field label={t("pricing.rates.roundingModeLabel")} htmlFor={`${idPrefix}-rounding`} className="col-span-2">
          <SelectDropdown
            variant="form"
            id={`${idPrefix}-rounding`}
            value={form.rounding_mode}
            onChange={(value) => setForm((prev) => ({ ...prev, rounding_mode: value as RoundingMode }))}
            icon={Filter}
            placeholder={t(`pricing.roundingModes.${form.rounding_mode}`)}
            options={ROUNDING_MODES.map((mode) => ({
              value: mode,
              label: t(`pricing.roundingModes.${mode}`),
            }))}
          />
        </Field>
        <div className="col-span-2 flex items-center gap-2.5">
          <Button
            variant="accent"
            className="w-fit"
            type="submit"
            disabled={isSubmitting || !isDirty || isRateInvalid}
          >
            {isSubmitting ? t("pricing.rates.saving") : t("pricing.rates.save")}
          </Button>
          {isDirty && <span className="text-xs text-warning">{t("pricing.rates.unsaved")}</span>}
        </div>
      </form>

      {diff && (
        <ConfirmDialog
          title={t("pricing.rates.confirmTitle")}
          icon={Coins}
          message={t("pricing.rates.confirmMessage", { currency: t(`pricing.currencyIn.${rate.currency}`) })}
          confirmLabel={t("pricing.rates.confirmButton")}
          cancelLabel={t("pricing.rates.cancelButton")}
          onConfirm={() => void handleConfirm()}
          onCancel={() => setDiff(null)}
        >
          <PricingDiffList diff={diff} />
        </ConfirmDialog>
      )}
    </div>
  );
}

function AnchorSwitcher({ anchorCurrency, onChanged }: { anchorCurrency: Currency; onChanged: () => void }) {
  const { t } = useTranslation();
  const [selected, setSelected] = useState<Currency>(anchorCurrency);
  const [diff, setDiff] = useState<PricingDiff | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => setSelected(anchorCurrency), [anchorCurrency]);

  const handlePreview = async (currency: Currency) => {
    setSelected(currency);
    setIsLoading(true);
    try {
      const preview = await previewPricingChange({ anchor: currency });
      setDiff(preview);
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.anchor.saveError")));
      setSelected(anchorCurrency);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConfirm = async () => {
    setDiff(null);
    try {
      await switchAnchorCurrency(selected);
      toast.success(t("pricing.anchor.saved"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.anchor.saveError")));
      setSelected(anchorCurrency);
    }
  };

  return (
    <div className="flex w-full items-center gap-1 rounded-full border border-glass-border bg-white/[0.03] p-0.5 backdrop-blur-md">
      <span className="flex items-center gap-1.5 pl-3 pr-2 text-xs text-foreground">
        <Anchor className="size-3.5" />
        {t("pricing.anchor.title")}
      </span>
      {ANCHOR_CURRENCIES.map((currency) => (
        <button
          key={currency}
          type="button"
          disabled={isLoading}
          onClick={() => currency !== anchorCurrency && void handlePreview(currency)}
          className={`flex h-[30px] flex-1 items-center justify-center rounded-full px-3 text-[12.5px] transition-colors disabled:cursor-not-allowed ${
            currency === anchorCurrency ? "bg-accent text-primary" : "text-foreground/70 hover:bg-white/[0.06]"
          }`}
        >
          {currency}
        </button>
      ))}

      {diff && (
        <ConfirmDialog
          title={t("pricing.anchor.confirmTitle")}
          message={t("pricing.anchor.confirmMessage", { currency: t(`pricing.currencyTo.${selected}`) })}
          confirmLabel={t("pricing.anchor.confirmButton")}
          cancelLabel={t("pricing.anchor.cancelButton")}
          danger
          onConfirm={() => void handleConfirm()}
          onCancel={() => {
            setDiff(null);
            setSelected(anchorCurrency);
          }}
        >
          <PricingDiffList diff={diff} />
        </ConfirmDialog>
      )}
    </div>
  );
}

function GlobalSettings({
  anchorCurrency,
  pricePerDay,
  pricePerGb,
  onChanged,
}: {
  anchorCurrency: Currency;
  pricePerDay: string | null;
  pricePerGb: string | null;
  onChanged: () => void;
}) {
  const { t } = useTranslation();
  const canManage = usePermissions().includes("PRICING_SETTINGS_MANAGE");
  const [perDay, setPerDay] = useState(toTwoDecimals(pricePerDay ?? ""));
  const [perGb, setPerGb] = useState(toTwoDecimals(pricePerGb ?? ""));
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setPerDay(toTwoDecimals(pricePerDay ?? ""));
    setPerGb(toTwoDecimals(pricePerGb ?? ""));
  }, [pricePerDay, pricePerGb]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await updatePricingSettings({
        price_per_day: perDay === "" ? null : perDay,
        price_per_gb: perGb === "" ? null : perGb,
      });
      toast.success(t("pricing.settings.saved"));
      onChanged();
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.settings.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card>
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Gauge className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("pricing.settings.title")}</h2>
          <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("pricing.settings.description")}</p>
        </div>
      </div>

      <div className="-mx-4 mt-4 border-t border-white/[0.07]" />

      <form onSubmit={(event) => void handleSubmit(event)} className="mt-4 flex flex-col gap-4">
        <fieldset disabled={!canManage} className="grid gap-3 sm:grid-cols-2">
          <Field label={t("pricing.settings.pricePerDayLabel")} htmlFor="pricing-per-day">
            <SuffixInput
              id="pricing-per-day"
              type="number"
              onKeyDown={blockNonDecimalKeys}
              step="any"
              min="0"
              value={perDay}
              onChange={(event) => setPerDay(event.target.value)}
              suffix={anchorCurrency}
            />
          </Field>
          <Field label={t("pricing.settings.pricePerGbLabel")} htmlFor="pricing-per-gb">
            <SuffixInput
              id="pricing-per-gb"
              type="number"
              onKeyDown={blockNonDecimalKeys}
              step="any"
              min="0"
              value={perGb}
              onChange={(event) => setPerGb(event.target.value)}
              suffix={anchorCurrency}
            />
          </Field>
        </fieldset>
        {canManage && (
          <Button
            variant="accent"
            className="w-fit"
            type="submit"
            disabled={isSubmitting}
          >
            {isSubmitting ? t("pricing.settings.saving") : t("pricing.settings.save")}
          </Button>
        )}
      </form>
    </Card>
  );
}
