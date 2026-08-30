import { AlertTriangle, Clock, Eye, Globe, KeyRound, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { createApiToken, type CreatedApiToken } from "@entities/api-tokens/api";
import { usePermissionCatalog } from "@entities/admin/permission-catalog";
import { getErrorMessage } from "@shared/api/http";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { toast } from "@shared/lib/toast";
import { DialogPortal } from "@shared/ui/DialogPortal";
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

export function CreateApiTokenDialog({ onCreated, onCancel }: CreateApiTokenDialogProps) {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
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
        name,
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
          onClick={onCancel}
        />

        <motion.div
          initial={{ opacity: 0, scale: 0.94, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.94, y: 8 }}
          transition={{ duration: 0.18, ease: "easeOut" }}
          className="relative z-50 flex max-h-[85vh] w-full max-w-lg flex-col rounded-dialog border border-white/[0.14] bg-popover/60 shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_0_1px_0_rgba(232,236,251,0.16)] backdrop-blur-2xl backdrop-saturate-150"
        >
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="flex items-center gap-2.5 text-base font-bold text-foreground">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.05] text-foreground backdrop-blur-md">
                <KeyRound className="size-4" />
              </div>
              {t("apiTokens.createTitle")}
            </h2>
            <button
              type="button"
              onClick={onCancel}
              aria-label={t("apiTokens.cancel")}
              className="flex size-8 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-white/[0.06] hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>

          <div className="mx-5 mt-4 flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2.5">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
            <p className="text-[12px] leading-snug text-warning">{t("apiTokens.createNotice")}</p>
          </div>

          <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-1 flex-col overflow-y-auto">
            <div className="flex gap-2 px-5 pt-4">
              <div className="flex-1">
                <label className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("apiTokens.nameLabel")}
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder={t("apiTokens.namePlaceholder")}
                  className="mt-1.5 w-full rounded-full border border-border bg-white/[0.04] px-4 py-2 text-sm text-foreground outline-none focus:border-primary"
                />
              </div>

              <div className="w-44 shrink-0">
                <label className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("apiTokens.lifetimeLabel")}
                </label>
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

            <div className="mt-4 flex items-center gap-2 px-5">
              <button
                type="button"
                onClick={applyReadOnly}
                className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-[12px] font-medium text-foreground/80 transition-colors hover:bg-white/5"
              >
                <Eye className="size-3.5" />
                {t("apiTokens.readOnly")}
              </button>
              <button
                type="button"
                onClick={applyFullAccess}
                className="flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-[12px] font-medium text-foreground/80 transition-colors hover:bg-white/5"
              >
                <Globe className="size-3.5" />
                {t("apiTokens.fullAccess")}
              </button>
            </div>

            <div className="mt-3 px-5">
              <div className="pb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t("apiTokens.permissionsLabel")}
              </div>
              <PermissionPicker mode="single" selected={permissions} onToggle={togglePermission} />
            </div>

            <div className="flex gap-2 px-5 pb-5 pt-4">
              <button
                type="button"
                onClick={onCancel}
                className="flex-1 rounded-full border border-border px-4 py-2 text-sm font-medium text-foreground/80 transition-colors hover:bg-white/5"
              >
                {t("apiTokens.cancel")}
              </button>
              <motion.button
                type="submit"
                disabled={isSubmitting || name.trim().length === 0}
                {...bounceTap(bounceStrength)}
                className="flex-1 rounded-full bg-accent px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t("apiTokens.submit")}
              </motion.button>
            </div>
          </form>
        </motion.div>
      </motion.div>
    </AnimatePresence>
    </DialogPortal>
  );
}
