import { Bell } from "lucide-react";

import { useKit } from "@pages/debug/use-kit";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { IconCircle } from "@shared/ui/glass/IconCircle";

const ROLES = ["kpi", "screen", "header", "cardTitle", "body", "button", "secondary", "eyebrow", "badge", "micro"] as const;

type Role = (typeof ROLES)[number];
type Scale = Record<Role, { size: string; px: number }>;

const CURRENT: Scale = {
  kpi: { size: "text-[26px]", px: 26 },
  screen: { size: "text-[21px]", px: 21 },
  header: { size: "text-[17px]", px: 17 },
  cardTitle: { size: "text-[15px]", px: 15 },
  body: { size: "text-[13px]", px: 13 },
  button: { size: "text-[13px]", px: 13 },
  secondary: { size: "text-[12px]", px: 12 },
  eyebrow: { size: "text-[11px]", px: 11 },
  badge: { size: "text-[11px]", px: 11 },
  micro: { size: "text-[10px]", px: 10 },
};

// Tailwind's default steps, the same as Material 3 and GitHub use: 14 body, 12 floor, 11 only for a counter
const STANDARD: Scale = {
  kpi: { size: "text-2xl", px: 24 },
  screen: { size: "text-xl", px: 20 },
  header: { size: "text-base", px: 16 },
  cardTitle: { size: "text-base", px: 16 },
  body: { size: "text-sm", px: 14 },
  button: { size: "text-sm", px: 14 },
  secondary: { size: "text-xs", px: 12 },
  eyebrow: { size: "text-xs", px: 12 },
  badge: { size: "text-xs", px: 12 },
  micro: { size: "text-[11px]", px: 11 },
};

const ROLE_STYLE: Record<Role, string> = {
  kpi: "font-bold leading-tight tabular-nums tracking-tight text-foreground",
  screen: "font-bold tracking-tight text-foreground",
  header: "font-semibold tracking-tight text-foreground",
  cardTitle: "font-semibold tracking-tight text-foreground",
  body: "text-foreground",
  button: "inline-flex h-9 items-center rounded-full border border-glass-border bg-white/[0.03] px-3.5 font-medium text-foreground",
  secondary: "text-muted-foreground",
  eyebrow: "font-semibold uppercase tracking-wide text-muted-foreground",
  badge: "inline-flex rounded-full bg-success/15 px-2 py-0.5 font-semibold uppercase tracking-wide text-success",
  micro: "inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 font-semibold leading-none text-primary-foreground",
};

function cls(scale: Scale, role: Role) {
  return `${scale[role].size} ${ROLE_STYLE[role]}`;
}

function Mock({ scale, label }: { scale: Scale; label: string }) {
  const k = useKit();
  const m = (key: string) => k(`variants.type.mock.${key}`);
  return (
    <div className="flex min-w-0 flex-col gap-2">
      <span className={`px-1 ${EYEBROW_CLASS}`}>{label}</span>
      <div className="glass-panel flex flex-col gap-4 rounded-3xl p-4">
        <div className="flex items-center justify-between gap-3">
          <span className={cls(scale, "header")}>{m("pageTitle")}</span>
          <span className={cls(scale, "button")}>{m("create")}</span>
        </div>
        <div className="flex items-center gap-3">
          <IconCircle icon={Bell} header />
          <div className="min-w-0">
            <h2 className={cls(scale, "cardTitle")}>{m("cardTitle")}</h2>
            <p className={`mt-0.5 ${cls(scale, "secondary")}`}>{m("cardDesc")}</p>
          </div>
        </div>
        <div className="-mx-4 border-t border-white/[0.08]" />
        <div className="flex flex-col gap-2">
          <span className={cls(scale, "eyebrow")}>{m("channel")}</span>
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className={cls(scale, "body")}>{m("telegram")}</div>
              <div className={cls(scale, "secondary")}>{m("telegramHint")}</div>
            </div>
            <span className={cls(scale, "badge")}>{m("on")}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-baseline gap-2">
              <span className={cls(scale, "body")}>{m("user")}</span>
              <span className={`font-mono ${cls(scale, "secondary")}`}>#1042</span>
            </div>
            <span className={cls(scale, "micro")}>5</span>
          </div>
        </div>
        <div className="flex flex-col gap-1 rounded-2xl bg-white/[0.03] p-3.5">
          <span className={cls(scale, "eyebrow")}>{m("revenue")}</span>
          <span className={cls(scale, "kpi")}>{m("revenueValue")}</span>
          <span className={cls(scale, "secondary")}>{m("revenueDelta")}</span>
        </div>
      </div>
    </div>
  );
}

/** Current type scale beside the conventional one: per role, then one card set in each. */
export function TypeScaleVariant() {
  const k = useKit();
  return (
    <section className="flex flex-col gap-3.5">
      <div className="flex flex-col gap-1 border-b border-white/[0.08] px-1 pb-2.5">
        <h2 className="text-[15px] font-semibold tracking-tight text-foreground">{k("variants.type.title")}</h2>
        <p className="text-[12px] text-muted-foreground">{k("variants.type.caption")}</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Mock scale={CURRENT} label={k("variants.type.now")} />
        <Mock scale={STANDARD} label={k("variants.type.standard")} />
      </div>

      <div className="glass-panel overflow-x-auto rounded-3xl p-2">
        <table className="w-full text-left">
          <thead>
            <tr className={`${EYEBROW_CLASS} [&>th]:px-3 [&>th]:py-2`}>
              <th>{k("variants.type.columns.role")}</th>
              <th>{k("variants.type.columns.size")}</th>
              <th>{k("variants.type.now")}</th>
              <th>{k("variants.type.standard")}</th>
            </tr>
          </thead>
          <tbody>
            {ROLES.map((role) => (
              <tr key={role} className="border-t border-white/[0.06] align-middle [&>td]:px-3 [&>td]:py-2.5">
                <td className="text-[12px] text-muted-foreground">{k(`variants.type.role.${role}`)}</td>
                <td className="whitespace-nowrap font-mono text-[12px] text-foreground">
                  {CURRENT[role].px} → {STANDARD[role].px}
                </td>
                <td><span className={cls(CURRENT, role)}>{k(`variants.type.sample.${role}`)}</span></td>
                <td><span className={cls(STANDARD, role)}>{k(`variants.type.sample.${role}`)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
