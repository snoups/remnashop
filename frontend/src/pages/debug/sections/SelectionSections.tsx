import { ArrowDownUp, BarChart3, Bot, Globe, Pencil, ShieldCheck, Smartphone, Smile, Star, Users } from "lucide-react";
import { useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";

import { PackTab } from "@entities/emoji-packs/EmojiPicker";
import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { Badge, type BadgeTone } from "@shared/ui/Badge";
import { CardPill } from "@shared/ui/CardPill";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { DialogTabs } from "@shared/ui/DialogTabs";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { TabBar } from "@shared/ui/glass/TabBar";
import { ToggleCapsule } from "@shared/ui/glass/ToggleCapsule";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { PeriodPills, type PeriodDays } from "@shared/ui/PeriodPills";
import { PillTabs } from "@shared/ui/PillTabs";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
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
  const [dialogTab, setDialogTab] = useState<DemoTab>("overview");
  const [segment, setSegment] = useState<DemoTab>("overview");
  const [pillTab, setPillTab] = useState<DemoTab>("overview");
  const [packTab, setPackTab] = useState<DemoTab>("overview");
  const [period, setPeriod] = useState<PeriodDays>(30);
  const [chip, setChip] = useState(30);
  const [bot, setBot] = useState(true);
  const [cabinet, setCabinet] = useState(false);
  const label = (tab: DemoTab) => k(`s.${tab}`);

  return (
    <DebugSection id="tabs">
      <Specimen name="TabBar" usage={k("u.glassTabBar")}>
        <TabBar
          items={DEMO_TABS.slice(0, 2).map((tab, index) => ({
            key: tab,
            to: "",
            icon: DEMO_ICONS[tab],
            label: label(tab),
            isActive: index === 0,
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
      <Specimen name="SegmentedPills panel" usage={k("u.segmentedPanel")}>
        <SegmentedPills
          value={segment}
          onChange={setSegment}
          panel
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
      <Specimen name="ToggleCapsule" usage={k("u.glassToggle")} stage="stretch">
        <div className="flex gap-2">
          <ToggleCapsule icon={Bot} label="Telegram" checked={bot} onChange={setBot} />
          <ToggleCapsule icon={Globe} label="Web" checked={cabinet} onChange={setCabinet} />
        </div>
      </Specimen>
      <Specimen name="GroupToggle · leading" usage={k("u.groupToggle")} stage="stretch">
        <GroupToggleDemo />
      </Specimen>
    </DebugSection>
  );
}

function GroupToggleDemo() {
  const k = useKit();
  const [open, setOpen] = useState([true, false]);
  const flip = (index: number) => setOpen((prev) => prev.map((value, i) => (i === index ? !value : value)));

  return (
    <div className="flex flex-col">
      <GroupToggle open={open[0]} onToggle={() => flip(0)} label={k("s.today")} count={3} />
      <GroupToggle
        open={open[1]}
        onToggle={() => flip(1)}
        leading={<span className="-ml-1 size-1.5 rounded-full bg-success" />}
        label={k("s.active")}
        count={12}
      />
    </div>
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
      <Specimen name='IconCircle tone="…" · glyph' usage={k("u.iconCircle")} wide>
        <IconCircle icon={Smartphone} />
        {TONES.map((tone) => (
          <IconCircle key={tone} icon={ShieldCheck} tone={tone} />
        ))}
        <IconCircle glyph={<span className="text-[11px] font-bold">AN</span>} />
        <IconCircle tone="violet" glyph={<span className="text-[11px] font-bold">R</span>} />
      </Specimen>
      <Specimen name="Tag" usage={k("u.tag")}>
        <Tag>128</Tag>
        <Tag>
          <Star className="size-2.5" />
          42
        </Tag>
        <Tag>{k("s.month")}</Tag>
      </Specimen>
      <Specimen name='Badge shape="count"' usage={k("u.badgeCount")}>
        <Badge tone="success" shape="count">2</Badge>
        <Badge tone="warning" shape="count">1</Badge>
        <Badge tone="error" shape="count">14</Badge>
        <Badge tone="neutral" shape="count">128</Badge>
      </Specimen>
      <Specimen name="Badge + icon" usage={k("u.badgeIcon")}>
        <Badge tone="accent">
          <ShieldCheck className="size-2.5" />
          {k("s.status")}
        </Badge>
      </Specimen>
      <Specimen name='StatusPill tone="success | warning | error"' usage={k("u.glassStatus")}>
        <StatusPill tone="success">{k("s.status")}</StatusPill>
        <StatusPill tone="warning">{k("s.status")}</StatusPill>
        <StatusPill tone="error">{k("s.status")}</StatusPill>
      </Specimen>
      <Specimen name="CardPill" usage={k("u.cardPill")} stage="stretch">
        <div className="flex gap-2">
          <CardPill icon={ArrowDownUp} label={k("s.month")} value="100 GB" />
          <CardPill icon={Smartphone} value="∞" />
        </div>
      </Specimen>
    </DebugSection>
  );
}
