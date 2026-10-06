import { AlertTriangle, Clock, Eye, Globe, KeyRound, Megaphone } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { createApiToken, type CreatedApiToken } from "@entities/api-tokens/api";
import { toTokenScopes } from "@entities/api-tokens/scopes";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import type { Permission } from "@shared/types/rbac";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { TextInput } from "@shared/ui/TextInput";
import { Field } from "@shared/ui/Field";

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
  { value: "30", labelKey: "apiTokens.expiresIn30Days" },
  { value: "90", labelKey: "apiTokens.expiresIn90Days" },
  { value: "180", labelKey: "apiTokens.expiresIn180Days" },
  { value: "365", labelKey: "apiTokens.expiresIn365Days" },
] as const;

// what an external marketing page needs to render plans and prices
const LANDING_PERMISSIONS: readonly Permission[] = ["PLANS_VIEW", "ADDONS_VIEW", "PRICING_VIEW"];

const labelClassName = "text-sm font-medium text-foreground/80";
export function CreateApiTokenDialog({ onCreated, onCancel }: CreateApiTokenDialogProps) {
  return (
    <Modal onClose={onCancel} size="lg" scrollable>
      <CreateApiTokenDialogBody onCreated={onCreated} />
    </Modal>
  );
}

function CreateApiTokenDialogBody({ onCreated }: Pick<CreateApiTokenDialogProps, "onCreated">) {
  const { t } = useTranslation();
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
    const full = new Set(
      catalogState.data.filter((entry) => entry.token_grantable).map((entry) => entry.permission),
    );
    setPermissions((prev) => (setsEqual(prev, full) ? new Set() : full));
  };

  const applyReadOnly = () => {
    if (catalogState.kind !== "ready") return;
    const readOnly = new Set(
      catalogState.data
        .filter((entry) => entry.token_grantable && entry.kind === "read")
        .map((entry) => entry.permission),
    );
    setPermissions((prev) => (setsEqual(prev, readOnly) ? new Set() : readOnly));
  };

  const applyLanding = () => {
    const landing = new Set(LANDING_PERMISSIONS);
    setPermissions((prev) => (setsEqual(prev, landing) ? new Set() : landing));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (catalogState.kind !== "ready") return;
    setIsSubmitting(true);
    try {
      const created = await createApiToken(
        name.trim(),
        toTokenScopes(permissions, catalogState.data),
        Number(expiresInDays),
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
      <DialogHeader icon={KeyRound} title={t("apiTokens.createTitle")} />

      <form onSubmit={(event) => void handleSubmit(event)} className="flex min-h-0 flex-1 flex-col">
        <div className="scroll-fade-y flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-4">
          <div className="flex items-start gap-2 rounded-xl border border-warning/30 bg-warning/10 px-3 py-2.5">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
            <p className="text-[12px] leading-snug text-warning">{t("apiTokens.createNotice")}</p>
          </div>

          <Card variant="form">
            <div className="flex gap-2">
              <Field label={t("apiTokens.nameLabel")} htmlFor="api-token-name" required className="flex-1">
                <TextInput
                  id="api-token-name"
                  type="text"
                  required
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder={t("apiTokens.namePlaceholder")}
                  className="mt-1 w-full"
                />
              </Field>

              <Field label={t("apiTokens.lifetimeLabel")} htmlFor="api-token-expiry" className="w-44 shrink-0">
                <div className="mt-1">
                  <SelectDropdown
                    variant="form"
                    id="api-token-expiry"
                    value={expiresInDays}
                    onChange={setExpiresInDays}
                    icon={Clock}
                    placeholder={t("apiTokens.expiresIn30Days")}
                    options={EXPIRY_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }))}
                  />
                </div>
              </Field>
            </div>
          </Card>

          <Card variant="form">
            <div className="flex items-center justify-between gap-2 pb-1.5">
              <span className={labelClassName}>{t("apiTokens.permissionsLabel")}</span>
              <div className="flex gap-1.5">
                <Button variant="secondary" size="sm" onClick={applyLanding}>
                  <Megaphone className="size-3.5" />
                  {t("apiTokens.landing")}
                </Button>
                <Button variant="secondary" size="sm" onClick={applyReadOnly}>
                  <Eye className="size-3.5" />
                  {t("apiTokens.readOnly")}
                </Button>
                <Button variant="secondary" size="sm" onClick={applyFullAccess}>
                  <Globe className="size-3.5" />
                  {t("apiTokens.fullAccess")}
                </Button>
              </div>
            </div>
            <PermissionPicker selected={permissions} onToggle={togglePermission} tokenGrantableOnly />
          </Card>
        </div>

        <div className="flex shrink-0 justify-end gap-2 border-t border-white/[0.07] px-5 py-4">
          <Button
            variant="outline"
            type="button"
            onClick={close}
          >
            {t("common.cancel")}
          </Button>
          <Button
            variant="accent"
            type="submit"
            disabled={isSubmitting || name.trim().length === 0 || permissions.size === 0}
          >
            {t("common.create")}
          </Button>
        </div>
      </form>
    </>
  );
}
