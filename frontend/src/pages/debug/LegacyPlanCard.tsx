import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ArrowDownUp, Gift, GripVertical, Package, Smartphone } from "lucide-react";
import { useTranslation } from "react-i18next";

import { BrandMark } from "@entities/appearance/BrandMark";
import type { Plan, PlanAvailability } from "@entities/plans/api";
import { PLAN_DISCOUNT_STATUS_TONE, planDiscountStatus } from "@entities/plans/discount";
import { PlanIcon } from "@entities/plans/PlanIcon";
import { formatMoney } from "@shared/lib/format";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";
import { Badge } from "@shared/ui/Badge";
import { CardPill } from "@shared/ui/CardPill";
import { Switch } from "@shared/ui/glass/Switch";
import { IconButton } from "@shared/ui/IconButton";
import { Tag } from "@shared/ui/Tag";

const RESTRICTED_AVAILABILITIES: ReadonlySet<PlanAvailability> = new Set(["INVITED", "ALLOWED", "LINK"]);
const CARD_HEIGHT_CLASSNAME = "aspect-[1.35]";

// Snapshot of the plan card before the glass-panel redesign, for visual comparison only.
export function LegacyPlanCard({
  plan,
  anchorCurrency,
  sortable,
  menuItems,
  onToggleActive,
}: {
  plan: Plan;
  anchorCurrency: string | null;
  sortable: boolean;
  menuItems: ActionMenuItem[];
  onToggleActive?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
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
      className={`relative grid ${CARD_HEIGHT_CLASSNAME} rounded-card ${plan.badge ? "ring-2 ring-primary/60" : ""} ${isDragging ? "z-10 shadow-2xl shadow-black/50" : ""}`}
    >
      <div
        className={`relative flex flex-col overflow-hidden rounded-card border border-white/[0.14] bg-white/[0.06] backdrop-blur-xl backdrop-saturate-150 ${
          plan.is_active ? "text-foreground" : "text-muted-foreground"
        }`}
      >
        <BrandMark className="pointer-events-none absolute -bottom-5 -right-5 size-36 opacity-[0.04]" />

        <div className="relative flex flex-1 flex-col gap-3 px-[18px] pb-4 pt-3">
          <div className="flex items-center gap-2">
            <div className="flex min-w-0 flex-1 items-center gap-1.5 text-sm font-semibold">
              <PlanIcon icon={plan} size={16} fallback={<DefaultIcon className="size-4 shrink-0" />} />
              <span className="truncate">{plan.name}</span>
            </div>
            <span className="shrink-0 font-mono text-[12px] tracking-[0.12em] text-muted-foreground">{plan.public_code}</span>
            <div className="-mr-2 flex shrink-0 items-center">
              {sortable && (
                <IconButton size="8" className="cursor-grab touch-none active:cursor-grabbing"
                  ref={setActivatorNodeRef}
                  {...attributes}
                  {...listeners}
                >
                  <GripVertical className="size-4" />
                </IconButton>
              )}
              {menuItems.length > 0 && <ActionMenu glass items={menuItems} />}
            </div>
          </div>

          <div className="mt-auto flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="text-[26px] font-bold leading-[1.1] tracking-tight tabular-nums">
                {cheapest && <span className="mr-1.5 text-[13px] font-medium text-muted-foreground">{t("plans.priceFrom")}</span>}
                {cheapest
                  ? anchorCurrency
                    ? formatMoney(cheapest.base_price, anchorCurrency, i18n.language)
                    : new Intl.NumberFormat(i18n.language).format(Number(cheapest.base_price))
                  : t("common.none")}
              </span>
              {cheapest && (
                <span className="min-w-0 truncate text-[13px] font-bold">{t("plans.perDays", { count: cheapest.days })}</span>
              )}
            </div>
            <div className="truncate text-[12px] text-muted-foreground">
              {durations.length > 0
                ? durations.map((d) => t("plans.daysShort", { count: d.days })).join(" · ")
                : " "}
            </div>
          </div>

          <div className="mt-1 flex gap-2">
            <CardPill
              icon={ArrowDownUp}
              label={plan.traffic_limit === 0 ? undefined : t(`plans.edit.strategy.${plan.traffic_limit_strategy}`)}
              value={plan.traffic_limit === 0 ? "∞" : `${plan.traffic_limit} GB`}
            />
            <CardPill
              icon={Smartphone}
              value={plan.device_limit === 0 ? "∞" : t("plans.devices", { count: plan.device_limit })}
            />
          </div>
        </div>

        <div className="relative flex min-h-12 items-center gap-2 bg-black/45 px-[18px] py-2">
          <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
            <Badge borderless tone={isRestricted ? "violet" : "neutral"} className="min-w-0">
              <span className="truncate">{t(`plans.access.availability.${plan.availability}`)}</span>
            </Badge>
            {plan.is_trial && <Badge borderless tone="warning">{t("plans.edit.isTrialLabel")}</Badge>}
            {plan.badge && <Badge borderless tone="accent">{t(`plans.edit.badges.${plan.badge}`)}</Badge>}
            {plan.tag && <Tag>{plan.tag}</Tag>}
            {discountStatus && (
              <Badge borderless tone={PLAN_DISCOUNT_STATUS_TONE[discountStatus]}>
                {t("plans.discount.badge", { percent: plan.discount_percent })}
                {discountStatus !== "active" && ` · ${t(`plans.discount.status.${discountStatus}`)}`}
              </Badge>
            )}
          </div>
          {onToggleActive && <Switch checked={plan.is_active} onChange={onToggleActive} />}
        </div>
      </div>
    </article>
  );
}
