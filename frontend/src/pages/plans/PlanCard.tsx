import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowDownUp, ChevronDown, Gift, Package, Smartphone } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";

import type { Plan, PlanAvailability } from "@entities/plans/api";
import { planDiscountStatus } from "@entities/plans/discount";
import { PlanIcon } from "@entities/plans/PlanIcon";
import { formatBytes, formatMoney } from "@shared/lib/format";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { Badge } from "@shared/ui/Badge";
import { CardPill } from "@shared/ui/CardPill";
import { IconButton } from "@shared/ui/IconButton";

const RESTRICTED_AVAILABILITIES: ReadonlySet<PlanAvailability> = new Set(["INVITED", "ALLOWED", "LINK"]);
const CARD_HEIGHT_CLASSNAME = "aspect-[1.4]";

export function PlanCard({
  plan,
  anchorCurrency,
  sortable,
  menuItems,
}: {
  plan: Plan;
  anchorCurrency: string | null;
  sortable: boolean;
  menuItems: ActionMenuItem[];
}) {
  const { t, i18n } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: plan.id,
    disabled: !sortable,
  });

  const durations = plan.durations.slice().sort((a, b) => a.order_index - b.order_index);
  const cheapest = durations.reduce<(typeof durations)[number] | null>(
    (min, d) => (min === null || Number(d.base_price) < Number(min.base_price) ? d : min),
    null,
  );
  const isRestricted = RESTRICTED_AVAILABILITIES.has(plan.availability);
  const discountStatus = planDiscountStatus(plan);
  const DefaultIcon = plan.is_trial ? Gift : Package;

  return (
    <article
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      {...attributes}
      {...listeners}
      className={`relative grid min-w-0 ${sortable ? "cursor-grab select-none [-webkit-touch-callout:none] active:cursor-grabbing" : ""} ${CARD_HEIGHT_CLASSNAME} rounded-3xl ${plan.badge ? "ring-1 ring-primary/30" : ""} ${isDragging ? "z-10 shadow-2xl shadow-black/50" : ""}`}
    >
      <div
        className={`glass-panel flex min-w-0 flex-col overflow-hidden rounded-3xl ${
          plan.is_active ? "text-foreground" : "text-muted-foreground"
        }`}
      >
        <div className="flex flex-1 flex-col gap-4 px-6 pt-4 pb-6">
          <div className="flex items-center gap-2">
            <div className="flex min-w-0 flex-1 items-center gap-1.5 text-sm font-semibold">
              <PlanIcon icon={plan} size={16} fallback={<DefaultIcon className="size-4 shrink-0" />} />
              <span className="truncate">{plan.name}</span>
              {plan.is_trial ? (
                <Badge borderless tone="warning">{t("plans.trialBadge")}</Badge>
              ) : (
                plan.badge && <Badge borderless tone="accent">{t(`plans.edit.badges.${plan.badge}`)}</Badge>
              )}
            </div>
            <div className="-mr-2 flex shrink-0 items-center">
              <IconButton size="8" onClick={() => setIsExpanded((open) => !open)} propagate={{ tap: false }}>
                <ChevronDown className={`size-4 transition-transform ${isExpanded ? "rotate-180" : ""}`} />
              </IconButton>
              {menuItems.length > 0 && <ActionMenu glass items={menuItems} />}
            </div>
          </div>

          {isExpanded ? (
            <div className="mt-auto grid grid-cols-2 gap-2">
              <DetailTile label={t("plans.codeLabel")} mono>
                {plan.public_code}
              </DetailTile>
              <DetailTile
                label={t("plans.access.availabilitySection")}
                className={isRestricted ? "text-violet-300" : undefined}
              >
                {t(`plans.access.availability.${plan.availability}`)}
              </DetailTile>
              <DetailTile label={t("plans.edit.tagLabel")} mono>
                {plan.tag ?? t("common.none")}
              </DetailTile>
              <DetailTile
                label={t("plans.discount.percentLabel")}
                className={discountStatus === "active" ? "text-success" : undefined}
              >
                {discountStatus
                  ? `${t("plans.discount.badge", { percent: plan.discount_percent })}${
                      discountStatus !== "active" ? ` · ${t(`plans.discount.status.${discountStatus}`)}` : ""
                    }`
                  : t("common.none")}
              </DetailTile>
            </div>
          ) : (
            <>
              <div className="mt-auto flex flex-col gap-1.5">
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <span className="min-w-0 break-words text-[26px] font-semibold leading-tight tracking-tight tabular-nums">
                    {durations.length > 1 && <span className="mr-1.5 text-[13px] font-medium text-muted-foreground">{t("plans.priceFrom")}</span>}
                    {cheapest
                      ? anchorCurrency
                        ? formatMoney(cheapest.base_price, anchorCurrency, i18n.language)
                        : new Intl.NumberFormat(i18n.language).format(Number(cheapest.base_price))
                      : t("common.none")}
                  </span>
                  {cheapest && (
                    <span className="text-[12px] text-muted-foreground">{t("plans.perDays", { count: cheapest.days })}</span>
                  )}
                </div>
                <div className="truncate text-[12px] text-muted-foreground">
                  {durations.length > 0
                    ? durations.map((d) => t("plans.daysShort", { count: d.days })).join(" · ")
                    : "\u00a0"}
                </div>
              </div>

              <div className="flex flex-wrap gap-2">
                <CardPill
                  icon={ArrowDownUp}
                  value={plan.traffic_limit === 0 ? "∞" : formatBytes(plan.traffic_limit * 1024 ** 3, i18n.language)}
                />
                <CardPill
                  icon={Smartphone}
                  value={plan.device_limit === 0 ? "∞" : t("plans.devices", { count: plan.device_limit })}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </article>
  );
}

function DetailTile({
  label,
  mono = false,
  className = "text-foreground",
  children,
}: {
  label: string;
  mono?: boolean;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 rounded-xl bg-white/[0.04] px-2.5 py-2">
      <span className="text-[11px] text-muted-foreground">{label}</span>
      <span className={`truncate text-[12.5px] ${mono ? "font-mono tracking-[0.08em]" : ""} ${className}`}>{children}</span>
    </div>
  );
}
