import { Filter, Pencil, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type AdLink, updateAdLink } from "@entities/advertising/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Switch } from "@shared/ui/Switch";

const CURRENCIES = ["USD", "XTR", "RUB"];

interface AdLinkEditDialogProps {
  adLink: AdLink;
  onClose: () => void;
  onSaved: (adLink: AdLink) => void;
}

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

export function AdLinkEditDialog({ adLink, onClose, onSaved }: AdLinkEditDialogProps) {
  return (
    <Modal onClose={onClose} size="sm">
      <AdLinkEditDialogBody adLink={adLink} onSaved={onSaved} />
    </Modal>
  );
}

function AdLinkEditDialogBody({ adLink, onSaved }: Pick<AdLinkEditDialogProps, "adLink" | "onSaved">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState(adLink.name);
  const [cost, setCost] = useState(adLink.cost);
  const [currency, setCurrency] = useState(adLink.cost_currency);
  const [isActive, setIsActive] = useState(adLink.is_active);
  const [note, setNote] = useState(adLink.note ?? "");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const updated = await updateAdLink(adLink.id, {
        name: name.trim(),
        cost,
        cost_currency: currency,
        is_active: isActive,
        note: note.trim() || null,
      });
      toast.success(t("advertising.edit.saved"));
      onSaved(updated);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <Pencil className="size-4" />
          </div>
          {t("advertising.edit.title")}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("advertising.edit.close")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4 px-5 pb-5 pt-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="adlink-edit-name" className="text-sm font-medium text-foreground/80">
            {t("advertising.edit.nameLabel")}
          </label>
          <input
            id="adlink-edit-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            className={fieldClassName}
          />
        </div>

        <div className="flex gap-3">
          <div className="flex flex-1 flex-col gap-1">
            <label htmlFor="adlink-edit-cost" className="text-sm font-medium text-foreground/80">
              {t("advertising.edit.costLabel")}
            </label>
            <input
              id="adlink-edit-cost"
              type="number"
              min={0}
              step="0.01"
              value={cost}
              onChange={(event) => setCost(event.target.value)}
              className={fieldClassName}
            />
          </div>
          <div className="flex flex-1 flex-col gap-1">
            <span className="text-sm font-medium text-foreground/80">{t("advertising.edit.currencyLabel")}</span>
            <SelectDropdown
              id="adlink-edit-currency"
              value={currency}
              onChange={setCurrency}
              icon={Filter}
              placeholder={currency}
              options={CURRENCIES.map((value) => ({ value, label: value }))}
            />
          </div>
        </div>

        <label className="flex items-center gap-2.5 text-sm font-medium text-foreground/80">
          <Switch checked={isActive} onChange={setIsActive} ariaLabel={t("advertising.edit.activeLabel")} />
          {t("advertising.edit.activeLabel")}
        </label>

        <div className="flex flex-col gap-1">
          <label htmlFor="adlink-edit-note" className="text-sm font-medium text-foreground/80">
            {t("advertising.edit.noteLabel")}
          </label>
          <textarea
            id="adlink-edit-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={2}
            className={`${fieldClassName} resize-none`}
          />
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={close}
            className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("advertising.edit.cancel")}
          </button>
          <motion.button
            type="submit"
            disabled={isSubmitting}
            {...bounceTap(bounceStrength)}
            className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? t("advertising.edit.saving") : t("advertising.edit.save")}
          </motion.button>
        </div>
      </form>
    </>
  );
}
