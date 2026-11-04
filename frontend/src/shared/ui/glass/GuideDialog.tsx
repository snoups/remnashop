import { CircleHelp } from "lucide-react";
import { useId, useState, type ReactNode } from "react";

import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { CopyInput } from "@shared/ui/glass/Input";
import { IconButton } from "@shared/ui/IconButton";
import { Modal } from "@shared/ui/Modal";

/** A ? button (32px with a 14px icon, a Row's) opening a glass help dialog; body text 13px, step groups
 *  divided by lines. */
export function GuideDialog({
  title,
  header = false,
  children,
}: {
  title: string;
  /** in a Section's header, among its 36px glass buttons */
  header?: boolean;
  children: ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  return (
    <>
      <IconButton
        size={header ? "9" : "8"}
        tone={header ? "glass" : "default"}
        onClick={(event) => {
          event.stopPropagation();
          setIsOpen(true);
        }}
      >
        <CircleHelp className={header ? "size-4 text-foreground/90" : "size-3.5"} />
      </IconButton>

      {isOpen && (
        // the trigger sits inside clickable rows; portal events still bubble through the React tree
        <span className="contents" onClick={(event) => event.stopPropagation()}>
          <Modal onClose={() => setIsOpen(false)} size="lg" scrollable>
            <DialogHeader icon={CircleHelp} title={title} />
            {/* each step group under a line, 20px apart; body 13px at 1.6 so long instructions don't run together */}
            <div className="scroll-fade-y flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4 text-[13px] leading-[1.6] text-foreground/85 [&>*+*]:border-t [&>*+*]:border-white/[0.08] [&>*+*]:pt-5">
              {children}
            </div>
          </Modal>
        </span>
      )}
    </>
  );
}

/** A step group's title inside GuideDialog: the 15px step of the type scale, above 13px text. */
export function GuideHeading({ children }: { children: ReactNode }) {
  return <h3 className="text-[15px] font-semibold tracking-tight text-foreground">{children}</h3>;
}

/** A value to paste somewhere else (a callback URL, a command), labelled, with copy. */
export function GuideCopy({ label, value }: { label: string; value: string }) {
  const id = useId();
  return (
    <Field label={label} htmlFor={id}>
      <CopyInput id={id} value={value} />
    </Field>
  );
}

/** An accent note in a guide: a tip the admin shouldn't miss. Out of the body's 16px padding to 12px off
 *  the dialog's edge, 12px corners concentric with its 24px. className: layout only. */
export function GuideTip({ className = "", children }: { className?: string; children: ReactNode }) {
  return <p className={`-mx-1 rounded-xl border border-primary/35 bg-primary/15 px-3 py-2.5 text-primary ${className}`}>{children}</p>;
}
