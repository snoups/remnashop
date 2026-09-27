import { AlertTriangle, Clock, Eye, Globe, KeyRound, X } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { createApiToken, type CreatedApiToken } from "@entities/api-tokens/api";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { Modal, useModalClose } from "@shared/ui/Modal";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import type { Permission } from "@shared/types/rbac";

interface CreateApiTokenDialogProps {
  onCreated: (created: CreatedApiToken) => void;
  onCancel: () => void;
}

function setsEqual<T>(a: Set<T>, b: Set<T>): boolean {
  if (a.size !== b.size) return false;
  for (const item of a) {
    if (!b.has(item)) return false;
  }
  return true;
}

const EXPIRY_OPTIONS = [
  { value: "", labelKey: "apiTokens.neverExpires" },
  { value: "30", labelKey: "apiTokens.expiresIn30Days" },
  { value: "90", labelKey: "apiTokens.expiresIn90Days" },
  { value: "180", labelKey: "apiTokens.expiresIn180Days" },
  { value: "365", labelKey: "apiTokens.expiresIn365Days" },
] as const;

const sectionClassName = "rounded-2xl border border-white/[0.08] bg-white/[0.03] p-4";
const labelClassName = "text-[11px] font-semibold uppercase tracking-wide text-muted-foreground";
const presetClassName =
  "flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-[12px] font-medium text-foreground/80 transition-colors hover:bg-white/5";

export function CreateApiTokenDialog({ onCreated, onCancel }: CreateApiTokenDialogProps) {
  return (
    <Modal onClose={onCancel} size="lg" scrollable>
      <CreateApiTokenDialogBody onCreated={onCreated} />
    </Modal>
  );
}

function CreateApiTokenDialogBody({ onCreated }: Pick<CreateApiTokenDialogProps, "onCreated">) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const close = useModalClose();
  const catalogState = usePermissionCatalog();
  const [name, setName] = useState("");
  const [permissions, setPermissions] = useState<Set<Permission>>(new Set());
  const [expiresInDays, setExpiresInDays] = useState("30");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const togglePermission = (permission: Permission) => {
    setPermissions((prev) => {
      const next = new Set(prev);
      if (next.has(permission)) {
        next.delete(permission);
      } else {
        next.add(permission);
      }
      return next;
    });
  };

  const applyFullAccess = () => {
    if (catalogState.kind !== "ready") return;
    const full = new Set(catalogState.data.map((entry) => entry.permission));
    setPermissions((prev) => (setsEqual(prev, full) ? new Set() : full));
  };

  const applyReadOnly = () => {
    if (catalogState.kind !== "ready") return;
    const readOnly = new Set(
      catalogState.data.filter((entry) => entry.kind === "read").map((entry) => entry.permission),
    );
    setPermissions((prev) => (setsEqual(prev, readOnly) ? new Set() : readOnly));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const created = await createApiToken(
        name.trim(),
        Array.from(permissions),
        expiresInDays === "" ? null : Number(expiresInDays),
      );
      onCreated(created);
    } catch (err) {
      toast.error(getErrorMessage(err, t("apiTokens.createError")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
        <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
            <KeyRound className="size-4" />
          </div>
          {t("apiTokens.createTitle")}
        </h2>
        <button
          type="button"
          onClick={close}
          aria-label={t("apiTokens.cancel")}
          className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      </div>

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <div className="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2.5">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
            <p className="text-[12px] leading-snug text-warning">{t("apiTokens.createNotice")}</p>
          </div>

          <section className={sectionClassName}>
            <div className="flex gap-2">
              <div className="flex-1">
                <label className={labelClassName}>{t("apiTokens.nameLabel")}</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder={t("apiTokens.namePlaceholder")}
                  className="mt-1.5 w-full rounded-xl border border-border bg-input/60 px-3 py-2 text-sm text-foreground outline-none focus:border-primary"
                />
              </div>

              <div className="w-44 shrink-0">
                <label className={labelClassName}>{t("apiTokens.lifetimeLabel")}</label>
                <div className="mt-1.5">
                  <SelectDropdown
                    id="api-token-expiry"
                    value={expiresInDays}
                    onChange={setExpiresInDays}
                    icon={Clock}
                    placeholder={t("apiTokens.neverExpires")}
                    options={EXPIRY_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }))}
                  />
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-4 pb-4 pt-3">
            <div className="flex items-center justify-between gap-2 pb-1.5">
              <span className={labelClassName}>{t("apiTokens.permissionsLabel")}</span>
              <div className="flex gap-1.5">
                <button type="button" onClick={applyReadOnly} className={presetClassName}>
                  <Eye className="size-3.5" />
                  {t("apiTokens.readOnly")}
                </button>
                <button type="button" onClick={applyFullAccess} className={presetClassName}>
                  <Globe className="size-3.5" />
                  {t("apiTokens.fullAccess")}
                </button>
              </div>
            </div>
            <PermissionPicker selected={permissions} onToggle={togglePermission} />
          </section>
        </div>

        <div className="flex shrink-0 justify-end gap-2 border-t border-white/[0.07] px-5 py-4">
          <button
            type="button"
            onClick={close}
            className="rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
          >
            {t("apiTokens.cancel")}
          </button>
          <motion.button
            type="submit"
            disabled={isSubmitting || name.trim().length === 0}
            {...bounceTap(bounceStrength)}
            className="rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("apiTokens.submit")}
          </motion.button>
        </div>
      </form>
    </>
  );
}
