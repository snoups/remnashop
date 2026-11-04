import { DndContext } from "@dnd-kit/core";
import { SortableContext, rectSortingStrategy } from "@dnd-kit/sortable";
import { BadgePercent, Pencil, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Plan } from "@entities/plans/api";
import { DebugShell } from "@pages/debug/debug-ui";
import { LegacyPlanCard } from "@pages/debug/LegacyPlanCard";
import { useKit } from "@pages/debug/use-kit";
import { PlanCard } from "@pages/plans/PlanCard";
import { toast } from "@shared/lib/toast";
import type { ActionMenuItem } from "@shared/ui/ActionMenu";

const DEMO_PLAN: Plan = {
  id: 1,
  public_code: "DEMO",
  name: "",
  description: null,
  tag: "VPN",
  badge: "POPULAR",
  type: "BOTH",
  availability: "ALL",
  traffic_limit_strategy: "MONTH",
  traffic_limit: 100,
  device_limit: 5,
  allowed_telegram_ids: [],
  allowed_emails: [],
  internal_squads: [],
  external_squad: null,
  order_index: 0,
  is_active: true,
  is_trial: false,
  allow_bonus_days: true,
  allow_promocodes: true,
  discount_percent: 15,
  discount_starts_at: null,
  discount_ends_at: null,
  icon_emoji_id: null,
  icon_emoji_fallback: null,
  durations: [
    { days: 30, order_index: 0, base_price: "299", overrides: [] },
    { days: 90, order_index: 1, base_price: "799", overrides: [] },
    { days: 365, order_index: 2, base_price: "2990", overrides: [] },
  ],
};

// Live copies of markup being redesigned, beside the current one, until the new one is signed off.
export function DebugVariantsPage() {
  const k = useKit();
  const { t } = useTranslation();
  const [isActive, setIsActive] = useState(true);
  const plan = { ...DEMO_PLAN, name: k("variants.planName"), is_active: isActive };
  const previewAction = () => toast.info(k("variants.previewOnly"));
  const menuItems: ActionMenuItem[] = [
    { label: t("common.edit"), icon: Pencil, onClick: previewAction },
    { label: t("plans.access.button"), icon: ShieldCheck, onClick: previewAction },
    { label: t("plans.discount.button"), icon: BadgePercent, onClick: previewAction },
    { label: t("plans.delete.button"), icon: Trash2, variant: "danger", onClick: previewAction },
  ];

  return (
    <DebugShell>
      <p className="px-1 text-[12px] text-muted-foreground">{k("variants.caption")}</p>
      <section className="flex flex-col gap-4">
        <h2 className="px-1 text-[15px] font-semibold tracking-tight text-foreground">{k("variants.planCards")}</h2>
        <div className="grid max-w-[900px] items-start gap-5 lg:grid-cols-2">
          {(["old", "new"] as const).map((variant) => {
            const Card = variant === "old" ? LegacyPlanCard : PlanCard;
            return (
              <div key={variant} className="flex w-full min-w-0 max-w-[440px] flex-col gap-3">
                <h3 className="px-1 text-[13px] font-medium text-muted-foreground">{k(`variants.${variant}`)}</h3>
                <DndContext>
                  <SortableContext items={[plan.id]} strategy={rectSortingStrategy}>
                    <Card
                      plan={plan}
                      anchorCurrency="RUB"
                      sortable
                      menuItems={menuItems}
                      onToggleActive={() => setIsActive((value) => !value)}
                    />
                  </SortableContext>
                </DndContext>
              </div>
            );
          })}
        </div>
      </section>
    </DebugShell>
  );
}
