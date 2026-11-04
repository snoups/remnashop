import { useMemo } from "react";

import { DebugNav, DebugShell } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { ButtonsSection, IconButtonsSection } from "@pages/debug/sections/ButtonSections";
import { CardsSection, FieldsSection, TablesSection } from "@pages/debug/sections/FormSections";
import { DialogsSection, HintsSection, MenusSection, StatesSection } from "@pages/debug/sections/OverlaySections";
import { ScreensSection } from "@pages/debug/sections/ScreenSections";
import { BadgesSection, TabsSection } from "@pages/debug/sections/SelectionSections";

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
  "screens",
] as const;

// Opened from the debug bar: every shared UI primitive, live, grouped like the codebase uses them.
export function DebugKitPage() {
  const k = useKit();
  const links = useMemo(() => SECTION_IDS.map((id) => ({ id, label: k(`sections.${id}.nav`) })), [k]);

  return (
    <DebugShell bar={<DebugNav links={links} />}>
      <div className="flex items-baseline justify-between gap-4 px-1">
        <p className="text-[12px] text-muted-foreground">{k("intro.caption")}</p>
        <span className="shrink-0 font-mono text-[12px] text-muted-foreground">{k("intro.meta")}</span>
      </div>

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
    </DebugShell>
  );
}
