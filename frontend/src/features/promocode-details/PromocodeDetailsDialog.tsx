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
  PLAN_LIMITED_REWARDS,
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
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Badge } from "@shared/ui/Badge";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { IconButton } from "@shared/ui/IconButton";
import { formatDate } from "@shared/lib/relative-time";

type PromocodeDetailsTab = "overview" | "users" | "settings";

const COPIED_RESET_MS = 1500;
const FORM_ID = "promocode-settings-form";

interface PromocodeDetailsDialogProps {
  promocode: Promocode;
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
    const limitsPayload = limitsToPayload(limits, promocode.reward_type);
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
        title={promocode.code}
        subtitle={t(`promocodes.rewardType.${promocode.reward_type}`)}
        actions={
          <>
            <Badge borderless tone={PROMOCODE_STATUS_BADGE_TONE[status]}>{t(`promocodes.status.${status}`)}</Badge>
            <IconButton size="9" onClick={handleCopy}>
              {isCopied ? <Check className="size-4 text-primary" /> : <Copy className="size-4" />}
            </IconButton>
          </>
        }
      />

      {tabs.length > 1 && (
        <div className="px-3 pt-3">
          <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
        </div>
      )}

      <div className="scroll-fade-y min-h-0 flex-1 overflow-y-auto p-3 [--dialog-pad:0.75rem]">
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
                    glass
                    icon={RewardIcon}
                    label={t("promocodes.sections.reward")}
                    value={describeReward(promocode, addons, plans, t)}
                  />
                  <KpiTile
                    glass
                    icon={Hash}
                    label={t("promocodes.details.used")}
                    value={String(promocode.activations_count)}
                    valueSuffix={t("promocodes.details.ofMax", { max: promocode.max_activations ?? "∞" })}
                  />
                </div>

                <DialogCard title={t("promocodes.sections.limits")} icon={ShieldCheck}>
                  <InfoRow icon={Users} label={t("promocodes.details.availability")}>
                    <span className="truncate">{t(`promocodes.availability.${promocode.availability}`)}</span>
                  </InfoRow>
                  <InfoRow icon={CalendarClock} label={t("promocodes.details.expires")}>
                    <span className="truncate">{expires}</span>
                  </InfoRow>
                  <InfoRow icon={Repeat} label={t("promocodes.details.reusable")}>
                    {promocode.is_reusable ? t("common.yes") : t("common.no")}
                  </InfoRow>
                </DialogCard>
              </div>
            )}
            {tab === "users" && <PromocodeUsersList promocode={promocode} />}
            {tab === "settings" && (
              <form id={FORM_ID} onSubmit={(event) => void handleSubmit(event)}>
                <PromocodeLimitsFields
                  idPrefix="promo-edit"
                  value={limits}
                  onChange={setLimits}
                  plans={PLAN_LIMITED_REWARDS.includes(promocode.reward_type) ? plans : undefined}
                />
              </form>
            )}
          </div>
        </motion.div>
      </div>

      {(canUpdate || canDelete) && (
        <div className="flex items-center justify-between gap-2 border-t border-white/[0.08] p-4">
          <div className="flex gap-2">
            {canDelete && (
              <Button variant="glassDanger" type="button" onClick={() => setIsConfirmingDelete(true)}>
                <Trash2 className="size-4" />
                {t("common.delete")}
              </Button>
            )}
            {canUpdate && (
              <Button variant="glass" onClick={() => void handleToggleActive()} isLoading={isToggling}>
                {promocode.is_active ? <Pause className="size-4" /> : <Play className="size-4" />}
                {promocode.is_active ? t("promocodes.pause") : t("promocodes.resume")}
              </Button>
            )}
          </div>
          {tab === "settings" && (
            <Button variant="glassAccent" type="submit" form={FORM_ID} isLoading={isSubmitting}>
              {t("common.save")}
            </Button>
          )}
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
