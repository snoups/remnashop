import { FlaskConical, LayoutGrid } from "lucide-react";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Outlet, useMatch } from "react-router-dom";

import { DebugNav } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { ButtonsSection, IconButtonsSection } from "@pages/debug/sections/ButtonSections";
import { CardsSection, FieldsSection, TablesSection } from "@pages/debug/sections/FormSections";
import { DialogsSection, HintsSection, MenusSection, StatesSection } from "@pages/debug/sections/OverlaySections";
import { BadgesSection, TabsSection } from "@pages/debug/sections/SelectionSections";
import { useBounceStrength } from "@shared/lib/bounceState";
import { TabBar } from "@shared/ui/TabBar";
import type { TabBarItem } from "@shared/ui/TabBar";

const SECTION_IDS = [
  "buttons",
  "icons",
  "tabs",
  "badges",
  "fields",
  "cards",
  "tables",
  "dialogs",
  "hints",
  "menus",
  "states",
] as const;

export function DebugPage() {
  const { t } = useTranslation();
  const bounceStrength = useBounceStrength();
  const isKitActive = useMatch({ path: "/dashboard/debug", end: true }) !== null;
  const isVariantsActive = useMatch("/dashboard/debug/variants") !== null;

  const items: TabBarItem[] = [
    { key: "kit", to: "", end: true, icon: LayoutGrid, label: t("debugPage.tabs.kit"), isActive: isKitActive },
    { key: "variants", to: "variants", icon: FlaskConical, label: t("debugPage.tabs.variants"), isActive: isVariantsActive },
  ];

  return (
    <div>
      <TabBar items={items} bounceStrength={bounceStrength} />
      <div className="mt-6">
        <Outlet />
      </div>
    </div>
  );
}

// Opened from the debug bar: every shared UI primitive, live, grouped like the codebase uses them.
export function DebugKitPage() {
  const k = useKit();
  const links = useMemo(() => SECTION_IDS.map((id) => ({ id, label: k(`sections.${id}.nav`) })), [k]);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-[21px] font-bold tracking-tight text-foreground">{k("intro.title")}</h1>
          <p className="text-[12.5px] text-muted-foreground">{k("intro.caption")}</p>
        </div>
        <span className="shrink-0 font-mono text-[11.5px] text-muted-foreground">{k("intro.meta")}</span>
      </div>

      <DebugNav links={links} ariaLabel={k("intro.nav")} />

      <ButtonsSection />
      <IconButtonsSection />
      <TabsSection />
      <BadgesSection />
      <FieldsSection />
      <CardsSection />
      <TablesSection />
      <DialogsSection />
      <HintsSection />
      <MenusSection />
      <StatesSection />
    </div>
  );
}
