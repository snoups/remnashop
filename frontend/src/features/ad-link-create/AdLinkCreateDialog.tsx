import { Dices, Filter, Link2, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { type AdLink, createAdLink, generateAdLinkCode } from "@entities/advertising/api";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { DialogPortal } from "@shared/ui/DialogPortal";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const CURRENCIES = ["USD", "XTR", "RUB"];

interface AdLinkCreateDialogProps {
  canGenerateCode: boolean;
  onClose: () => void;
  onSaved: (adLink: AdLink) => void;
}

const fieldClassName =
  "rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary";

export function AdLinkCreateDialog({ canGenerateCode, onClose, onSaved }: AdLinkCreateDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [cost, setCost] = useState("0");
  const [currency, setCurrency] = useState("USD");
  const [note, setNote] = useState("");

  const handleGenerate = async () => {
    try {
      setCode(await generateAdLinkCode());
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.create.error")));
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
        note: note.trim() || null,
      });
      toast.success(t("advertising.create.saved"));
      onSaved(created);
      onClose();
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.create.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <DialogPortal>
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15, ease: "easeOut" }}
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/55 backdrop-blur-3xl p-4"
        >
          <button
            type="button"
            aria-hidden
            tabIndex={-1}
            className="absolute inset-0 cursor-default"
            onClick={onClose}
          />

          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 8 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className="relative z-50 w-full max-w-sm rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
          >
            <div className="flex items-center justify-between border-b border-border px-5 py-4">
              <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                  <Link2 className="size-4" />
                </div>
                {t("advertising.create.title")}
              </h2>
              <button
                type="button"
                onClick={onClose}
                aria-label={t("advertising.create.close")}
                className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
              >
                <X className="size-4" />
              </button>
            </div>

            <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4 px-5 pb-5 pt-4">
              <div className="flex flex-col gap-1">
                <label htmlFor="adlink-name" className="text-sm font-medium text-foreground/80">
                  {t("advertising.create.nameLabel")}
                </label>
                <input
                  id="adlink-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className={fieldClassName}
                />
              </div>

              <div className="flex flex-col gap-1">
                <label htmlFor="adlink-code" className="text-sm font-medium text-foreground/80">
                  {t("advertising.create.codeLabel")}
                </label>
                <div className="flex gap-2">
                  <input
                    id="adlink-code"
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    placeholder={t("advertising.create.codePlaceholder")}
                    className={`${fieldClassName} flex-1 font-mono`}
                  />
                  {canGenerateCode && (
                    <motion.button
                      type="button"
                      onClick={() => void handleGenerate()}
                      {...bounceTap(bounceStrength)}
                      className="flex shrink-0 items-center gap-1.5 rounded-full border border-border px-3 text-[12.5px] font-medium text-foreground/90 transition-colors hover:bg-white/5"
                    >
                      <Dices className="size-3.5" />
                      {t("advertising.create.generate")}
                    </motion.button>
                  )}
                </div>
              </div>

              <div className="flex gap-3">
                <div className="flex flex-1 flex-col gap-1">
                  <label htmlFor="adlink-cost" className="text-sm font-medium text-foreground/80">
                    {t("advertising.create.costLabel")}
                  </label>
                  <input
                    id="adlink-cost"
                    type="number"
                    min={0}
                    step="0.01"
                    value={cost}
                    onChange={(event) => setCost(event.target.value)}
                    className={fieldClassName}
                  />
                </div>
                <div className="flex flex-1 flex-col gap-1">
                  <span className="text-sm font-medium text-foreground/80">{t("advertising.create.currencyLabel")}</span>
                  <SelectDropdown
                    id="adlink-currency"
                    value={currency}
                    onChange={setCurrency}
                    icon={Filter}
                    placeholder={currency}
                    options={CURRENCIES.map((value) => ({ value, label: value }))}
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label htmlFor="adlink-note" className="text-sm font-medium text-foreground/80">
                  {t("advertising.create.noteLabel")}
                </label>
                <textarea
                  id="adlink-note"
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  rows={2}
                  className={`${fieldClassName} resize-none`}
                />
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
                >
                  {t("advertising.create.cancel")}
                </button>
                <motion.button
                  type="submit"
                  disabled={isSubmitting}
                  {...bounceTap(bounceStrength)}
                  className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {isSubmitting ? t("advertising.create.saving") : t("advertising.create.save")}
                </motion.button>
              </div>
            </form>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    </DialogPortal>
  );
}
