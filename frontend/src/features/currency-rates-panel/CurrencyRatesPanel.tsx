import { Anchor, Coins, Filter, Gauge, History } from "lucide-react";
import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  CURRENCIES,
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
import {
  listUnratedAnchorAmounts,
  rateUnratedAnchorAmounts,
  type UnratedAnchorCount,
} from "@entities/transactions/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { currencySymbol } from "@shared/lib/format";
import { blockNonDecimalKeys, blockNonIntegerKeys, parseOptionalInt, toTwoDecimals } from "@shared/lib/number-input";
import { toast } from "@shared/lib/toast";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { Button } from "@shared/ui/Button";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Badge } from "@shared/ui/Badge";
import { Field } from "@shared/ui/glass/Field";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { PillTabs } from "@shared/ui/PillTabs";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { Tooltip } from "@shared/ui/Tooltip";

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
  const canRateUnrated = permissions.includes("TRANSACTIONS_UNRATED_RATE");

  return (
    <>
      {(canManageRates || canSwitchAnchor) && (
        <Section
          icon={Coins}
          title={t("pricing.rates.title")}
          description={t("pricing.rates.description")}
        >
          {(canSwitchAnchor || canRateUnrated) && (
            <SectionRows>
              {canSwitchAnchor && (
                <Row icon={Anchor} label={t("pricing.anchor.title")} description={t("pricing.anchor.description")}>
                  <AnchorSwitcher anchorCurrency={book.settings.anchor_currency} onChanged={onChanged} />
                </Row>
              )}
              {canRateUnrated && <UnratedAnchorRow />}
            </SectionRows>
          )}
          {canManageRates && (
            <div className="mt-4 grid min-w-0 gap-3 lg:grid-cols-3">
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
        </Section>
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

  // undefined: the charm-ending field isn't a valid optional integer, reject the submit
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
      className={`flex min-w-0 flex-col gap-3 rounded-2xl border p-3.5 transition-colors ${
        isDirty ? "border-primary/35 bg-primary/[0.04]" : "border-white/[0.08] bg-white/[0.03]"
      }`}
    >
      <div className="flex items-center gap-2.5">
        <IconCircle glyph={currencySymbol(rate.currency)} />
        <span className="text-[13px] font-semibold text-foreground">{rate.currency}</span>
        {isAnchor && (
          <Badge borderless tone="accent" className="ml-auto">
            <Anchor className="size-2.5" />
            {t("pricing.anchor.badge")}
          </Badge>
        )}
      </div>
      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-1 flex-col gap-3">
        <Field
          label={t("pricing.rates.rateLabel")}
          htmlFor={`${idPrefix}-rate`}
          required={!isAnchor}
          error={isRateInvalid ? t("pricing.rates.rateInvalid") : undefined}
        >
          <Input
            id={`${idPrefix}-rate`}
            type="number"
            onKeyDown={blockNonDecimalKeys}
            step="any"
            min="0"
            disabled={isAnchor}
            aria-invalid={isRateInvalid}
            value={form.rate}
            onChange={(event) => setForm((prev) => ({ ...prev, rate: event.target.value }))}
          />
        </Field>
        <Field label={t("pricing.rates.charmEndingLabel")} htmlFor={`${idPrefix}-charm`} info={t("pricing.rates.charmEndingHint")}>
          <Input
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
        <Field label={t("pricing.rates.roundingModeLabel")} htmlFor={`${idPrefix}-rounding`}>
          <SelectDropdown
            variant="well"
            size="compact"
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
        <div className="mt-auto">
          <SaveFooter variant="glassAccent" dirty={isDirty} saving={isSubmitting} disabled={isRateInvalid} flush />
        </div>
      </form>

      {diff && (
        <ConfirmDialog
          title={t("pricing.rates.confirmTitle")}
          icon={Coins}
          size="md"
          message={t("pricing.rates.confirmMessage", { currency: t(`pricing.currencyIn.${rate.currency}`) })}
          confirmLabel={t("pricing.rates.confirmButton")}
          cancelLabel={t("common.cancel")}
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
    <>
      <div className="w-36">
        <PillTabs
          items={ANCHOR_CURRENCIES.map((currency) => ({ key: currency, label: currency }))}
          activeKey={anchorCurrency}
          disabled={isLoading}
          onSelect={(currency) => currency !== anchorCurrency && void handlePreview(currency)}
        />
      </div>

      {diff && (
        <ConfirmDialog
          title={t("pricing.anchor.confirmTitle")}
          size="md"
          message={t("pricing.anchor.confirmMessage", { currency: t(`pricing.currencyTo.${selected}`) })}
          confirmLabel={t("pricing.anchor.confirmButton")}
          cancelLabel={t("common.cancel")}
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
    </>
  );
}

function UnratedAnchorRow() {
  const { t } = useTranslation();
  const [items, setItems] = useState<UnratedAnchorCount[]>([]);
  const [isConfirming, setIsConfirming] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    listUnratedAnchorAmounts(controller.signal)
      .then(setItems)
      .catch(() => undefined);
    return () => controller.abort();
  }, []);

  const count = items.reduce((sum, item) => sum + item.count, 0);
  if (count === 0) return null;
  const currencies = items.map((item) => item.currency).join(", ");

  const handleConfirm = async () => {
    setIsConfirming(false);
    setIsSubmitting(true);
    try {
      setItems(await rateUnratedAnchorAmounts());
      toast.success(t("pricing.unrated.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.unrated.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Row
      icon={History}
      label={t("pricing.unrated.title")}
      description={t("pricing.unrated.description", { count, currencies })}
    >
      <Button variant="glass" size="sm" isLoading={isSubmitting} onClick={() => setIsConfirming(true)}>
        {t("pricing.unrated.button")}
      </Button>
      {isConfirming && (
        <ConfirmDialog
          title={t("pricing.unrated.confirmTitle")}
          size="md"
          message={t("pricing.unrated.confirmMessage", { count, currencies })}
          confirmLabel={t("pricing.unrated.button")}
          cancelLabel={t("common.cancel")}
          onConfirm={() => void handleConfirm()}
          onCancel={() => setIsConfirming(false)}
        />
      )}
    </Row>
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

  const dirty = perDay !== toTwoDecimals(pricePerDay ?? "") || perGb !== toTwoDecimals(pricePerGb ?? "");

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
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={Gauge}
        title={
          <>
            {t("pricing.settings.title")}
            <Badge tone="warning" borderless tabIndex={0} className="group relative outline-none">
              {t("dialogs.beta")}
              <Tooltip text={t("pricing.settings.betaHint")} side="bottom" />
            </Badge>
          </>
        }
        description={t("pricing.settings.description")}
        footer={canManage && <SaveFooter variant="glassAccent" dirty={dirty} saving={isSubmitting} />}
      >
        <SectionFields>
          <fieldset disabled={!canManage} className="grid min-w-0 gap-3 sm:grid-cols-2">
            <Field label={t("pricing.settings.pricePerDayLabel")} htmlFor="pricing-per-day">
              <Input
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
              <Input
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
        </SectionFields>
      </Section>
    </form>
  );
}
