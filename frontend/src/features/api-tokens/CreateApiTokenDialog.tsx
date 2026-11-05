import { AlertTriangle, Clock, Eye, Globe, KeyRound, Megaphone } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { createApiToken, type CreatedApiToken } from "@entities/api-tokens/api";
import { LANDING_PERMISSIONS, toTokenScopes } from "@entities/api-tokens/scopes";
import { usePermissionCatalog } from "@entities/admin/use-permission-catalog";
import { isIpOrNetwork, parseEntries } from "@entities/user/security";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { PermissionPicker } from "@entities/admin/PermissionPicker";
import type { Permission } from "@shared/types/rbac";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_BODY_CLASS, GLASS_DIALOG_CARD_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input, TextArea } from "@shared/ui/glass/Input";
import { SelectDropdown } from "@shared/ui/SelectDropdown";

const NAME_MAX_LENGTH = 32;

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
  const [ipText, setIpText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const ipEntries = parseEntries(ipText);
  const invalidIps = ipEntries.filter((entry) => !isIpOrNetwork(entry));

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
        ipEntries,
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
        <div className={`${GLASS_DIALOG_BODY_CLASS} flex flex-col gap-3`}>
          <div className="flex items-start gap-2 rounded-xl bg-warning/10 px-3.5 py-2.5">
            <AlertTriangle className="mt-0.5 size-4 shrink-0 text-warning" />
            <p className="text-[12px] leading-snug text-warning">{t("apiTokens.createNotice")}</p>
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <div className="flex gap-2">
              <div className="min-w-0 flex-1">
                <Field label={t("apiTokens.nameLabel")} htmlFor="api-token-name" required>
                  <Input
                    id="api-token-name"
                    maxLength={NAME_MAX_LENGTH}
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder={t("apiTokens.namePlaceholder")}
                  />
                </Field>
              </div>
              <div className="w-44 shrink-0">
                <Field label={t("apiTokens.lifetimeLabel")} htmlFor="api-token-expiry">
                  <SelectDropdown
                    id="api-token-expiry"
                    variant="well"
                    size="compact"
                    value={expiresInDays}
                    onChange={setExpiresInDays}
                    icon={Clock}
                    placeholder={t("apiTokens.expiresIn30Days")}
                    options={EXPIRY_OPTIONS.map((option) => ({ value: option.value, label: t(option.labelKey) }))}
                  />
                </Field>
              </div>
            </div>
            <Field label={t("apiTokens.presets")}>
              <div className="flex flex-wrap gap-2">
                <Button variant="glass" icon={Megaphone} className="flex-auto" onClick={applyLanding}>
                  {t("apiTokens.landing")}
                </Button>
                <Button variant="glass" icon={Eye} className="flex-auto" onClick={applyReadOnly}>
                  {t("apiTokens.readOnly")}
                </Button>
                <Button variant="glass" icon={Globe} className="flex-auto" onClick={applyFullAccess}>
                  {t("apiTokens.fullAccess")}
                </Button>
              </div>
            </Field>
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field label={t("apiTokens.permissionsLabel")}>
              <PermissionPicker selected={permissions} onToggle={togglePermission} tokenGrantableOnly />
            </Field>
          </div>

          <div className={GLASS_DIALOG_CARD_CLASS}>
            <Field
              label={t("apiTokens.ipAllowlist")}
              htmlFor="api-token-ips"
              hint={t("apiTokens.ipAllowlistHint")}
              error={
                invalidIps.length > 0
                  ? t("profile.accountSecurity.invalidEntries", { entries: invalidIps.join(", ") })
                  : undefined
              }
            >
              <TextArea
                id="api-token-ips"
                value={ipText}
                onChange={(event) => setIpText(event.target.value)}
                placeholder={t("profile.accountSecurity.placeholder")}
                spellCheck={false}
                rows={3}
                mono
                aria-invalid={invalidIps.length > 0}
              />
            </Field>
          </div>
        </div>

        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
          <Button variant="glass" onClick={close}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="glassAccent"
            type="submit"
            isLoading={isSubmitting}
            disabled={permissions.size === 0 || invalidIps.length > 0}
          >
            {t("common.create")}
          </Button>
        </div>
      </form>
    </>
  );
}
