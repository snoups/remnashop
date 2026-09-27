import { Anchor, Coins, Filter, Gauge, Info } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
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
import { useCurrentUser } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { parseOptionalInt } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { FieldHint } from "@shared/ui/FieldHint";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const CURRENCIES: Currency[] = ["USD", "RUB", "XTR"];
const ANCHOR_CURRENCIES: Currency[] = ["USD", "RUB"];
const ROUNDING_MODES: RoundingMode[] = ["INTEGER", "DECIMAL_2"];
const CURRENCY_SYMBOLS: Record<Currency, string> = { USD: "$", XTR: "★", RUB: "₽" };

const inputClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary disabled:cursor-not-allowed disabled:opacity-50";

interface CurrencyRatesPanelProps {
  book: PriceBook;
  onChanged: () => void;
}

export function CurrencyRatesPanel({ book, onChanged }: CurrencyRatesPanelProps) {
  const { t } = useTranslation();
  const userState = useCurrentUser();
  const canManageRates =
    userState.kind === "ready" && userState.data.effective_permissions.includes("PRICING_RATES_MANAGE");

  return (
    <>
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
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

        {canManageRates && (
          <div className="mt-4 grid items-center gap-3 md:grid-cols-2 xl:grid-cols-3">
            <p className="flex items-center gap-1.5 text-[12.5px] text-muted-foreground xl:col-span-2">
              <Info className="size-3.5 shrink-0" aria-hidden />
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

      </div>

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
    rate: rate.rate,
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
  const [form, setForm] = useState<RateRowState>(() => toRowState(rate));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [diff, setDiff] = useState<PricingDiff | null>(null);

  useEffect(() => setForm(toRowState(rate)), [rate]);

  const initial = toRowState(rate);
  const isDirty =
    form.rate !== initial.rate ||
    form.rounding_mode !== initial.rounding_mode ||
    form.charm_ending !== initial.charm_ending;

  // undefined means the charm-ending field holds something that isn't a
  // valid optional integer -- callers reject the submit instead of sending it.
  const buildBody = () => {
    const charmEnding = parseOptionalInt(form.charm_ending, 0);
    if (charmEnding === undefined) return undefined;
    return {
      rate: form.rate,
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
          {CURRENCY_SYMBOLS[rate.currency]}
        </span>
        <span className="text-[15px] font-bold tracking-wide text-foreground">{rate.currency}</span>
        {isAnchor && (
          <span className="ml-auto inline-flex items-center gap-1 rounded-full border border-primary/40 bg-accent px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-primary">
            <Anchor className="size-2.5" aria-hidden />
            {t("pricing.anchor.badge")}
          </span>
        )}
      </div>
      <form onSubmit={(event) => void handleSubmit(event)} className="grid grid-cols-2 gap-3">
        <label className="col-span-2 flex flex-col gap-1.5 text-[12px] text-muted-foreground">
          {t("pricing.rates.rateLabel")}
          <input
            type="number"
            step="any"
            min="0"
            required
            disabled={isAnchor}
            value={form.rate}
            onChange={(event) => setForm((prev) => ({ ...prev, rate: event.target.value }))}
            className={inputClassName}
          />
        </label>
        <div className="col-span-2 flex flex-col gap-1.5 text-[12px] text-muted-foreground">
          <span>{t("pricing.rates.roundingModeLabel")}</span>
          <SelectDropdown
            value={form.rounding_mode}
            onChange={(value) => setForm((prev) => ({ ...prev, rounding_mode: value as RoundingMode }))}
            icon={Filter}
            placeholder={t(`pricing.roundingModes.${form.rounding_mode}`)}
            options={ROUNDING_MODES.map((mode) => ({
              value: mode,
              label: t(`pricing.roundingModes.${mode}`),
            }))}
          />
        </div>
        <label className="col-span-2 flex flex-col gap-1.5 text-[12px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            {t("pricing.rates.charmEndingLabel")}
            <FieldHint text={t("pricing.rates.charmEndingHint")} />
          </span>
          <input
            type="number"
            step="1"
            min="0"
            max="99"
            placeholder={t("pricing.rates.charmEndingPlaceholder")}
            value={form.charm_ending}
            onChange={(event) => setForm((prev) => ({ ...prev, charm_ending: event.target.value }))}
            className={inputClassName}
          />
        </label>
        <div className="col-span-2 flex items-center gap-2.5">
          <button
            type="submit"
            disabled={isSubmitting || !isDirty}
            className="w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("pricing.rates.saving") : t("pricing.rates.save")}
          </button>
          {isDirty && <span className="text-xs text-warning">{t("pricing.rates.unsaved")}</span>}
        </div>
      </form>

      {diff && (
        <ConfirmDialog
          title={t("pricing.rates.confirmTitle")}
          message={t("pricing.rates.confirmMessage", { currency: rate.currency })}
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
    <div role="group" aria-label={t("pricing.anchor.title")} className="flex w-full items-center gap-1 rounded-full border border-border bg-white/[0.03] p-[3px]">
      <span className="flex items-center gap-1.5 pl-3 pr-2 text-xs text-muted-foreground">
        <Anchor className="size-3.5" aria-hidden />
        {t("pricing.anchor.title")}
      </span>
      {ANCHOR_CURRENCIES.map((currency) => (
        <button
          key={currency}
          type="button"
          disabled={isLoading}
          aria-pressed={currency === anchorCurrency}
          onClick={() => currency !== anchorCurrency && void handlePreview(currency)}
          className={`flex-1 rounded-full px-3 py-1.5 text-[12.5px] font-semibold transition-colors disabled:cursor-not-allowed ${
            currency === anchorCurrency
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"
          }`}
        >
          {currency}
        </button>
      ))}

      {diff && (
        <ConfirmDialog
          title={t("pricing.anchor.confirmTitle")}
          message={t("pricing.anchor.confirmMessage", { currency: selected })}
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
  const [perDay, setPerDay] = useState(pricePerDay ?? "");
  const [perGb, setPerGb] = useState(pricePerGb ?? "");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    setPerDay(pricePerDay ?? "");
    setPerGb(pricePerGb ?? "");
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
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
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
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="flex flex-col gap-1.5 text-[12px] text-muted-foreground">
            {t("pricing.settings.pricePerDayLabel")}
            <div className="relative">
              <input
                type="number"
                step="any"
                min="0"
                value={perDay}
                onChange={(event) => setPerDay(event.target.value)}
                className={`${inputClassName} w-full pr-14`}
              />
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                {anchorCurrency}
              </span>
            </div>
          </label>
          <label className="flex flex-col gap-1.5 text-[12px] text-muted-foreground">
            {t("pricing.settings.pricePerGbLabel")}
            <div className="relative">
              <input
                type="number"
                step="any"
                min="0"
                value={perGb}
                onChange={(event) => setPerGb(event.target.value)}
                className={`${inputClassName} w-full pr-14`}
              />
              <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                {anchorCurrency}
              </span>
            </div>
          </label>
        </div>
        <button
          type="submit"
          disabled={isSubmitting}
          className="w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? t("pricing.settings.saving") : t("pricing.settings.save")}
        </button>
      </form>
    </div>
  );
}
