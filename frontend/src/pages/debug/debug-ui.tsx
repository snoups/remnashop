import { useEffect, useState, type ReactNode } from "react";

import { useKit } from "@pages/debug/use-kit";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { Pressable } from "@shared/ui/Pressable";

export interface DebugSectionLink {
  id: string;
  label: string;
}

/** Sticky section strip; highlights the section under the upper part of the viewport. */
export function DebugNav({ links }: { links: DebugSectionLink[] }) {
  const [active, setActive] = useState(links[0]?.id);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting);
        if (visible.length > 0) setActive(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    for (const { id } of links) {
      const element = document.getElementById(id);
      if (element) observer.observe(element);
    }
    return () => observer.disconnect();
  }, [links]);

  return (
    <nav
      className="no-scrollbar sticky top-0 z-20 flex gap-1 overflow-x-auto rounded-full border border-glass-border bg-popover/60 p-1 backdrop-blur-2xl backdrop-saturate-150"
    >
      {links.map(({ id, label }) => (
        <Pressable
          key={id}
          type="button"
          onClick={() => {
            setActive(id);
            document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
          className={`h-[30px] flex-1 shrink-0 whitespace-nowrap rounded-full px-3.5 text-[13px] font-medium transition-colors ${
            active === id ? "bg-accent text-primary" : "text-foreground hover:bg-white/[0.06]"
          }`}
        >
          {label}
        </Pressable>
      ))}
    </nav>
  );
}

/** A titled group of specimens; two columns from sm up. Title and meta come from debugPage.kit.sections.<id>. */
export function DebugSection({ id, children }: { id: string; children: ReactNode }) {
  const k = useKit();
  return (
    // scroll-mt clears the sticky nav when jumped to
    <section id={id} className="flex scroll-mt-16 flex-col gap-3.5">
      <div className="flex items-baseline justify-between gap-4 border-b border-border pb-2.5">
        <h2 className="text-[15px] font-bold text-foreground">{k(`sections.${id}.title`)}</h2>
        <span className={`truncate ${EYEBROW_CLASS}`}>{k(`sections.${id}.meta`)}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">{children}</div>
    </section>
  );
}

/** One live sample: a stage with the component, then its name and where it is used. */
export function Specimen({
  name,
  usage,
  wide = false,
  stage = "center",
  children,
}: {
  name: string;
  usage: string;
  /** spans both columns */
  wide?: boolean;
  /** center: the sample sits centered; stretch: it fills the stage width (fields, tables) */
  stage?: "center" | "stretch";
  children: ReactNode;
}) {
  return (
    <div
      className={`flex flex-col rounded-2xl max-md:rounded-card border border-white/[0.08] bg-white/[0.03] ${
        wide ? "sm:col-span-2" : ""
      }`}
    >
      <div
        // no overflow-hidden on the card: tooltips and menus inside a stage must not be clipped
        className={`flex min-h-[120px] flex-1 rounded-t-[15px] bg-black/[0.18] p-5 ${
          stage === "center" ? "flex-wrap items-center justify-center gap-2" : "flex-col justify-center gap-3"
        }`}
      >
        {children}
      </div>
      <div className="flex flex-col gap-0.5 px-3.5 py-3">
        <span className="font-mono text-[12px] font-semibold text-foreground">{name}</span>
        <span className="text-[12px] text-muted-foreground">{usage}</span>
      </div>
    </div>
  );
}
