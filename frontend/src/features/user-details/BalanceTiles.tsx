import { Pencil } from "lucide-react";
import { useRef, useState, type ChangeEvent, type FocusEvent, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { listEventLog, type EventLogEntry } from "@entities/event-log/api";
import { adjustUserPoints } from "@entities/referrals/api";
import { setUserDiscount, type UserListItem } from "@entities/user/api";
import { usePermissions } from "@entities/user/use-current-user";
import { EventDetailDialog } from "@features/event-details/EventDetailDialog";
import { getErrorMessage } from "@shared/api/http";
import { formatRelative } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { Button } from "@shared/ui/Button";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { KpiTile } from "@shared/ui/KpiTile";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { SuffixInput, TextInput } from "@shared/ui/TextInput";

// Points and discount tiles of the user profile; each opens its own editor.

const POINT_DELTAS = [-50, -10, 10, 50];
const DISCOUNT_PRESETS = [0, 5, 10, 15, 20];
const POPOVER_HEIGHT = 240;

type DiscountKind = "personal_discount" | "purchase_discount";

const DISCOUNT_EVENT: Record<DiscountKind, string> = {
  personal_discount: "UserPersonalDiscountChangedEvent",
  purchase_discount: "UserPurchaseDiscountChangedEvent",
};

export function BalanceTiles({ user, onChanged }: { user: UserListItem; onChanged?: (user: UserListItem) => void }) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const [openedEntry, setOpenedEntry] = useState<EventLogEntry | null>(null);
  const canEditPoints = Boolean(onChanged) && permissions.includes("REFERRALS_POINTS_MANAGE");
  // the backend refuses a staff account's discount without ADMINS_MANAGE
  const canEditDiscount =
    Boolean(onChanged) &&
    permissions.includes("USERS_DISCOUNT_MANAGE") &&
    (user.role === "USER" || permissions.includes("ADMINS_MANAGE"));
  const lastChange = (eventType: string, close: () => void) =>
    permissions.includes("EVENT_LOG_VIEW") ? (
      <LastChange
        userId={user.id}
        eventType={eventType}
        onOpen={(entry) => {
          close();
          setOpenedEntry(entry);
        }}
      />
    ) : null;

  const discountTile = (kind: DiscountKind, label: string) => {
    const percent = user[kind];
    if (!canEditDiscount) return <KpiTile label={label} value={`${percent}%`} />;
    return (
      <EditableKpi label={label} value={`${percent}%`}>
        {(close) => (
          <>
            <ValueEditor
              current={percent}
              max={100}
              suffix="%"
              hint={t("users.details.balance.discountHint")}
              chips={DISCOUNT_PRESETS.map((preset) => ({ label: `${preset}%`, apply: () => preset }))}
              onApply={async (next) => {
                try {
                  onChanged?.(await setUserDiscount(user.id, { [kind]: next }));
                  toast.success(t("users.details.balance.saved"));
                  close();
                } catch (err) {
                  toast.error(getErrorMessage(err, t("users.details.balance.discountError")));
                }
              }}
            />
            {lastChange(DISCOUNT_EVENT[kind], close)}
          </>
        )}
      </EditableKpi>
    );
  };

  const points = Math.trunc(Number(user.points));

  return (
    <div className="grid grid-cols-3 gap-3">
      {canEditPoints ? (
        <EditableKpi label={t("users.details.points")} value={String(user.points)}>
          {(close) => (
            <>
              <ValueEditor
                current={points}
                hint={t("users.details.balance.pointsHint")}
                chips={POINT_DELTAS.map((delta) => ({
                  label: delta > 0 ? `+${delta}` : `−${-delta}`,
                  apply: (value) => value + delta,
                }))}
                onApply={async (next) => {
                  try {
                    // the endpoint takes a change, not a value
                    const stats = await adjustUserPoints(user.id, String(next - points));
                    onChanged?.({ ...user, points: stats.points });
                    toast.success(t("users.details.balance.saved"));
                    close();
                  } catch (err) {
                    toast.error(getErrorMessage(err, t("users.details.balance.pointsError")));
                  }
                }}
              />
              {lastChange("UserPointsAdjustedEvent", close)}
            </>
          )}
        </EditableKpi>
      ) : (
        <KpiTile label={t("users.details.points")} value={String(user.points)} />
      )}
      {discountTile("personal_discount", t("users.details.personalDiscount"))}
      {discountTile("purchase_discount", t("users.details.purchaseDiscount"))}
      {/* outside the popovers: opening the dialog closes them */}
      {openedEntry && <EventDetailDialog entry={openedEntry} onClose={() => setOpenedEntry(null)} />}
    </div>
  );
}

/** A KpiTile that opens an editor under itself; the pencil shows on hover. */
function EditableKpi({
  label,
  value,
  children,
}: {
  label: string;
  value: string;
  children: (close: () => void) => ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const close = () => setIsOpen(false);
  useClickOutside([ref, popoverRef], isOpen, close);
  useCloseOnScroll(isOpen, popoverRef, close);

  return (
    <div ref={ref} className="group relative min-w-0">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        className="block w-full rounded-2xl text-left transition-colors hover:bg-white/[0.04]"
      >
        <KpiTile label={label} value={value} highlighted={isOpen} />
      </button>
      <Pencil
        className={`pointer-events-none absolute right-3.5 top-4 size-3.5 transition-opacity ${
          isOpen ? "text-accent-foreground opacity-100" : "text-muted-foreground opacity-0 group-hover:opacity-100"
        }`}
      />
      <PortalPopover
        open={isOpen}
        triggerRef={ref}
        popoverRef={popoverRef}
        align="left"
        maxHeight={POPOVER_HEIGHT}
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="flex w-72 flex-col gap-2.5 p-3"
      >
        {children(close)}
      </PortalPopover>
    </div>
  );
}

/** "250" sets the value, "300-5" adds up, a leading "+50" / "−10" counts from the current one;
 *  null when it doesn't parse */
function resolveValue(input: string, current: number): number | null {
  const text = input.replace(/\s/g, "").replace(/−/g, "-");
  if (!/^[+-]?\d+([+-]\d+)*$/.test(text)) return null;
  const sum = (text.match(/[+-]?\d+/g) ?? []).reduce((total, term) => total + Number(term), 0);
  return /^[+-]/.test(text) ? current + sum : sum;
}

interface ValueEditorProps {
  current: number;
  max?: number;
  suffix?: string;
  hint: string;
  /** quick picks; each gets the value the field resolves to right now */
  chips: { label: string; apply: (value: number) => number }[];
  onApply: (next: number) => Promise<void>;
}

function ValueEditor({ current, max = Number.MAX_SAFE_INTEGER, suffix, hint, chips, onApply }: ValueEditorProps) {
  const { t, i18n } = useTranslation();
  const [input, setInput] = useState(String(current));
  const [isSaving, setIsSaving] = useState(false);
  const resolved = resolveValue(input, current);
  const isValid = resolved !== null && resolved >= 0 && resolved <= max;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!isValid || resolved === current) return;
    setIsSaving(true);
    await onApply(resolved);
    setIsSaving(false);
  };

  const field = {
    autoFocus: true,
    inputMode: "numeric" as const,
    value: input,
    onChange: (event: ChangeEvent<HTMLInputElement>) => setInput(event.target.value),
    onFocus: (event: FocusEvent<HTMLInputElement>) => event.target.select(),
    "aria-invalid": input.trim() !== "" && !isValid,
  };

  return (
    <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-2.5">
      <div className="flex gap-2">
        {suffix ? (
          <SuffixInput suffix={suffix} className="min-w-0 flex-1" {...field} />
        ) : (
          <TextInput className="min-w-0 flex-1" {...field} />
        )}
        <Button variant="accent" size="field" type="submit" disabled={!isValid || resolved === current || isSaving}>
          {t("users.details.balance.apply")}
        </Button>
      </div>
      <div className="flex gap-1.5">
        {chips.map((chip) => (
          <ChoiceChip
            key={chip.label}
            size="sm"
            className="flex-1"
            active={false}
            onClick={() => setInput(String(Math.min(max, Math.max(0, chip.apply(resolved ?? current)))))}
          >
            {chip.label}
          </ChoiceChip>
        ))}
      </div>
      <p className="text-[12px] text-muted-foreground">
        {isValid && resolved !== current ? (
          <>
            {t("users.details.balance.willBe")}{" "}
            <span className="tabular-nums">
              {current.toLocaleString(i18n.language)}
              {suffix}
            </span>
            {" → "}
            <span className="font-semibold tabular-nums text-foreground">
              {resolved.toLocaleString(i18n.language)}
              {suffix}
            </span>
          </>
        ) : (
          hint
        )}
      </p>
    </form>
  );
}

/** Who made the latest change of this kind; nothing until there is one. */
function LastChange({
  userId,
  eventType,
  onOpen,
}: {
  userId: number;
  eventType: string;
  onOpen: (entry: EventLogEntry) => void;
}) {
  const { t, i18n } = useTranslation();
  const [state] = useAsyncResource((signal) => listEventLog({ targetId: userId, eventType, pageSize: 1 }, signal));
  const entry = state.kind === "ready" ? state.data.items[0] : undefined;
  if (!entry) return null;

  return (
    <button
      type="button"
      onClick={() => onOpen(entry)}
      className="truncate border-t border-white/[0.07] pt-2 text-left text-[12px] text-muted-foreground transition-colors hover:text-foreground"
    >
      {t("users.details.balance.lastChange", {
        name: entry.actor_name ?? entry.actor_login ?? t("common.none"),
        when: formatRelative(entry.occurred_at, i18n.language),
      })}
    </button>
  );
}
