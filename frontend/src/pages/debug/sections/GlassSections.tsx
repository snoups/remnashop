import { Bot, Copy, Globe, Hash, Layers, RefreshCw, Settings, User } from "lucide-react";
import { useState } from "react";

import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { GuideCopy, GuideDialog, GuideHeading, GuideTip } from "@shared/ui/glass/GuideDialog";
import { Input, PasswordInput, TextArea } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { Switch } from "@shared/ui/glass/Switch";
import { TabBar } from "@shared/ui/glass/TabBar";
import { Tag } from "@shared/ui/glass/Tag";
import { TextWidth } from "@shared/ui/glass/TextWidth";
import { ToggleCapsule } from "@shared/ui/glass/ToggleCapsule";
import { IconButton } from "@shared/ui/IconButton";
import { Modal } from "@shared/ui/Modal";
import { SaveFooter } from "@shared/ui/SaveFooter";

// shared/ui/glass: the new design, page by page; the old primitives stay until the last page moves
export function GlassSection() {
  const k = useKit();
  const [on, setOn] = useState(true);
  const [bot, setBot] = useState(true);
  const [cabinet, setCabinet] = useState(false);
  const [open, setOpen] = useState(false);
  const [dialog, setDialog] = useState(false);

  return (
    <DebugSection id="glass">
      <Specimen name="Row / SectionRows" usage={k("u.glassRowVsRows")} wide stage="stretch">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="flex flex-col gap-2">
            <p className="text-[12px] text-muted-foreground">{k("s.rowOnly")}</p>
            <div className="rounded-[30px] outline-1 outline-dashed outline-primary">
              <Row icon={User} label={k("s.status")} description={k("s.nameHint")}>
                <Switch checked={on} onChange={setOn} />
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
                  <Switch checked={on} onChange={setOn} />
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
      </Specimen>

      <Specimen name="Section · SectionRows · Row · SectionFields" usage={k("u.glassSection")} wide stage="stretch">
        <Section
          icon={Settings}
          title={k("s.sectionTitle")}
          description={k("s.body")}
          aside={<Button variant="glass" icon={RefreshCw}>{k("s.refresh")}</Button>}
          footer={<SaveFooter variant="glassAccent" dirty saving={false} onSave={() => {}} />}
        >
          <SectionRows>
            <Row icon={User} label={k("s.status")} description={k("s.nameHint")}>
              <Switch checked={on} onChange={setOn} />
            </Row>
            <Row icon={Hash} label={k("s.code")} expanded={open} onClick={() => setOpen((value) => !value)} panel={
              <Field label={k("s.name")} htmlFor="glass-row-name">
                <Input id="glass-row-name" placeholder={k("s.namePlaceholder")} />
              </Field>
            }>
              <Tag>12</Tag>
              <Button variant="glass" size="sm">
                {k("s.edit")}
              </Button>
            </Row>
          </SectionRows>
          <SectionFields divided>
            <Field label={k("s.login")} htmlFor="glass-login">
              <Input id="glass-login" />
            </Field>
          </SectionFields>
        </Section>
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

      <Specimen name="Field info · PasswordInput · error" usage={k("u.glassField")} stage="stretch">
        <Field label={k("s.password")} htmlFor="glass-password" required info={k("s.mrrInfo")} hint={k("s.nameHint")}>
          <PasswordInput id="glass-password" />
        </Field>
        <Field label={k("s.code")} htmlFor="glass-code" error={k("s.codeError")}>
          <Input id="glass-code" aria-invalid defaultValue="код!" />
        </Field>
      </Specimen>

      <Specimen name="TextArea corner mono" usage={k("u.glassTextarea")} stage="stretch">
        <TextArea rows={4} mono corner="42 / 32763" defaultValue={k("s.body")} />
      </Specimen>

      <Specimen name="Switch" usage={k("u.glassSwitch")}>
        <Switch checked={on} onChange={setOn} />
        <Switch checked={false} onChange={() => {}} />
        <Switch checked disabled onChange={() => {}} />
      </Specimen>

      <Specimen name='StatusPill tone="success | warning | error"' usage={k("u.glassStatus")}>
        <StatusPill tone="success">{k("s.status")}</StatusPill>
        <StatusPill tone="warning">{k("s.status")}</StatusPill>
        <StatusPill tone="error">{k("s.status")}</StatusPill>
      </Specimen>

      <Specimen name="ToggleCapsule" usage={k("u.glassToggle")} stage="stretch">
        <div className="flex gap-2">
          <ToggleCapsule icon={Bot} label="Telegram" checked={bot} onChange={setBot} />
          <ToggleCapsule icon={Globe} label="Web" checked={cabinet} onChange={setCabinet} />
        </div>
      </Specimen>

      <Specimen name="TextWidth · Tag" usage={k("u.glassTextWidth")}>
        <TextWidth text={k("s.namePlaceholder")}>
          <Input size="sm" className="flex-1" placeholder={k("s.namePlaceholder")} />
        </TextWidth>
        <TextWidth text={k("s.namePlaceholder")}>
          <Input size="sm" className="flex-1" defaultValue="24" />
          <Switch checked={on} onChange={setOn} />
        </TextWidth>
        <Tag>{k("s.status")}</Tag>
      </Specimen>

      <Specimen name='TabBar · Modal material="glass" · DialogHeader' usage={k("u.glassTabBar")}>
        <TabBar
          items={[
            { key: "one", to: "", icon: Layers, label: k("s.users"), isActive: true },
            { key: "two", to: "", icon: User, label: k("s.revenue"), isActive: false },
          ]}
        />
        <Button variant="glass" onClick={() => setDialog(true)}>
          {k("s.dialogTitle")}
        </Button>
        {dialog && (
          <Modal onClose={() => setDialog(false)} material="glass">
            <DialogHeader icon={Layers} title={k("s.dialogTitle")} />
            <p className="p-4 text-[13px] text-muted-foreground">{k("s.modalText")}</p>
          </Modal>
        )}
      </Specimen>
      <Specimen name="GuideDialog · GuideHeading · GuideCopy · GuideTip" usage={k("u.glassGuide")}>
        <GuideDialog title={k("s.dialogTitle")}>
          <p>{k("s.modalText")}</p>
          <div className="flex flex-col gap-2">
            <GuideHeading>{k("s.sectionTitle")}</GuideHeading>
            <GuideCopy label={k("s.code")} value="https://example.com/api/v1/auth/callback" />
          </div>
          <GuideTip>{k("s.body")}</GuideTip>
        </GuideDialog>
      </Specimen>
    </DebugSection>
  );
}
