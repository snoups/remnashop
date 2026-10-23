import { Database, Globe, Hash, Layers, Receipt, TrendingUp, User } from "lucide-react";
import { useState } from "react";

import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { normalizeEmail } from "@shared/lib/chip-normalizers";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { EYEBROW_CLASS, LIST_BODY_CLASS, LIST_HEAD_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";
import { ColorPickerField } from "@shared/ui/ColorPickerField";
import { Field } from "@shared/ui/Field";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { InfoRow } from "@shared/ui/InfoRow";
import { KpiTile } from "@shared/ui/KpiTile";
import { PasswordInput } from "@shared/ui/PasswordInput";
import { SearchField } from "@shared/ui/SearchField";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Slider } from "@shared/ui/Slider";
import { Switch } from "@shared/ui/Switch";
import { Tag } from "@shared/ui/Tag";
import { SuffixInput, TextArea, TextInput } from "@shared/ui/TextInput";
import { UserRow } from "@shared/ui/UserRow";

const ROWS = [
  { days: 30, rub: "199", usd: "2.49", share: "30%" },
  { days: 90, rub: "549", usd: "6.99", share: "22%" },
  { days: 365, rub: "1 990", usd: "24.9", share: "15%" },
];
const GRID = "grid grid-cols-[minmax(0,1fr)_80px_80px_60px] items-center gap-3";
const TABLE_BODY = "[&>tr:not(:last-child)>td]:border-b [&>tr:not(:last-child)>td]:border-border/50";

export function FieldsSection() {
  const k = useKit();
  const [search, setSearch] = useState("");
  const [select, setSelect] = useState("ru");
  const [isOn, setIsOn] = useState(true);
  const [slider, setSlider] = useState(30);
  const [color, setColor] = useState("#22d3ee");
  const [chips, setChips] = useState(["user@example.com"]);
  const options = [
    { value: "ru", label: "Русский", icon: Globe },
    { value: "en", label: "English", icon: Globe },
  ];

  return (
    <DebugSection id="fields">
      <Specimen name="Field + TextInput · hint" usage={k("u.field")} stage="stretch">
        <Field label={k("s.name")} htmlFor="kit-name" hint={k("s.nameHint")}>
          <TextInput id="kit-name" placeholder={k("s.namePlaceholder")} />
        </Field>
      </Specimen>
      <Specimen name="Field · info · aside" usage={k("u.fieldInfo")} stage="stretch">
        <Field
          label={k("s.login")}
          htmlFor="kit-login"
          info={k("s.hintShort")}
          aside={<span className="text-error">*</span>}
        >
          <TextInput id="kit-login" placeholder="admin" />
        </Field>
      </Specimen>
      <Specimen name="Field · error" usage={k("u.fieldError")} stage="stretch">
        <Field label={k("s.code")} htmlFor="kit-code" error={k("s.codeError")}>
          <div className="flex gap-2">
            <TextInput
              id="kit-code"
              aria-invalid
              defaultValue="bad code!"
              className="min-w-0 flex-1 font-mono"
            />
            <Button variant="secondary" size="field">
              {k("s.generate")}
            </Button>
          </div>
        </Field>
      </Specimen>
      <Specimen name="Field · TextArea · aside Tag" usage={k("u.textarea")} stage="stretch">
        <Field label={k("s.ids")} htmlFor="kit-ids" aside={<Tag>2</Tag>} hint={k("s.idsHint")}>
          <TextArea id="kit-ids" rows={2} defaultValue={"123456789\n987654321"} className="font-mono" />
        </Field>
      </Specimen>
      <Specimen name="TextInput · disabled" usage={k("u.textInput")} stage="stretch">
        <TextInput disabled defaultValue="42" />
      </Specimen>
      <Specimen name="PasswordInput" usage={k("u.passwordInput")} stage="stretch">
        <PasswordInput defaultValue="secret-pass" />
      </Specimen>
      <Specimen name="ChipsInput" usage={k("u.chipsInput")} stage="stretch">
        <ChipsInput values={chips} onChange={setChips} normalize={normalizeEmail} inputMode="email" />
      </Specimen>
      <Specimen name="SuffixInput · aria-invalid · disabled" usage={k("u.suffixInput")} stage="stretch">
        <SuffixInput type="number" defaultValue="30" suffix={k("s.days")} />
        <SuffixInput type="number" defaultValue="199" aria-invalid suffix="₽" />
        <SuffixInput type="number" defaultValue="5" disabled suffix="USDT" />
      </Specimen>
      <Specimen name="SearchField" usage={k("u.search")} stage="stretch">
        <SearchField
          id="kit-search"
          label={k("s.search")}
          placeholder={k("s.searchPlaceholder")}
          value={search}
          onChange={setSearch}
        />
      </Specimen>
      <Specimen name='SelectDropdown · size="default | compact"' usage={k("u.select")} stage="stretch">
        <SelectDropdown value={select} options={options} placeholder="—" onChange={setSelect} icon={Globe} />
        <SelectDropdown
          value={select}
          options={options}
          placeholder="—"
          onChange={setSelect}
          icon={Globe}
          size="compact"
        />
      </Specimen>
      <Specimen name="Switch · ColorPickerField" usage={`${k("u.switch")} ${k("u.color")}`}>
        <Switch checked={isOn} onChange={setIsOn} />
        <Switch checked={!isOn} onChange={(value) => setIsOn(!value)} />
        <Switch checked onChange={() => undefined} disabled />
        <span className="mx-2 h-6 w-px bg-border" />
        <ColorPickerField value={color} onChange={setColor} />
      </Specimen>
      <Specimen name="Slider" usage={k("u.slider")}>
        <Slider max={100} value={slider} onChange={setSlider} className="w-56" />
        <Slider max={100} value={60} onChange={() => undefined} disabled className="w-56" />
      </Specimen>
      <Specimen name="label · EYEBROW_CLASS" usage={k("u.labels")} wide>
        <span className="text-sm font-medium text-foreground/80">{k("s.name")}</span>
        <span className="mx-3 h-4 w-px bg-border" />
        <span className={EYEBROW_CLASS}>{k("s.filterLabel")}</span>
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
      <Specimen name='Card variant="page"' usage={k("u.cardPage")} stage="stretch">
        <Card>
          <h3 className="text-sm font-bold text-foreground">{k("s.sectionTitle")}</h3>
          <p className="mt-2 text-[12.5px] text-muted-foreground">{k("s.body")}</p>
        </Card>
      </Specimen>
      <Specimen name="Card · CardHeader aside" usage={k("u.cardHeader")} stage="stretch">
        <Card>
          <CardHeader
            icon={Database}
            title={k("s.sectionTitle")}
            description={k("s.cardHeaderDescription")}
            aside={<Button variant="outline">{k("s.botLogs")}</Button>}
          />
          <p className="mt-4 text-[12.5px] text-muted-foreground">{k("s.body")}</p>
        </Card>
      </Specimen>
      <Specimen name='Card variant="form" title' usage={k("u.cardForm")} stage="stretch">
        <Card variant="form" title={k("s.sectionTitle")}>
          <Field label={k("s.name")} htmlFor="kit-card-name">
            <TextInput id="kit-card-name" placeholder={k("s.namePlaceholder")} />
          </Field>
        </Card>
      </Specimen>
      <Specimen name='Card variant="list" title icon · InfoRow' usage={k("u.cardList")} stage="stretch">
        <Card variant="list" title={k("s.sectionTitle")} icon={Layers}>
          {rows}
        </Card>
      </Specimen>
      <Specimen name='Card variant="list" · UserRow' usage={k("u.userRow")} stage="stretch">
        <Card variant="list">
          <UserRow name={k("s.person")} subtitle="@anna · 03.10.2026" aside={<Tag>#1042</Tag>} onClick={() => {}} />
          <UserRow name="" subtitle="03.10.2026" onClick={() => {}} />
          <UserRow name={null} subtitle="03.10.2026" />
        </Card>
      </Specimen>
      <Specimen name='Card variant="bare"' usage={k("u.cardBare")} stage="stretch">
        <Card variant="bare" className="divide-y divide-white/[0.06]">
          <p className="px-4 py-2.5 text-[12.5px] text-muted-foreground">{k("s.body")}</p>
          <p className="px-4 py-2.5 text-[12.5px] text-muted-foreground">{k("s.body")}</p>
        </Card>
      </Specimen>
      <Specimen name="KpiTile · highlighted" usage={k("u.kpi")} stage="stretch">
        <div className="grid grid-cols-2 gap-2">
          <KpiTile label={k("s.revenue")} value="₽ 128 400" hint="+12%" highlighted />
          <KpiTile label={k("s.users")} value="3 214" />
        </div>
      </Specimen>
      <Specimen name="KpiTile · trend" usage={k("u.kpiTrend")} stage="stretch">
        <div className="grid grid-cols-3 gap-2">
          <KpiTile label={k("s.users")} value="1 222" trend={{ delta: 240, hint: k("s.trendMonth") }} />
          <KpiTile label={k("s.users")} value="66" trend={{ delta: -12, hint: k("s.trendWeek") }} />
          <KpiTile label={k("s.users")} value="78" trend={{ delta: 0, hint: k("s.trendWeek") }} />
          <KpiTile label={k("s.revenue")} value="₽ 128 400" trend={{ delta: 0.124, text: "12,4 %", hint: k("s.trendWeek") }} />
          <KpiTile label={k("s.revenue")} value="₽ 12 345 678" hint="+12%" trend={{ delta: -0.083, text: "8,3 %", hint: k("s.trendWeek") }} />
          <KpiTile label={k("s.users")} value="78" hint="+12%" />
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
      <Specimen name="LIST_HEAD_CLASS · LIST_BODY_CLASS · LIST_ROW_CLASS" usage={k("u.list")} stage="stretch" wide>
        <Card>
          <div className={`${GRID} ${LIST_HEAD_CLASS}`}>
            {head.map((cell, index) => (
              <span key={cell} className={index > 0 ? "text-right" : ""}>
                {cell}
              </span>
            ))}
          </div>
          <div className={`${LIST_BODY_CLASS} text-[13px]`}>
            {ROWS.map((row) => (
              <div key={row.days} className={`${GRID} ${LIST_ROW_CLASS} hover:bg-white/[0.04]`}>
                <span className="text-foreground">{days(row.days)}</span>
                <span className="text-right tabular-nums text-foreground/90">{row.rub}</span>
                <span className="text-right tabular-nums text-foreground/90">{row.usd}</span>
                <span className="text-right tabular-nums text-muted-foreground">{row.share}</span>
              </div>
            ))}
          </div>
        </Card>
      </Specimen>
      <Specimen name="GroupToggle · leading" usage={k("u.groupToggle")} stage="stretch">
        <GroupToggleDemo />
      </Specimen>
      <Specimen name="table · page" usage={k("u.table")} stage="stretch">
        <Card>
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
        </Card>
      </Specimen>
      <Specimen name="table · compact" usage={k("u.compact")} stage="stretch">
        <Card variant="bare" className="overflow-hidden">
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
        </Card>
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
