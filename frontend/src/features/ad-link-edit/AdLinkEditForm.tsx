import { Coins } from "lucide-react";
import { useTranslation } from "react-i18next";

import { ChannelsPicker } from "@entities/advertising/ChannelsPicker";
import { CURRENCY_ICON } from "@entities/transactions/api";
import { AD_LINK_EDIT_FORM_ID, type AdLinkEditFormState } from "@features/ad-link-edit/use-ad-link-edit-form";
import { blockNonDecimalKeys } from "@shared/lib/number-input";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Card } from "@shared/ui/Card";
import { TextInput, TextArea } from "@shared/ui/TextInput";
import { Field } from "@shared/ui/Field";

const CURRENCIES = ["USD", "XTR", "RUB"];

export function AdLinkEditForm({ form }: { form: AdLinkEditFormState }) {
  const { t } = useTranslation();
  const { name, setName, cost, setCost, currency, setCurrency, note, setNote, channels, setChannels } = form;

  return (
    <form
      id={AD_LINK_EDIT_FORM_ID}
      onSubmit={(event) => {
        event.preventDefault();
        if (form.canSubmit) void form.submit();
      }}
      className="flex flex-col gap-4"
    >
      {/* column order pairs the rows: name | channels, cost | currency */}
      <Card variant="form">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label={t("advertising.edit.nameLabel")} htmlFor="adlink-edit-name" required>
            <TextInput
              id="adlink-edit-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              maxLength={255}
              className="w-full"
            />
          </Field>
          <Field label={t("advertising.channels.label")}>
            <ChannelsPicker value={channels} onChange={setChannels} />
          </Field>
          <Field label={t("advertising.edit.costLabel")} htmlFor="adlink-edit-cost">
            <TextInput
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
              variant="form"
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
      </Card>

      <Card variant="form">
        <Field label={t("advertising.edit.noteLabel")} htmlFor="adlink-edit-note">
          <TextArea
            id="adlink-edit-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            className="w-full"
          />
        </Field>
      </Card>
    </form>
  );
}
