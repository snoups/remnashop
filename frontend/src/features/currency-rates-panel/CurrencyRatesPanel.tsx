import { Coins, Filter } from "lucide-react";
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
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const CURRENCIES: Currency[] = ["USD", "XTR", "RUB"];
const ROUNDING_MODES: RoundingMode[] = ["INTEGER", "DECIMAL_2"];

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
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <Coins className="size-4" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">{t("pricing.rates.title")}</h2>
          <p className="text-[12.5px] text-muted-foreground">{t("pricing.rates.description")}</p>
        </div>
      </div>

      {canManageRates && (
        <>
          <div className="mt-4 flex flex-col gap-3">
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

          <div className="my-4 border-t border-border" />

          <AnchorSwitcher anchorCurrency={book.settings.anchor_currency} onChanged={onChanged} />
        </>
      )}

      <div className="my-4 border-t border-border" />

      <GlobalSettings pricePerDay={book.settings.price_per_day} pricePerGb={book.settings.price_per_gb} onChanged={onChanged} />
    </div>
  );
}

interface RateRowState {
  rate: string;
  rounding_mode: RoundingMode;
  charm_ending: string;
  min_amount: string;
}

function toRowState(rate: CurrencyRate): RateRowState {
  return {
    rate: rate.rate,
    rounding_mode: rate.rounding_mode,
    charm_ending: rate.charm_ending === null ? "" : String(rate.charm_ending),
    min_amount: rate.min_amount,
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

  // undefined means the charm-ending field holds something that isn't a
  // valid optional integer -- callers reject the submit instead of sending it.
  const buildBody = () => {
    const charmEnding = parseOptionalInt(form.charm_ending, 0);
    if (charmEnding === undefined) return undefined;
    return {
      rate: form.rate,
      rounding_mode: form.rounding_mode,
      charm_ending: charmEnding,
      min_amount: form.min_amount,
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
    <div className="rounded-xl border border-border bg-white/[0.02] p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-sm font-bold text-foreground">{rate.currency}</span>
        {isAnchor && (
          <span className="rounded-full border border-primary/40 bg-accent px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-wide text-primary">
            {t("pricing.anchor.badge")}
          </span>
        )}
      </div>
      <form onSubmit={(event) => void handleSubmit(event)} className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
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
        <div className="flex flex-col gap-1 text-[12px] text-muted-foreground">
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
        <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
          {t("pricing.rates.charmEndingLabel")}
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
        <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
          {t("pricing.rates.minAmountLabel")}
          <input
            type="number"
            step="any"
            min="0"
            required
            value={form.min_amount}
            onChange={(event) => setForm((prev) => ({ ...prev, min_amount: event.target.value }))}
            className={inputClassName}
          />
        </label>
        <div className="col-span-2 sm:col-span-4">
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("pricing.rates.saving") : t("pricing.rates.save")}
          </button>
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

  const handlePreview = async () => {
    setIsLoading(true);
    try {
      const preview = await previewPricingChange({ anchor: selected });
      setDiff(preview);
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.anchor.saveError")));
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
    <div>
      <h3 className="text-sm font-bold text-foreground">{t("pricing.anchor.title")}</h3>
      <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("pricing.anchor.description")}</p>
      <div className="mt-2.5 flex items-center gap-2">
        <div className="w-40">
          <SelectDropdown
            value={selected}
            onChange={(value) => setSelected(value as Currency)}
            icon={Filter}
            placeholder={selected}
            options={CURRENCIES.map((currency) => ({ value: currency, label: currency }))}
          />
        </div>
        <button
          type="button"
          disabled={selected === anchorCurrency || isLoading}
          onClick={() => void handlePreview()}
          className="rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/90 transition-colors hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {t("pricing.anchor.change")}
        </button>
      </div>

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
  pricePerDay,
  pricePerGb,
  onChanged,
}: {
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
    <div>
      <h3 className="text-sm font-bold text-foreground">{t("pricing.settings.title")}</h3>
      <p className="mt-0.5 text-[12.5px] text-muted-foreground">{t("pricing.settings.description")}</p>
      <form onSubmit={(event) => void handleSubmit(event)} className="mt-2.5 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
          {t("pricing.settings.pricePerDayLabel")}
          <input
            type="number"
            step="any"
            min="0"
            value={perDay}
            onChange={(event) => setPerDay(event.target.value)}
            className={inputClassName}
          />
        </label>
        <label className="flex flex-col gap-1 text-[12px] text-muted-foreground">
          {t("pricing.settings.pricePerGbLabel")}
          <input
            type="number"
            step="any"
            min="0"
            value={perGb}
            onChange={(event) => setPerGb(event.target.value)}
            className={inputClassName}
          />
        </label>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isSubmitting ? t("pricing.settings.saving") : t("pricing.settings.save")}
        </button>
      </form>
    </div>
  );
}
