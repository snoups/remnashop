import { Bell, GripVertical, Plus, RefreshCw, Trash2, X } from "lucide-react";
import { useState } from "react";

import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { Button } from "@shared/ui/Button";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { IconButton } from "@shared/ui/IconButton";
import { POPOVER_CLASS } from "@shared/ui/classes";
import { LoadMoreButton } from "@shared/ui/LoadMoreButton";
import { MonthCalendar } from "@shared/ui/MonthCalendar";
import { TextInput } from "@shared/ui/TextInput";
import { Pressable } from "@shared/ui/Pressable";

export function ButtonsSection() {
  const k = useKit();

  return (
    <DebugSection id="buttons">
      <Specimen name="accent · solid · outline · danger" usage={k("u.primary")}>
        <Button variant="accent">{k("s.save")}</Button>
        <Button variant="solid">{k("s.create")}</Button>
        <Button variant="outline">{k("s.cancel")}</Button>
        <Button variant="danger">
          <Trash2 className="size-3.5" />
          {k("s.delete")}
        </Button>
      </Specimen>
      <Specimen name="secondary" usage={k("u.secondary")}>
        <Button variant="secondary">
          <RefreshCw className="size-3.5" />
          {k("s.sync")}
        </Button>
      </Specimen>
      <Specimen name='size="sm | md | field"' usage={k("u.sizes")}>
        <Button variant="outline" size="sm">
          sm
        </Button>
        <Button variant="outline">md</Button>
        <TextInput placeholder="38px" className="w-24" />
        <Button variant="secondary" size="field">
          field
        </Button>
      </Specimen>
      <Specimen name="disabled" usage={k("u.disabled")}>
        <Button variant="accent" disabled>
          {k("s.disabled")}
        </Button>
        <Button variant="secondary" disabled>
          {k("s.disabled")}
        </Button>
      </Specimen>
      <Specimen name="icon · isLoading" usage={k("u.buttonLoading")}>
        <Button variant="secondary" icon={RefreshCw}>
          {k("s.sync")}
        </Button>
        <Button variant="secondary" icon={RefreshCw} isLoading>
          {k("s.sync")}
        </Button>
        <Button variant="accent" isLoading>
          {k("s.save")}
        </Button>
      </Specimen>
      <Specimen name="LoadMoreButton" usage={k("u.loadMore")} stage="stretch">
        <LoadMoreButton shown={20} total={134} onClick={() => undefined} />
      </Specimen>
      <Specimen name="dashed" usage={k("u.dashed")}>
        <Pressable
          type="button"
          className="flex h-9 cursor-pointer items-center justify-center gap-1.5 rounded-full border border-dashed border-white/[0.12] px-4 text-[13px] text-foreground/70 transition-colors hover:bg-white/[0.06]"
        >
          <Plus className="size-3.5" />
          {k("s.add")}
        </Pressable>
      </Specimen>
    </DebugSection>
  );
}

// CopyableValue/DatePickerField are the real components; the rest mirrors the markup where each size is used
export function IconButtonsSection() {
  const k = useKit();
  const [date, setDate] = useState("2026-09-29");
  const [range, setRange] = useState({ start: "2026-09-10", end: "2026-09-18" });

  const pickRangeDay = (iso: string) =>
    setRange(({ start, end }) => {
      if (start === "" || end !== "") return { start: iso, end: "" };
      return iso < start ? { start: iso, end: start } : { start, end: iso };
    });

  return (
    <DebugSection id="icons">
      <Specimen name='size="7" tone="group"' usage={k("u.copy")} stage="stretch">
        <CopyableValue label="start" value="?start=ad_summer" />
      </Specimen>
      <Specimen name='size="5"' usage={k("u.clear")} stage="stretch">
        <DatePickerField value={date} onChange={setDate} placeholder="—" />
      </Specimen>
      <Specimen name='size="18px"' usage={k("u.chip")} stage="stretch">
        <div className="flex min-h-9.5 flex-wrap items-center gap-1.5 rounded-[19px] border border-border bg-input/60 px-1.5 py-1">
          {["123456789", "987654321"].map((id) => (
            <span
              key={id}
              className="flex items-center gap-1 rounded-full bg-white/[0.06] py-0.5 pl-2.5 pr-0.5 font-mono text-[12.5px] text-foreground"
            >
              {id}
              <IconButton size="18px">
                <X className="size-2.5" />
              </IconButton>
            </span>
          ))}
        </div>
      </Specimen>
      <Specimen name='size="9.5" tone="danger"' usage={k("u.fieldRow")} stage="stretch">
        <div className="flex items-center gap-2">
          <TextInput defaultValue="199" className="min-w-0 flex-1" />
          <IconButton size="9.5" tone="danger">
            <Trash2 className="size-4" />
          </IconButton>
        </div>
      </Specimen>
      <Specimen name="MonthCalendar" usage={k("u.monthCalendar")}>
        <div className={`${POPOVER_CLASS} w-64 p-3`}>
          <MonthCalendar value={date} onPick={setDate} />
        </div>
        <div className={`${POPOVER_CLASS} w-64 p-3`}>
          <MonthCalendar value={range.start} rangeEnd={range.end} onPick={pickRangeDay} />
        </div>
      </Specimen>
      <Specimen name='size="8"' usage={k("u.cardCorner")} stage="stretch">
        <div className="flex items-start justify-between gap-3 rounded-[20px] border border-white/[0.08] bg-white/[0.03] p-4">
          <span className="text-sm font-bold text-foreground">{k("s.month")}</span>
          <div className="-mr-1.5 -mt-1.5 flex shrink-0 items-center">
            <IconButton size="8" className="cursor-grab">
              <GripVertical className="size-4" />
            </IconButton>
          </div>
        </div>
      </Specimen>
      <Specimen name='size="8"' usage={k("u.toast")} stage="stretch">
        <div className="flex items-start gap-2.5 rounded-popover-item border border-white/[0.14] bg-popover p-3.5">
          <p className="flex-1 text-[13px] leading-6 text-foreground">{k("s.toast")}</p>
          <IconButton size="8" className="-my-1 -mr-1">
            <X className="size-4" />
          </IconButton>
        </div>
      </Specimen>
      <Specimen name="DialogHeader · close" usage={k("u.dialogClose")} stage="stretch">
        <div className="overflow-hidden rounded-dialog border border-white/[0.14] bg-popover/60">
          <DialogHeader title={k("s.dialogTitle")} onClose={() => undefined} />
        </div>
      </Specimen>
      <Specimen name='tone="glass"' usage={k("u.glass")}>
        <IconButton size="8" tone="glass">
          <RefreshCw className="size-[15px]" />
        </IconButton>
        <IconButton size="9" tone="glass">
          <Bell className="size-[17px]" />
        </IconButton>
      </Specimen>
    </DebugSection>
  );
}
