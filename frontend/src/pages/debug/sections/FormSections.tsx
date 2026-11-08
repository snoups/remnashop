import { Copy, Globe, Hash, Layers, Receipt, RefreshCw, Settings, TrendingUp, User } from "lucide-react";
import { useState } from "react";

import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { normalizeEmail } from "@shared/lib/chip-normalizers";
import { Button } from "@shared/ui/Button";
import { CellText } from "@shared/ui/CellText";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { EYEBROW_CLASS, GLASS_LIST_HEAD_CLASS, GLASS_LIST_ROW_CLASS, GLASS_POPOVER_CLASS, LIST_BODY_CLASS } from "@shared/ui/classes";
import { ColorPickerField } from "@shared/ui/ColorPickerField";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { DateTimePickerField } from "@shared/ui/DateTimePickerField";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { Field } from "@shared/ui/glass/Field";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Input, PasswordInput, TextArea } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { TextWidth } from "@shared/ui/glass/TextWidth";
import { IconButton } from "@shared/ui/IconButton";
import { InfoRow } from "@shared/ui/InfoRow";
import { KpiTile } from "@shared/ui/KpiTile";
import { ListRow } from "@shared/ui/ListRow";
import { MonthCalendar } from "@shared/ui/MonthCalendar";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Slider } from "@shared/ui/Slider";
import { Tag } from "@shared/ui/Tag";
import { TextInput } from "@shared/ui/TextInput";
import { UserRow } from "@shared/ui/UserRow";

const ROWS = [
  { days: 30, rub: "199", usd: "2.49", share: "30%" },
  { days: 90, rub: "549", usd: "6.99", share: "22%" },
  { days: 365, rub: "1 990", usd: "24.9", share: "15%" },
];
const GRID = "grid grid-cols-[minmax(0,1fr)_80px_80px_60px] items-center gap-3";
// a page list panel and a block inside a glass dialog, as the pages and dialogs draw them
const PANEL = "glass-panel rounded-3xl p-4";
const DIALOG_BLOCK = "overflow-hidden rounded-xl border border-white/[0.08] bg-white/[0.03]";
const TABLE_BODY = "[&>tr:not(:last-child)>td]:border-b [&>tr:not(:last-child)>td]:border-border/50";

export function FieldsSection() {
  const k = useKit();
  const [search, setSearch] = useState("");
  const [select, setSelect] = useState("ru");
  const [isOn, setIsOn] = useState(true);
  const [slider, setSlider] = useState(30);
  const [color, setColor] = useState("#22d3ee");
  const [chips, setChips] = useState(["user@example.com"]);
  const [date, setDate] = useState("2026-09-29");
  const [dateTime, setDateTime] = useState("2026-09-29T18:30");
  const [range, setRange] = useState({ start: "2026-09-10", end: "2026-09-18" });
  const options = [
    { value: "ru", label: "Русский", icon: Globe },
    { value: "en", label: "English", icon: Globe },
  ];

  const pickRangeDay = (iso: string) =>
    setRange(({ start, end }) => {
      if (start === "" || end !== "") return { start: iso, end: "" };
      return iso < start ? { start: iso, end: start } : { start, end: iso };
    });

  return (
    <DebugSection id="fields">
      <Specimen name="Field info · PasswordInput · error" usage={k("u.glassField")} stage="stretch">
        <Field label={k("s.password")} htmlFor="kit-password" required info={k("s.mrrInfo")} hint={k("s.nameHint")}>
          <PasswordInput id="kit-password" />
        </Field>
        <Field label={k("s.code")} htmlFor="kit-code" error={k("s.codeError")}>
          <Input id="kit-code" aria-invalid defaultValue="код!" />
        </Field>
      </Specimen>
      <Specimen name='Input size="md | sm" · suffix · mono end' usage={k("u.glassInput")} stage="stretch">
        <Input placeholder={k("s.namePlaceholder")} />
        <Input size="sm" suffix={k("s.hours")} defaultValue="24" />
        <Input
          mono
          readOnly
          value="BMx7pQ2vR8nK1sT4wY6zA3cF5hJ9lN0oP2qS4uV6xZ8b"
          end={
            <IconButton size="7">
              <Copy className="size-3.5" />
            </IconButton>
          }
        />
      </Specimen>
      <Specimen name="TextArea mono" usage={k("u.glassTextarea")} stage="stretch">
        <TextArea rows={4} mono defaultValue={k("s.body")} />
      </Specimen>
      <Specimen name="TextWidth" usage={k("u.glassTextWidth")}>
        <TextWidth text={k("s.namePlaceholder")}>
          <Input size="sm" className="flex-1" placeholder={k("s.namePlaceholder")} />
        </TextWidth>
        <TextWidth text={k("s.namePlaceholder")}>
          <Input size="sm" className="flex-1" defaultValue="24" />
          <Switch checked={isOn} onChange={setIsOn} />
        </TextWidth>
      </Specimen>
      <Specimen name="ChipsInput" usage={k("u.chipsInput")} stage="stretch">
        <ChipsInput values={chips} onChange={setChips} normalize={normalizeEmail} inputMode="email" />
      </Specimen>
      <Specimen name="SearchField" usage={k("u.search")} stage="stretch">
        <SearchField
          id="kit-search"
          placeholder={k("s.searchPlaceholder")}
          value={search}
          onChange={setSearch}
        />
      </Specimen>
      <Specimen name='SelectDropdown variant="well" · size="default | compact | lg"' usage={k("u.select")} stage="stretch">
        <SelectDropdown value={select} options={options} placeholder="—" onChange={setSelect} icon={Globe} variant="well" />
        <SelectDropdown value={select} options={options} placeholder="—" onChange={setSelect} icon={Globe} />
        <SelectDropdown
          value={select}
          options={options}
          placeholder="—"
          onChange={setSelect}
          icon={Globe}
          size="compact"
        />
        <SelectDropdown value={select} options={options} placeholder="—" onChange={setSelect} icon={Globe} size="lg" />
      </Specimen>
      <Specimen name='DatePickerField variant="well" · DateTimePickerField' usage={k("u.dateTime")} stage="stretch">
        <DatePickerField value={date} onChange={setDate} placeholder="—" variant="well" />
        <DatePickerField value={date} onChange={setDate} placeholder="—" />
        <DateTimePickerField value={dateTime} onChange={setDateTime} placeholder="—" />
      </Specimen>
      <Specimen name="MonthCalendar" usage={k("u.monthCalendar")}>
        <div className={`${GLASS_POPOVER_CLASS} w-64 p-3`}>
          <MonthCalendar value={date} onPick={setDate} />
        </div>
        <div className={`${GLASS_POPOVER_CLASS} w-64 p-3`}>
          <MonthCalendar value={range.start} rangeEnd={range.end} onPick={pickRangeDay} />
        </div>
      </Specimen>
      <Specimen name="Switch" usage={k("u.glassSwitch")}>
        <Switch checked={isOn} onChange={setIsOn} />
        <Switch checked={!isOn} onChange={(value) => setIsOn(!value)} />
        <Switch checked disabled onChange={() => undefined} />
      </Specimen>
      <Specimen name="Slider · ColorPickerField" usage={`${k("u.slider")} ${k("u.color")}`}>
        <Slider max={100} value={slider} onChange={setSlider} className="w-56" />
        <Slider max={100} value={60} onChange={() => undefined} disabled className="w-56" />
        <ColorPickerField value={color} onChange={setColor} />
      </Specimen>
      <Specimen name="label · EYEBROW_CLASS" usage={k("u.labels")}>
        <span className="text-sm font-medium text-foreground/80">{k("s.name")}</span>
        <span className="mx-3 h-4 w-px bg-border" />
        <span className={EYEBROW_CLASS}>{k("s.filterLabel")}</span>
      </Specimen>
      <Specimen name="TextInput" usage={k("u.editorFields")} stage="stretch">
        <TextInput defaultValue="42" />
      </Specimen>
    </DebugSection>
  );
}

export function CardsSection() {
  const k = useKit();
  const rows = (
    <>
      <InfoRow icon={Hash} label="ID" copyValue="1042" mono>
        1042
      </InfoRow>
      <InfoRow icon={User} label={k("s.users")}>
        {k("s.person")}
      </InfoRow>
    </>
  );

  return (
    <DebugSection id="cards">
      <Specimen name="Section · SectionRows · Row · SectionFields" usage={k("u.glassSection")} wide stage="stretch">
        <SectionDemo />
      </Specimen>
      <Specimen name="Row / SectionRows" usage={k("u.glassRowVsRows")} wide stage="stretch">
        <RowsDemo />
      </Specimen>
      <Specimen name='DialogCard variant="list" title icon · InfoRow' usage={k("u.cardList")} stage="stretch">
        <DialogCard title={k("s.sectionTitle")} icon={Layers}>
          {rows}
        </DialogCard>
      </Specimen>
      <Specimen name='DialogCard variant="form" title' usage={k("u.cardForm")} stage="stretch">
        <DialogCard variant="form" title={k("s.sectionTitle")}>
          <Field label={k("s.name")} htmlFor="kit-card-name">
            <Input id="kit-card-name" placeholder={k("s.namePlaceholder")} />
          </Field>
        </DialogCard>
      </Specimen>
      <Specimen name='DialogCard · UserRow' usage={k("u.userRow")} stage="stretch">
        <DialogCard>
          <UserRow name={k("s.person")} subtitle="@anna · 03.10.2026" aside={<Tag>#1042</Tag>} onClick={() => {}} />
          <UserRow name="" subtitle="03.10.2026" onClick={() => {}} />
          <UserRow name={null} subtitle="03.10.2026" />
        </DialogCard>
      </Specimen>
      <Specimen name="KpiTile · highlighted" usage={k("u.kpi")} stage="stretch">
        <div className="grid grid-cols-2 gap-2">
          <KpiTile label={k("s.revenue")} value="₽ 128 400" hint="+12%" highlighted />
          <KpiTile label={k("s.users")} value="3 214" />
        </div>
      </Specimen>
      <Specimen name="KpiTile · trend · lowerIsBetter" usage={k("u.kpiTrend")} stage="stretch">
        <div className="grid grid-cols-3 gap-2">
          <KpiTile label={k("s.users")} value="1 222" trend={{ delta: 240, hint: k("s.trendMonth") }} />
          <KpiTile label={k("s.users")} value="66" trend={{ delta: -12, hint: k("s.trendWeek") }} />
          <KpiTile label={k("s.users")} value="78" trend={{ delta: 0, hint: k("s.trendWeek") }} />
          <KpiTile label={k("s.revenue")} value="₽ 128 400" trend={{ delta: 0.124, text: "12,4 %", hint: k("s.trendWeek") }} />
          <KpiTile label={k("s.revenue")} value="₽ 12 345 678" hint="+12%" trend={{ delta: -0.083, text: "8,3 %", hint: k("s.trendWeek") }} />
          <KpiTile label={k("s.users")} value="78" hint="+12%" />
          <KpiTile label={k("s.refunds")} value="5" trend={{ delta: 2, hint: k("s.trendWeek"), lowerIsBetter: true }} />
          <KpiTile label={k("s.refunds")} value="1" trend={{ delta: -2, hint: k("s.trendWeek"), lowerIsBetter: true }} />
        </div>
      </Specimen>
      <Specimen name="KpiTile · icon · info" usage={k("u.kpiIcon")} stage="stretch">
        <div className="grid grid-cols-2 gap-2">
          <KpiTile icon={TrendingUp} label="MRR" value="₽ 42 000" info={k("s.mrrInfo")} />
          <KpiTile icon={Receipt} label={k("s.revenue")} value="₽ 1 990" />
        </div>
      </Specimen>
    </DebugSection>
  );
}

export function TablesSection() {
  const k = useKit();
  const days = (count: number) => `${k("s.month")} · ${count}`;
  const head = [k("s.name"), "RUB", "USD", "%"];

  return (
    <DebugSection id="tables">
      <Specimen name="GLASS_LIST_HEAD_CLASS · LIST_BODY_CLASS · GLASS_LIST_ROW_CLASS" usage={k("u.list")} stage="stretch" wide>
        <div className={PANEL}>
          <div className={`${GRID} ${GLASS_LIST_HEAD_CLASS}`}>
            {head.map((cell, index) => (
              <span key={cell} className={index > 0 ? "text-right" : ""}>
                {cell}
              </span>
            ))}
          </div>
          <div className={`${LIST_BODY_CLASS} text-[13px]`}>
            {ROWS.map((row) => (
              <div key={row.days} className={`${GRID} ${GLASS_LIST_ROW_CLASS} hover:bg-white/[0.04]`}>
                <span className="text-foreground">{days(row.days)}</span>
                <span className="text-right tabular-nums text-foreground/90">{row.rub}</span>
                <span className="text-right tabular-nums text-foreground/90">{row.usd}</span>
                <span className="text-right tabular-nums text-muted-foreground">{row.share}</span>
              </div>
            ))}
          </div>
        </div>
      </Specimen>
      <Specimen name="ListRow · disabled" usage={k("u.listRow")} stage="stretch" wide>
        <div className={PANEL}>
          <div className={`${LIST_BODY_CLASS} text-[13px]`}>
            {ROWS.map((row, index) => (
              <ListRow key={row.days} className={GRID} disabled={index === 2}>
                <span className="text-foreground">{days(row.days)}</span>
                <span className="text-right tabular-nums text-foreground/90">{row.rub}</span>
                <span className="text-right tabular-nums text-foreground/90">{row.usd}</span>
                <span className="text-right tabular-nums text-muted-foreground">{row.share}</span>
              </ListRow>
            ))}
          </div>
        </div>
      </Specimen>
      <Specimen name="ListRow · IconCircle · CellText" usage={k("u.cellText")} stage="stretch" wide>
        <div className={PANEL}>
          <div className={LIST_BODY_CLASS}>
            <ListRow className="grid grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-3">
              <IconCircle icon={Globe} tone="success" />
              <CellText title={k("s.person")} sub="SUMMER24" mono />
              <Tag>#1042</Tag>
            </ListRow>
            <ListRow className="grid grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-3">
              <IconCircle glyph={<span className="text-[11px] font-bold">AN</span>} />
              <CellText title={k("s.person")} sub="03.10.2026" />
              <Tag>#1041</Tag>
            </ListRow>
          </div>
        </div>
      </Specimen>
      <Specimen name="table · page" usage={k("u.table")} stage="stretch">
        <div className={PANEL}>
          <table className="w-full border-separate border-spacing-0 text-[13px]">
            <thead>
              <tr className={`text-left ${EYEBROW_CLASS}`}>
                {head.slice(0, 3).map((cell, index) => (
                  <th
                    key={cell}
                    className={`border-b border-border px-3 pb-2.5 font-semibold ${index > 0 ? "text-right" : ""}`}
                  >
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className={TABLE_BODY}>
              {ROWS.map((row) => (
                <tr key={row.days}>
                  <td className="px-3 py-2.5 text-foreground">{days(row.days)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-foreground/90">{row.rub}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums text-foreground/90">{row.usd}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Specimen>
      <Specimen name="table · compact" usage={k("u.compact")} stage="stretch">
        <div className={DIALOG_BLOCK}>
          <table className="w-full border-separate border-spacing-0 text-[12px]">
            <thead>
              <tr className="text-left">
                {head.slice(0, 3).map((cell) => (
                  <th
                    key={cell}
                    className={`border-b border-border px-2.5 pb-1.5 pt-2 font-semibold ${EYEBROW_CLASS}`}
                  >
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className={TABLE_BODY}>
              {ROWS.map((row) => (
                <tr key={row.days}>
                  <td className="px-2.5 py-1.5 text-foreground/90">{days(row.days)}</td>
                  <td className="px-2.5 py-1.5 text-muted-foreground">{row.rub}</td>
                  <td className="px-2.5 py-1.5 font-medium text-foreground">{row.usd}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Specimen>
    </DebugSection>
  );
}

function SectionDemo() {
  const k = useKit();
  const [isOn, setIsOn] = useState(true);
  const [open, setOpen] = useState(false);

  return (
    <Section
      icon={Settings}
      title={k("s.sectionTitle")}
      description={k("s.body")}
      aside={<Button variant="glass" icon={RefreshCw}>{k("s.refresh")}</Button>}
      footer={<SaveFooter dirty saving={false} onSave={() => {}} />}
    >
      <SectionRows>
        <Row icon={User} label={k("s.status")} description={k("s.nameHint")}>
          <Switch checked={isOn} onChange={setIsOn} />
        </Row>
        <Row
          icon={Hash}
          label={k("s.code")}
          expanded={open}
          onClick={() => setOpen((value) => !value)}
          panel={
            <Field label={k("s.name")} htmlFor="kit-row-name">
              <Input id="kit-row-name" placeholder={k("s.namePlaceholder")} />
            </Field>
          }
        >
          <Tag>12</Tag>
          <Button variant="glass" size="sm">
            {k("s.edit")}
          </Button>
        </Row>
      </SectionRows>
      <SectionFields divided>
        <Field label={k("s.login")} htmlFor="kit-login">
          <Input id="kit-login" />
        </Field>
      </SectionFields>
    </Section>
  );
}

function RowsDemo() {
  const k = useKit();
  const [isOn, setIsOn] = useState(true);

  return (
    <div className="grid gap-4 md:grid-cols-3">
      <div className="flex flex-col gap-2">
        <p className="text-[12px] text-muted-foreground">{k("s.rowOnly")}</p>
        <div className="rounded-[30px] outline-1 outline-dashed outline-primary">
          <Row icon={User} label={k("s.status")} description={k("s.nameHint")}>
            <Switch checked={isOn} onChange={setIsOn} />
          </Row>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-[12px] text-muted-foreground">{k("s.rowsOnly")}</p>
        <div className="rounded-2xl outline-1 outline-dashed outline-warning">
          <SectionRows flush>
            <div className="flex h-15 items-center justify-center text-[12px] text-muted-foreground">1</div>
            <div className="flex h-15 items-center justify-center text-[12px] text-muted-foreground">2</div>
            <div className="flex h-15 items-center justify-center text-[12px] text-muted-foreground">3</div>
          </SectionRows>
        </div>
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-[12px] text-muted-foreground">{k("s.rowsTogether")}</p>
        <div className="rounded-2xl outline-1 outline-dashed outline-warning">
          <SectionRows flush>
            <Row icon={User} label={k("s.status")} description={k("s.nameHint")}>
              <Switch checked={isOn} onChange={setIsOn} />
            </Row>
            <Row icon={Hash} label={k("s.code")} description={k("s.nameHint")}>
              <Tag>12</Tag>
            </Row>
            <Row icon={Globe} label={k("s.name")} description={k("s.nameHint")}>
              <Button variant="glass" size="sm">
                {k("s.edit")}
              </Button>
            </Row>
          </SectionRows>
        </div>
      </div>
    </div>
  );
}
