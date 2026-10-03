import { BarChart3, CalendarClock, Check, Copy, Hash, Pause, Pencil, Play, Repeat, ShieldCheck, Ticket, Trash2, Users } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { AddOnListItem } from "@entities/addons/api";
import type { Plan } from "@entities/plans/api";
import { type Promocode, deletePromocode, updatePromocode } from "@entities/promocodes/api";
import {
  describeReward,
  getPromocodeStatus,
  limitsDraftOf,
  limitsToPayload,
  PROMOCODE_STATUS_BADGE_TONE,
  REWARD_TYPE_ICON,
} from "@entities/promocodes/display";
import { PromocodeLimitsFields } from "@entities/promocodes/PromocodeLimitsFields";
import { usePermissions } from "@entities/user/use-current-user";
import { PromocodeUsersList } from "@features/promocode-details/PromocodeUsersList";
import { getErrorMessage } from "@shared/api/http";
import { copyToClipboard } from "@shared/lib/clipboard";
import { toast } from "@shared/lib/toast";
import { useMeasuredHeight } from "@shared/lib/use-measured-height";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { InfoRow } from "@shared/ui/InfoRow";
import { KpiTile } from "@shared/ui/KpiTile";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Badge } from "@shared/ui/Badge";
import { Card } from "@shared/ui/Card";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { IconButton } from "@shared/ui/IconButton";
import { formatDate } from "@shared/lib/relative-time";

type PromocodeDetailsTab = "overview" | "users" | "settings";

const COPIED_RESET_MS = 1500;
const FORM_ID = "promocode-settings-form";

interface PromocodeDetailsDialogProps {
  promocode: Promocode;
  /** all-time activations; undefined while the summary is unavailable */
  usedCount?: number;
  addons: AddOnListItem[];
  plans: Plan[];
  onSaved?: (promocode: Promocode) => void;
  /** deleted from the footer; the dialog closes itself */
  onDeleted?: (promocode: Promocode) => void;
  onClose: () => void;
}

export function PromocodeDetailsDialog({ onClose, ...props }: PromocodeDetailsDialogProps) {
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <PromocodeDetailsDialogBody {...props} />
    </Modal>
  );
}

function PromocodeDetailsDialogBody({
  promocode: initialPromocode,
  usedCount,
  addons,
  plans,
  onSaved,
  onDeleted,
}: Omit<PromocodeDetailsDialogProps, "onClose">) {
  const { t, i18n } = useTranslation();
  const close = useModalClose();
  const permissions = usePermissions();
  const canViewUsers = permissions.includes("PROMOCODES_USERS_VIEW");
  const canUpdate = permissions.includes("PROMOCODES_UPDATE");
  const canDelete = permissions.includes("PROMOCODES_DELETE");
  const [promocode, setPromocode] = useState(initialPromocode);
  const [isConfirmingDelete, setIsConfirmingDelete] = useState(false);
  const [tab, setTab] = useState<PromocodeDetailsTab>("overview");
  const [contentRef, contentHeight] = useMeasuredHeight();
  const [isCopied, setIsCopied] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [limits, setLimits] = useState(() => limitsDraftOf(promocode));

  const status = getPromocodeStatus(promocode);
  const RewardIcon = REWARD_TYPE_ICON[promocode.reward_type];
  const none = t("common.none");

  const tabs: DialogTabItem<PromocodeDetailsTab>[] = [
    { key: "overview", label: t("promocodes.details.tabs.overview"), icon: BarChart3 },
    ...(canViewUsers ? [{ key: "users" as const, label: t("promocodes.details.tabs.users"), icon: Users }] : []),
    ...(canUpdate ? [{ key: "settings" as const, label: t("promocodes.details.tabs.settings"), icon: Pencil }] : []),
  ];

  const handleCopy = () => {
    void copyToClipboard(promocode.code).then((copied) => {
      if (!copied) return;
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), COPIED_RESET_MS);
    });
  };

  const saved = (updated: Promocode) => {
    setPromocode(updated);
    onSaved?.(updated);
  };

  const handleDelete = async () => {
    try {
      await deletePromocode(promocode.id);
      onDeleted?.(promocode);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.delete.error")));
    }
  };

  const handleToggleActive = async () => {
    setIsToggling(true);
    try {
      saved(await updatePromocode(promocode.id, { is_active: !promocode.is_active }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.edit.error")));
    } finally {
      setIsToggling(false);
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const limitsPayload = limitsToPayload(limits);
    if (limitsPayload === undefined) {
      toast.error(t("errors.invalidNumber"));
      return;
    }
    setIsSubmitting(true);
    try {
      saved(await updatePromocode(promocode.id, limitsPayload));
      toast.success(t("promocodes.edit.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  const expires = promocode.expires_at
    ? formatDate(promocode.expires_at, i18n.language)
    : t("promocodes.noExpiry");

  return (
    <>
      <DialogHeader
        icon={Ticket}
        tone={status === "ACTIVE" ? "primary" : "muted"}
        title={<span className="font-mono">{promocode.code}</span>}
        badges={
          <>
            <IconButton size="6" onClick={handleCopy}>
              {isCopied ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
            </IconButton>
            <Badge tone={PROMOCODE_STATUS_BADGE_TONE[status]}>{t(`promocodes.status.${status}`)}</Badge>
          </>
        }
        subtitle={t(`promocodes.rewardType.${promocode.reward_type}`)}
      />

      {tabs.length > 1 && (
        <div className="px-4 pt-4">
          <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
        </div>
      )}

      <div className={`scroll-fade-y min-h-0 flex-1 overflow-y-auto px-4 pb-4 ${tabs.length > 1 ? "pt-3" : "pt-4"}`}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {tab === "overview" && (
              <div className="flex flex-col gap-3">
                <div className="grid grid-cols-2 gap-3">
                  <KpiTile
                    icon={RewardIcon}
                    label={t("promocodes.sections.reward")}
                    value={describeReward(promocode, addons, plans, t)}
                    hint={t(`promocodes.availability.${promocode.availability}`)}
                  />
                  <KpiTile
                    icon={Hash}
                    label={t("promocodes.details.used")}
                    value={usedCount !== undefined ? String(usedCount) : none}
                    valueSuffix={t("promocodes.details.ofMax", { max: promocode.max_activations ?? "∞" })}
                  />
                </div>

                <Card variant="list" title={t("promocodes.sections.limits")} icon={ShieldCheck}>
                  <InfoRow icon={Users} label={t("promocodes.details.availability")}>
                    <span className="truncate">{t(`promocodes.availability.${promocode.availability}`)}</span>
                  </InfoRow>
                  <InfoRow icon={CalendarClock} label={t("promocodes.details.expires")}>
                    <span className="truncate">{expires}</span>
                  </InfoRow>
                  <InfoRow icon={Repeat} label={t("promocodes.details.reusable")}>
                    {promocode.is_reusable ? t("common.yes") : t("common.no")}
                  </InfoRow>
                </Card>
              </div>
            )}
            {tab === "users" && <PromocodeUsersList promocode={promocode} />}
            {tab === "settings" && (
              <form id={FORM_ID} onSubmit={(event) => void handleSubmit(event)}>
                <PromocodeLimitsFields idPrefix="promo-edit" value={limits} onChange={setLimits} />
              </form>
            )}
          </div>
        </motion.div>
      </div>

      {tab === "settings" && (
        <div className="flex items-center justify-between gap-2 border-t border-white/[0.07] px-5 py-4">
          <div className="flex gap-2">
            {canDelete && (
              <Button
                variant="danger"
                type="button"
                onClick={() => setIsConfirmingDelete(true)}
              >
                <Trash2 className="size-3.5" />
                {t("common.delete")}
              </Button>
            )}
            <Button variant="outline" onClick={() => void handleToggleActive()} disabled={isToggling}>
              {promocode.is_active ? <Pause className="size-3.5" /> : <Play className="size-3.5" />}
              {promocode.is_active ? t("promocodes.pause") : t("promocodes.resume")}
            </Button>
          </div>
          <Button variant="accent" type="submit" form={FORM_ID} disabled={isSubmitting}>
            {isSubmitting ? t("common.saving") : t("common.save")}
          </Button>
        </div>
      )}
      {isConfirmingDelete && (
        <ConfirmDialog
          title={t("promocodes.delete.title")}
          message={t("promocodes.delete.confirm", { code: promocode.code })}
          confirmLabel={t("common.delete")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            setIsConfirmingDelete(false);
            void handleDelete();
          }}
          onCancel={() => setIsConfirmingDelete(false)}
        />
      )}
    </>
  );
}
