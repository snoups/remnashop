import { Coins, Dices, Link2, Loader2 } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  type AdLink,
  AD_LINK_CODE_MAX_LENGTH,
  AD_LINK_CODE_PATTERN,
  createAdLink,
  generateAdLinkCode,
} from "@entities/advertising/api";
import { type AdLinkChannels, ChannelsPicker } from "@entities/advertising/ChannelsPicker";
import { CURRENCY_ICON } from "@entities/transactions/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { blockNonDecimalKeys } from "@shared/lib/number-input";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { TextInput, TextArea } from "@shared/ui/TextInput";
import { Field } from "@shared/ui/Field";

const CURRENCIES = ["USD", "XTR", "RUB"];
const FORM_ID = "adlink-create-form";

interface AdLinkCreateDialogProps {
  canGenerateCode: boolean;
  onClose: () => void;
  onSaved: (adLink: AdLink) => void;
}


export function AdLinkCreateDialog({ canGenerateCode, onClose, onSaved }: AdLinkCreateDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <AdLinkCreateDialogBody canGenerateCode={canGenerateCode} onSaved={onSaved} />
    </Modal>
  );
}

function AdLinkCreateDialogBody({
  canGenerateCode,
  onSaved,
}: Pick<AdLinkCreateDialogProps, "canGenerateCode" | "onSaved">) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [cost, setCost] = useState("0");
  const [currency, setCurrency] = useState("USD");
  const [note, setNote] = useState("");
  const [channels, setChannels] = useState<AdLinkChannels>({ allow_bot: true, allow_webcabinet: true });
  const trimmedCode = code.trim();
  const isCodeInvalid = trimmedCode !== "" && !AD_LINK_CODE_PATTERN.test(trimmedCode);
  const canSubmit = name.trim() !== "" && trimmedCode !== "" && !isCodeInvalid;

  const [isGenerating, setIsGenerating] = useState(false);

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      setCode(await generateAdLinkCode());
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.create.error")));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const created = await createAdLink({
        name: name.trim(),
        code: code.trim(),
        cost,
        cost_currency: currency,
        ...channels,
        note: note.trim() || null,
      });
      toast.success(t("advertising.create.saved"));
      onSaved(created);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.create.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <DialogHeader icon={Link2} title={t("advertising.create.title")} />

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        <form id={FORM_ID} onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-3">
          <Card variant="form">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <Field label={t("advertising.create.nameLabel")} htmlFor="adlink-name" required>
                <TextInput
                  id="adlink-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  maxLength={255}
                />
              </Field>
              <Field label={t("advertising.channels.label")}>
                <ChannelsPicker value={channels} onChange={setChannels} />
              </Field>
              <Field label={t("advertising.create.costLabel")} htmlFor="adlink-cost">
                <TextInput
                  id="adlink-cost"
                  type="number"
                  onKeyDown={blockNonDecimalKeys}
                  min={0}
                  step="0.01"
                  value={cost}
                  onChange={(event) => setCost(event.target.value)}
                />
              </Field>
              <Field label={t("advertising.create.currencyLabel")} htmlFor="adlink-currency">
                <SelectDropdown
                  variant="form"
                  id="adlink-currency"
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
            <Field label={t("advertising.create.codeLabel")} htmlFor="adlink-code" required>
              <div className="flex gap-2">
                <TextInput
                  id="adlink-code"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  placeholder={t("advertising.create.codePlaceholder")}
                  maxLength={AD_LINK_CODE_MAX_LENGTH}
                  aria-invalid={isCodeInvalid}
                  className="flex-1 font-mono"
                />
                {canGenerateCode && (
                  <Button
                    variant="secondary"
                    size="field"
                    onClick={() => void handleGenerate()}
                    disabled={isGenerating}
                  >
                    {isGenerating ? <Loader2 className="size-3.5 animate-spin" /> : <Dices className="size-3.5" />}
                    {t("advertising.create.generate")}
                  </Button>
                )}
              </div>
              {isCodeInvalid && (
                <p id="adlink-code-hint" className="text-[12px] text-error">
                  {t("advertising.create.codeInvalid")}
                </p>
              )}
            </Field>
          </Card>

          <Card variant="form">
            <Field label={t("advertising.create.noteLabel")} htmlFor="adlink-note">
              <TextArea
                id="adlink-note"
                value={note}
                onChange={(event) => setNote(event.target.value)}
                rows={2}
              />
            </Field>
          </Card>
        </form>
      </div>

      <div className="flex justify-end gap-2 border-t border-white/[0.07] px-5 py-4">
        <Button variant="outline" onClick={close}>
          {t("advertising.create.cancel")}
        </Button>
        <Button variant="accent" type="submit" form={FORM_ID} disabled={isSubmitting || !canSubmit}>
          {isSubmitting ? t("advertising.create.saving") : t("advertising.create.save")}
        </Button>
      </div>
    </>
  );
}
