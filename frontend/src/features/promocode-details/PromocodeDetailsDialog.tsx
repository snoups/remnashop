import { CalendarClock, CalendarDays, Check, Copy, Info, Package, Pause, Pencil, Play, Repeat, Settings2, ShieldCheck, Ticket, TicketCheck, Trash2, UserCheck, Users } from "lucide-react";
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
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { DialogTabs, type DialogTabItem } from "@shared/ui/DialogTabs";
import { InfoRow } from "@shared/ui/InfoRow";
import { Modal } from "@shared/ui/Modal";
import { GLASS_DIALOG_BODY_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Badge } from "@shared/ui/Badge";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { IconButton } from "@shared/ui/IconButton";
import { formatDate } from "@shared/lib/relative-time";

type PromocodeDetailsTab = "overview" | "users";

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
  const [isEditing, setIsEditing] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [limits, setLimits] = useState(() => limitsDraftOf(promocode));

  const status = getPromocodeStatus(promocode);
  const RewardIcon = REWARD_TYPE_ICON[promocode.reward_type];

  const tabs: DialogTabItem<PromocodeDetailsTab>[] = [
    { key: "overview", label: t("promocodes.details.tabs.details"), icon: Info },
    ...(canViewUsers ? [{ key: "users" as const, label: t("promocodes.details.tabs.users"), icon: Users }] : []),
  ];
  const menuItems: ActionMenuItem[] = [
    ...(canUpdate
      ? [
          {
            label: t("common.edit"),
            icon: Pencil,
            onClick: () => {
              setLimits(limitsDraftOf(promocode));
              setIsEditing(true);
            },
          },
          {
            label: promocode.is_active ? t("promocodes.pause") : t("promocodes.resume"),
            icon: promocode.is_active ? Pause : Play,
            onClick: () => void handleToggleActive(),
          },
        ]
      : []),
    ...(canDelete
      ? [
          {
            label: t("common.delete"),
            icon: Trash2,
            onClick: () => setIsConfirmingDelete(true),
            variant: "danger" as const,
            separatorBefore: canUpdate,
          },
        ]
      : []),
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
    try {
      saved(await updatePromocode(promocode.id, { is_active: !promocode.is_active }));
    } catch (err) {
      toast.error(getErrorMessage(err, t("promocodes.edit.error")));
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
      setIsEditing(false);
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
            <Badge tone={PROMOCODE_STATUS_BADGE_TONE[status]}>{t(`promocodes.status.${status}`)}</Badge>
            <IconButton size="9" onClick={handleCopy}>
              {isCopied ? <Check className="size-4 text-primary" /> : <Copy className="size-4" />}
            </IconButton>
          </>
        }
      />

      {tabs.length > 1 && !isEditing && (
        <div className="px-3 pt-3">
          <DialogTabs items={tabs} activeKey={tab} onSelect={setTab} />
        </div>
      )}

      <div className={GLASS_DIALOG_BODY_CLASS}>
        <motion.div
          animate={{ height: contentHeight }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="overflow-hidden"
        >
          <div ref={contentRef}>
            {!isEditing && tab === "overview" && (
              <div className="flex flex-col gap-3">
                <DialogCard title={t("promocodes.details.promocode")} icon={Ticket}>
                  <InfoRow icon={RewardIcon} label={t("promocodes.sections.reward")}>
                    <span className="truncate">{describeReward(promocode, addons, plans, t)}</span>
                  </InfoRow>
                  <InfoRow icon={TicketCheck} label={t("promocodes.details.used")}>
                    {promocode.activations_count} {t("promocodes.details.ofMax", { max: promocode.max_activations ?? "∞" })}
                  </InfoRow>
                  {promocode.created_at && (
                    <InfoRow icon={CalendarDays} label={t("promocodes.details.createdAt")} mono>
                      {formatDate(promocode.created_at, i18n.language)}
                    </InfoRow>
                  )}
                </DialogCard>

                <DialogCard title={t("promocodes.sections.limits")} icon={ShieldCheck}>
                  <InfoRow icon={Users} label={t("promocodes.details.availability")}>
                    <span className="truncate">{t(`promocodes.availability.${promocode.availability}`)}</span>
                  </InfoRow>
                  {promocode.availability === "ALLOWED" && (
                    <InfoRow icon={UserCheck} label={t("promocodes.limits.allowedUserIdsLabel")} mono>
                      <span className="truncate">
                        {promocode.allowed_user_ids.map((id) => `#${id}`).join(", ") || t("common.none")}
                      </span>
                    </InfoRow>
                  )}
                  {PLAN_LIMITED_REWARDS.includes(promocode.reward_type) && (
                    <InfoRow icon={Package} label={t("promocodes.details.plans")}>
                      <span className="truncate">
                        {promocode.allowed_plan_ids.length > 0
                          ? promocode.allowed_plan_ids
                              .map((id) => plans.find((plan) => plan.id === id)?.name ?? `#${id}`)
                              .join(", ")
                          : t("promocodes.limits.plansAll")}
                      </span>
                    </InfoRow>
                  )}
                  <InfoRow icon={CalendarClock} label={t("promocodes.details.expires")}>
                    <span className="truncate">{expires}</span>
                  </InfoRow>
                  <InfoRow icon={Repeat} label={t("promocodes.details.reusable")}>
                    {promocode.is_reusable ? t("common.yes") : t("common.no")}
                  </InfoRow>
                </DialogCard>
              </div>
            )}
            {!isEditing && tab === "users" && <PromocodeUsersList promocode={promocode} />}
            {isEditing && (
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

      {isEditing ? (
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} items-center justify-end`}>
          <Button variant="glass" type="button" onClick={() => setIsEditing(false)}>
            {t("common.cancel")}
          </Button>
          <Button variant="glassAccent" type="submit" form={FORM_ID} isLoading={isSubmitting}>
            {t("common.save")}
          </Button>
        </div>
      ) : (
        menuItems.length > 0 && (
          <div className={`${GLASS_DIALOG_FOOTER_CLASS} items-center`}>
            <div className="ml-auto">
              <ActionMenu trigger={{ label: t("users.details.actions"), icon: Settings2 }} items={menuItems} />
            </div>
          </div>
        )
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
