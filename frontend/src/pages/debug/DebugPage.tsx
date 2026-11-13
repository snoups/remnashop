import { useMemo } from "react";

import { DebugNav, DebugShell } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { ButtonsSection, IconButtonsSection } from "@pages/debug/sections/ButtonSections";
import { CardsSection, FieldsSection, TablesSection } from "@pages/debug/sections/FormSections";
import { DialogsSection, HintsSection, MenusSection, StatesSection } from "@pages/debug/sections/OverlaySections";
import { OverviewSection } from "@pages/debug/sections/OverviewSections";
import { ScreensSection } from "@pages/debug/sections/ScreenSections";
import { BadgesSection, TabsSection } from "@pages/debug/sections/SelectionSections";
import { TypographySection } from "@pages/debug/sections/TypographySection";

const SECTION_IDS = [
  "typography",
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
  "screens",
  "overview",
] as const;

// Opened from the debug bar: every shared UI primitive, live, grouped like the codebase uses them.
export function DebugKitPage() {
  const k = useKit();
  const links = useMemo(() => SECTION_IDS.map((id) => ({ id, label: k(`sections.${id}.nav`) })), [k]);

  return (
    <DebugShell bar={<DebugNav links={links} />}>
      <div className="flex items-baseline justify-between gap-4 px-1">
        <p className="text-xs text-muted-foreground">{k("intro.caption")}</p>
        <span className="shrink-0 font-mono text-xs text-muted-foreground">{k("intro.meta")}</span>
      </div>

      <TypographySection />
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
      <ScreensSection />
      <OverviewSection />
    </DebugShell>
  );
}
