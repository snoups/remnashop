import { FlaskConical, LayoutGrid } from "lucide-react";
import { useEffect, useId, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMatch } from "react-router-dom";

import { useKit } from "@pages/debug/use-kit";
import { ActivePill } from "@shared/ui/ActivePill";
import { EYEBROW_CLASS, PAGE_BAR_CLASS, PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, TAB_HOVER_CLASS } from "@shared/ui/classes";
import { Pressable } from "@shared/ui/Pressable";
import { TabBar } from "@shared/ui/glass/TabBar";

/** The debug page frame, as on the settings pages: a bar floating over a scroller of its own, so main's
 *  top fade can't dim the bar. bar: what floats beside the Kit / Variants tabs. */
export function DebugShell({ bar, children }: { bar?: ReactNode; children: ReactNode }) {
  const { t } = useTranslation();
  const isKit = useMatch({ path: "/dashboard/debug", end: true }) !== null;
  return (
    <div data-fills-main className={PAGE_CLASS}>
      <div className={`${PAGE_BAR_CLASS} flex gap-3`}>
        <TabBar
          items={[
            { key: "kit", to: "/dashboard/debug", icon: LayoutGrid, label: t("debugPage.tabs.kit"), isActive: isKit },
            { key: "variants", to: "/dashboard/debug/variants", icon: FlaskConical, label: t("debugPage.tabs.variants"), isActive: !isKit },
          ]}
        />
        {bar && <div className="min-w-0 flex-1">{bar}</div>}
      </div>
      <div className={`${PAGE_SCROLL_UNDER_BAR_CLASS} flex flex-col gap-6`}>
        {children}
      </div>
    </div>
  );
}

export interface DebugSectionLink {
  id: string;
  label: string;
}

/** Sticky section strip; highlights the section under the upper part of the viewport. */
export function DebugNav({ links }: { links: DebugSectionLink[] }) {
  const [active, setActive] = useState(links[0]?.id);
  const pillId = useId();

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
    // the glass TabBar's capsule: 48px, 36px items 6px in
    // a mouse wheel scrolls it sideways: the strip outgrows the bar and hides its scrollbar
    <nav
      onWheel={(event) => {
        if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) event.currentTarget.scrollLeft += event.deltaY;
      }}
      className="glass-panel no-scrollbar flex h-12 gap-1 overflow-x-auto rounded-full p-1.5"
    >
      {links.map(({ id, label }) => (
        <Pressable
          key={id}
          type="button"
          onClick={() => {
            setActive(id);
            document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
          }}
          className="group relative isolate h-9 flex-1 shrink-0 whitespace-nowrap rounded-full text-[13px] font-medium"
        >
          {active === id ? (
            <ActivePill layoutId={pillId} />
          ) : (
            <span className={TAB_HOVER_CLASS} />
          )}
          <span className={`relative z-10 px-4 ${active === id ? "text-primary" : "text-foreground"}`}>{label}</span>
        </Pressable>
      ))}
    </nav>
  );
}

/** A titled group of specimens; two columns from sm up. Title and meta come from debugPage.kit.sections.<id>. */
export function DebugSection({ id, children }: { id: string; children: ReactNode }) {
  const k = useKit();
  return (
    // the scroller's scroll-pt clears the nav on desktop; scroll-mt clears the fixed mobile header
    <section id={id} className="flex max-md:scroll-mt-16 flex-col gap-3.5">
      <div className="flex items-baseline justify-between gap-4 border-b border-white/[0.08] px-1 pb-2.5">
        <h2 className="text-[15px] font-semibold tracking-tight text-foreground">{k(`sections.${id}.title`)}</h2>
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
      className={`glass-panel flex flex-col rounded-3xl ${
        wide ? "sm:col-span-2" : ""
      }`}
    >
      <div
        // no overflow-hidden on the card: tooltips and menus inside a stage must not be clipped
        className={`flex min-h-[120px] flex-1 rounded-t-3xl bg-black/[0.18] p-5 ${
          stage === "center" ? "flex-wrap items-center justify-center gap-2" : "flex-col justify-center gap-3"
        }`}
      >
        {children}
      </div>
      <div className="flex flex-col gap-0.5 p-4">
        <span className="font-mono text-[12px] font-semibold text-foreground">{name}</span>
        <span className="text-[12px] text-muted-foreground">{usage}</span>
      </div>
    </div>
  );
}
