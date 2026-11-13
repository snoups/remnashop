import { Coins } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ChannelsPicker } from "@entities/advertising/ChannelsPicker";
import { RevenueSharePercentField } from "@entities/advertising/RevenueSharePercentField";
import { CURRENCIES } from "@entities/pricing/api";
import { CURRENCY_ICON } from "@entities/transactions/api";
import { AD_LINK_EDIT_FORM_ID, type AdLinkEditFormState } from "@features/ad-link-edit/use-ad-link-edit-form";
import { blockNonDecimalKeys } from "@shared/lib/number-input";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { GLASS_DIALOG_CARD_CLASS } from "@shared/ui/classes";
import { Field } from "@shared/ui/glass/Field";
import { Input, TextArea } from "@shared/ui/glass/Input";


export function AdLinkEditForm({ form }: { form: AdLinkEditFormState }) {
  const { t } = useTranslation();
  const { name, setName, cost, setCost, currency, setCurrency, note, setNote, channels, setChannels } = form;
  const { revenueSharePercent, setRevenueSharePercent } = form;

  return (
    <form
      id={AD_LINK_EDIT_FORM_ID}
      onSubmit={(event) => {
        event.preventDefault();
        if (form.canSubmit) void form.submit();
      }}
      className="flex flex-col gap-3"
    >
      {/* column order pairs the rows: name | channels, cost | currency */}
      <div className={GLASS_DIALOG_CARD_CLASS}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label={t("advertising.edit.nameLabel")} htmlFor="adlink-edit-name" required>
            <Input
              id="adlink-edit-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t("advertising.create.namePlaceholder")}
              maxLength={255}
              className="w-full"
            />
          </Field>
          <Field label={t("advertising.channels.label")}>
            <ChannelsPicker value={channels} onChange={setChannels} />
          </Field>
          <Field label={t("advertising.edit.costLabel")} htmlFor="adlink-edit-cost">
            <Input
              id="adlink-edit-cost"
              type="number"
              onKeyDown={blockNonDecimalKeys}
              min={0}
              step="0.01"
              value={cost}
              onChange={(event) => setCost(event.target.value)}
              className="w-full"
            />
          </Field>
          <Field label={t("advertising.edit.currencyLabel")} htmlFor="adlink-edit-currency">
            <SelectDropdown
              variant="well"
              size="compact"
              id="adlink-edit-currency"
              value={currency}
              onChange={setCurrency}
              icon={Coins}
              placeholder={currency}
              options={CURRENCIES.map((value) => ({
                value,
                label: t(`advertising.currencies.${value}`),
                icon: CURRENCY_ICON[value],
              }))}
            />
          </Field>
        </div>
      </div>

      <div className={GLASS_DIALOG_CARD_CLASS}>
        <RevenueSharePercentField
          id="adlink-edit-revenue-share"
          value={revenueSharePercent}
          onChange={setRevenueSharePercent}
        />
      </div>

      <div className={GLASS_DIALOG_CARD_CLASS}>
        <Field label={t("advertising.edit.noteLabel")} htmlFor="adlink-edit-note">
          <TextArea
            id="adlink-edit-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={t("advertising.create.notePlaceholder")}
            rows={2}
            className="w-full"
          />
        </Field>
      </div>
    </form>
  );
}
