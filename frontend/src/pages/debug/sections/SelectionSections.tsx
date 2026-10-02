import { BarChart3, Pencil, ShieldCheck, Smile, Star, Users } from "lucide-react";
import { useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { PillTabs } from "@features/dialog-canvas-editor/PillTabs";
import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { DialogTabs } from "@shared/ui/DialogTabs";
import { PackTab } from "@shared/ui/EmojiPicker";
import { PeriodPills, type PeriodDays } from "@shared/ui/PeriodPills";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { TabBar } from "@shared/ui/TabBar";
import { Tag } from "@shared/ui/Tag";

type DemoTab = "overview" | "users" | "settings";
const DEMO_TABS: DemoTab[] = ["overview", "users", "settings"];
const DEMO_ICONS: Record<DemoTab, ComponentType<{ className?: string }>> = {
  overview: BarChart3,
  users: Users,
  settings: Pencil,
};
const TONES: BadgeTone[] = ["success", "warning", "error", "neutral", "accent", "violet"];

export function TabsSection() {
  const k = useKit();
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const routeTab = (searchParams.get("tab") as DemoTab | null) ?? "overview";
  const [dialogTab, setDialogTab] = useState<DemoTab>("overview");
  const [segment, setSegment] = useState<DemoTab>("overview");
  const [pillTab, setPillTab] = useState<DemoTab>("overview");
  const [packTab, setPackTab] = useState<DemoTab>("overview");
  const [period, setPeriod] = useState<PeriodDays>(30);
  const [chip, setChip] = useState(30);
  const label = (tab: DemoTab) => k(`s.${tab}`);

  return (
    <DebugSection id="tabs">
      <Specimen name="TabBar" usage={k("u.tabBar")}>
        <TabBar
          items={DEMO_TABS.map((tab) => ({
            key: tab,
            to: `?tab=${tab}`,
            icon: DEMO_ICONS[tab],
            label: label(tab),
            isActive: routeTab === tab,
          }))}
        />
      </Specimen>
      <Specimen name="DialogTabs" usage={k("u.dialogTabs")} stage="stretch">
        <DialogTabs
          items={DEMO_TABS.map((tab) => ({ key: tab, label: label(tab), icon: DEMO_ICONS[tab] }))}
          activeKey={dialogTab}
          onSelect={setDialogTab}
        />
      </Specimen>
      <Specimen name="SegmentedPills" usage={k("u.segmented")}>
        <SegmentedPills
          value={segment}
          onChange={setSegment}
          options={DEMO_TABS.map((tab) => ({ value: tab, label: label(tab) }))}
        />
      </Specimen>
      <Specimen name="SegmentedPills stretch" usage={k("u.segmentedStretch")} stage="stretch">
        <SegmentedPills
          value={segment}
          onChange={setSegment}
          stretch
          options={DEMO_TABS.map((tab) => ({ value: tab, label: label(tab) }))}
        />
      </Specimen>
      <Specimen name="PeriodPills" usage={k("u.period")}>
        <PeriodPills value={period} onChange={setPeriod} />
      </Specimen>
      <Specimen name='PillTabs · size="compact | field"' usage={k("u.pillTabs")} stage="stretch">
        <PillTabs
          items={DEMO_TABS.map((tab) => ({ key: tab, label: label(tab) }))}
          activeKey={pillTab}
          onSelect={setPillTab}
        />
        <PillTabs
          items={DEMO_TABS.map((tab) => ({ key: tab, label: label(tab) }))}
          activeKey={pillTab}
          onSelect={setPillTab}
          size="field"
        />
      </Specimen>
      <Specimen name="EmojiPicker · PackTab" usage={k("u.packTab")}>
        <nav className="flex w-fit gap-1 rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md">
          {DEMO_TABS.map((tab, index) => {
            const Glyph = [Smile, Star, Users][index];
            return (
              <PackTab
                key={tab}
                isActive={packTab === tab}
                glyph={<Glyph className="size-[18px]" />}
                onSelect={() => setPackTab(tab)}
              />
            );
          })}
        </nav>
      </Specimen>
      <Specimen name='ChoiceChip · size="md | sm"' usage={k("u.choice")} wide>
        <div className="flex flex-wrap gap-1.5">
          {[7, 30, 90].map((days) => (
            <ChoiceChip key={days} active={chip === days} onClick={() => setChip(days)}>
              {k("s.month")} · {days}
            </ChoiceChip>
          ))}
        </div>
        <div className="grid w-64 grid-cols-4 gap-1.5">
          {[6, 12, 24, 48].map((hours) => (
            <ChoiceChip
              key={hours}
              size="sm"
              active={chip === hours}
              onClick={() => setChip(hours)}
            >
              {t("backups.schedule.preset", { hours })}
            </ChoiceChip>
          ))}
        </div>
      </Specimen>
    </DebugSection>
  );
}

export function BadgesSection() {
  const k = useKit();
  return (
    <DebugSection id="badges">
      <Specimen name='Badge tone="…"' usage={k("u.badge")} wide>
        {TONES.map((tone) => (
          <div key={tone} className="flex flex-col items-center gap-1.5">
            <Badge tone={tone}>{k("s.status")}</Badge>
            <span className="font-mono text-[11px] text-muted-foreground">{tone}</span>
          </div>
        ))}
      </Specimen>
      <Specimen name="Tag" usage={k("u.tag")}>
        <Tag>128</Tag>
        <Tag>
          <Star className="size-2.5" />
          42
        </Tag>
        <Tag>{k("s.month")}</Tag>
      </Specimen>
      <Specimen name="Badge + icon" usage={k("u.badgeIcon")}>
        <Badge tone="accent">
          <ShieldCheck className="size-2.5" />
          {k("s.status")}
        </Badge>
      </Specimen>
    </DebugSection>
  );
}
