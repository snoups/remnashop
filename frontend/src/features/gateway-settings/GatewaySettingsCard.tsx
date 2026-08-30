import { ChevronDown, CreditCard } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import {
  toggleGatewayActive,
  updateGatewaySettings,
  type Gateway,
  type GatewayFieldSpec,
} from "@entities/gateways/api";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Switch } from "@shared/ui/Switch";

interface GatewaySettingsCardProps {
  gateway: Gateway;
  fields: GatewayFieldSpec[];
  onChanged: (gateway: Gateway) => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
}

function inputTypeFor(kind: GatewayFieldSpec["kind"]): string {
  if (kind === "secret") return "password";
  if (kind === "number") return "number";
  return "text";
}

export function GatewaySettingsCard({
  gateway,
  fields,
  onChanged,
  onMoveUp,
  onMoveDown,
}: GatewaySettingsCardProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isToggling, setIsToggling] = useState(false);

  const label = t(`settings.gateways.types.${gateway.type}`);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const changed = Object.fromEntries(
      Object.entries(values).filter(([, value]) => value !== ""),
    );
    if (Object.keys(changed).length === 0) {
      toast.error(t("settings.gateways.errorEmptyFields"));
      return;
    }

    setIsSubmitting(true);
    try {
      const updated = await updateGatewaySettings(gateway.type, changed);
      onChanged(updated);
      setValues({});
      toast.success(t("settings.gateways.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("auth.errors.genericError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      const updated = await toggleGatewayActive(gateway.type);
      onChanged(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("settings.gateways.toggleError")));
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4">
      <div className="flex items-center gap-2.5">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
          <CreditCard className="size-4" />
        </div>
        <div
          role="button"
          tabIndex={0}
          onClick={() => setIsOpen((open) => !open)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            setIsOpen((open) => !open);
          }}
          className="min-w-0 flex-1 cursor-pointer"
        >
          <p className="text-sm font-bold text-foreground">{label}</p>
          <p className="text-[12px]">
            {gateway.is_configured ? (
              <span className="text-success">{t("settings.gateways.configured")}</span>
            ) : (
              <span className="text-warning">{t("settings.gateways.notConfigured")}</span>
            )}
          </p>
        </div>
        <div className="flex flex-col text-muted-foreground">
          <button
            type="button"
            onClick={onMoveUp}
            disabled={!onMoveUp}
            aria-label={t("settings.gateways.moveUp")}
            className="disabled:opacity-30"
          >
            <span aria-hidden>&#9650;</span>
          </button>
          <button
            type="button"
            onClick={onMoveDown}
            disabled={!onMoveDown}
            aria-label={t("settings.gateways.moveDown")}
            className="disabled:opacity-30"
          >
            <span aria-hidden>&#9660;</span>
          </button>
        </div>
        {fields.length > 0 && (
          <span className="flex size-6 shrink-0 items-center justify-center">
            <ChevronDown
              className={`size-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`}
            />
          </span>
        )}
        <Switch
          checked={gateway.is_active}
          onChange={() => void handleToggle()}
          disabled={isToggling || !gateway.is_configured}
          ariaLabel={t("settings.gateways.enableAria", { gateway: label })}
        />
      </div>

      <AnimatePresence initial={false}>
        {isOpen && fields.length > 0 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <form
              onSubmit={(event) => void handleSubmit(event)}
              className="flex flex-col gap-3 px-[12.5px] pb-2 pt-3"
            >
              {fields.map((field) => (
                <div key={field.key} className="flex flex-col gap-1">
                  <label className="text-sm font-medium text-foreground/80">
                    {t(`settings.gateways.fields.${gateway.type}.${field.key}`)}
                  </label>
                  <input
                    type={inputTypeFor(field.kind)}
                    value={values[field.key] ?? ""}
                    onChange={(event) =>
                      setValues((prev) => ({ ...prev, [field.key]: event.target.value }))
                    }
                    placeholder={t("settings.gateways.placeholder")}
                    autoComplete="off"
                    className="rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                  />
                </div>
              ))}
              <button
                type="submit"
                disabled={isSubmitting}
                className="mt-1 w-fit rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSubmitting ? t("settings.gateways.saving") : t("settings.gateways.save")}
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
