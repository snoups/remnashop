import { Pin, PinOff, Table2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { useBlocker } from "react-router-dom";
import { useTranslation } from "react-i18next";

import {
  CURRENCIES,
  setMatrixPrices,
  type Currency,
  type PriceBook,
  type SetMatrixPricesBody,
  type PriceBookCell,
  type PriceBookRow,
} from "@entities/pricing/api";
import { BulkAdjustButton } from "@features/pricing-matrix/BulkAdjustButton";
import { PricingGuideDialog } from "@features/pricing-matrix/PricingGuideDialog";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { formatDuration } from "@shared/lib/duration";
import { toast } from "@shared/lib/toast";
import { blockNonDecimalKeys } from "@shared/lib/number-input";
import { GroupToggle } from "@shared/ui/GroupToggle";
import { COLLAPSE_MOTION } from "@shared/ui/collapse-motion";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { EmptyState } from "@shared/ui/glass/EmptyState";
import { Input } from "@shared/ui/glass/Input";
import { Section } from "@shared/ui/glass/Section";
import { Button } from "@shared/ui/Button";
import { IconButton } from "@shared/ui/IconButton";
import { EYEBROW_CLASS } from "@shared/ui/classes";


// an unsaved edit in a matrix field
const EDITED_CLASS = "ring-1 ring-warning/60";

const cellInputClassName =
  "w-24 shrink-0 [&_input]:text-right [&_input]:tabular-nums";

interface PricingMatrixProps {
  book: PriceBook;
  onChanged: () => void;
  onSaved: (book: PriceBook) => void;
}

/** Unsaved edits. A base price is always a string; an override's null removes its pin. */
type Drafts = Readonly<Record<string, string | null>>;

const baseKey = (row: PriceBookRow) => `base:${row.kind}:${row.ref_id}`;
const cellKey = (row: PriceBookRow, currency: Currency) => `cell:${row.kind}:${row.ref_id}:${currency}`;

function isValidPrice(value: string): boolean {
  return value.trim() !== "" && Number(value) > 0;
}

function buildBody(book: PriceBook, drafts: Drafts): SetMatrixPricesBody {
  const body: SetMatrixPricesBody = {
    plan_base_prices: [],
    plan_overrides: [],
    addon_base_prices: [],
    addon_overrides: [],
  };
  for (const row of [...book.plans, ...book.addons]) {
    const base = drafts[baseKey(row)];
    if (typeof base === "string") {
      if (row.kind === "addon") body.addon_base_prices.push({ addon_id: row.ref_id, base_price: base });
      else if (row.plan_id !== null && row.days !== null) {
        body.plan_base_prices.push({ plan_id: row.plan_id, days: row.days, base_price: base });
      }
    }
    for (const { currency } of row.cells) {
      const price = drafts[cellKey(row, currency)];
      if (price === undefined) continue;
      if (row.kind === "addon") body.addon_overrides.push({ addon_id: row.ref_id, currency, price });
      else if (row.plan_id !== null && row.days !== null) {
        body.plan_overrides.push({ plan_id: row.plan_id, days: row.days, currency, price });
      }
    }
  }
  return body;
}

export function PricingMatrix({ book, onChanged, onSaved }: PricingMatrixProps) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  // the dialog previews the change before applying it
  const canBulkAdjust =
    permissions.includes("PRICING_BASE_ADJUST_MANAGE") && permissions.includes("PRICING_PREVIEW_VIEW");

  const canEditAny =
    permissions.includes("PRICING_MATRIX_MANAGE") &&
    (permissions.includes("PLANS_DURATION_BASE_PRICE_MANAGE") ||
      permissions.includes("PLANS_PRICE_OVERRIDE_MANAGE") ||
      permissions.includes("ADDONS_PRICES_MANAGE") ||
      permissions.includes("ADDONS_PRICE_OVERRIDE_MANAGE"));

  const [drafts, setDrafts] = useState<Drafts>({});
  const [isSaving, setIsSaving] = useState(false);
  const dirty = Object.keys(drafts).length > 0;
  const isInvalid = Object.values(drafts).some((value) => value !== null && !isValidPrice(value));

  const setDraft = (key: string, value: string | null | undefined) =>
    setDrafts((prev) => {
      const { [key]: _dropped, ...rest } = prev;
      return value === undefined ? rest : { ...rest, [key]: value };
    });

  const handleSave = async () => {
    setIsSaving(true);
    try {
      onSaved(await setMatrixPrices(buildBody(book, drafts)));
      setDrafts({});
      toast.success(t("pricing.matrix.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("pricing.matrix.saveError")));
    } finally {
      setIsSaving(false);
    }
  };

  // read by the blocker, which keeps the function it was first given
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) => dirtyRef.current && currentLocation.pathname !== nextLocation.pathname,
  );
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const [collapsedSections, setCollapsedSections] = useState<ReadonlySet<string>>(new Set());
  const toggleSection = (section: string) =>
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (!next.delete(section)) next.add(section);
      return next;
    });

  const planGroups: PriceBookRow[][] = [];
  for (const row of book.plans) {
    const group = planGroups.find((rows) => rows[0].plan_id === row.plan_id);
    if (group) group.push(row);
    else planGroups.push([row]);
  }
  const rows: { row: PriceBookRow }[] = [
    ...book.plans.map((row) => ({ row })),
    ...book.addons.map((row) => ({ row })),
  ];

  return (
    <Section
      className="[&>header>div.min-w-0]:min-w-48"
      icon={Table2}
      title={t("pricing.matrix.title")}
      description={t("pricing.matrix.description")}
      aside={
        <>
          <PricingGuideDialog />
          {canBulkAdjust && (
            <BulkAdjustButton
              planGroups={planGroups}
              anchorCurrency={book.settings.anchor_currency}
              onChanged={onChanged}
            />
          )}
        </>
      }
      footer={
        rows.length > 0 &&
        canEditAny && (
          <SaveFooter
            dirty={dirty}
            saving={isSaving}
            disabled={isInvalid}
            onSave={() => void handleSave()}
            beside={
              <Button variant="glass" disabled={!dirty || isSaving} onClick={() => setDrafts({})}>
                {t("common.reset")}
              </Button>
            }
          />
        )
      }
    >
      {rows.length === 0 ? (
        <EmptyState text={t("pricing.matrix.empty")} />
      ) : (
        <div className="relative -mx-2 mt-4 -mb-1 overflow-x-auto px-2 py-1">
          {/* separate borders: collapsed tables ignore border-radius on cells */}
          <table className="w-full min-w-[720px] border-separate border-spacing-0 text-sm">
            <thead>
              <tr className={`whitespace-nowrap text-left ${EYEBROW_CLASS} [&>th]:border-b [&>th]:border-border [&>th]:px-3 [&>th]:py-2`}>
                <th>{t("pricing.matrix.item")}</th>
                <th>{t("pricing.matrix.basePrice")}</th>
                {CURRENCIES.map((currency) => (
                  <th key={currency}>
                    <span className="inline-flex items-center gap-1.5">
                      {currency}
                      {currency === book.settings.anchor_currency && (
                        <span className="rounded-full bg-accent px-1.5 py-px text-[11px] tracking-wide text-primary">
                          {t("pricing.anchor.badge")}
                        </span>
                      )}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* a section per plan, its durations as rows */}
              {planGroups.map((group) => {
                const section = `plan:${group[0].plan_id}`;
                return (
                  <Fragment key={section}>
                    <SectionHeader
                      label={group[0].name}
                      count={group.length}
                      isCollapsed={collapsedSections.has(section)}
                      onToggle={() => toggleSection(section)}
                    />
                    <AnimatePresence initial={false}>
                      {!collapsedSections.has(section) &&
                        group.map((row, index) => (
                          <MatrixRow
                            key={`plan_duration-${row.ref_id}`}
                            row={row}
                            isLast={index === group.length - 1}
                            anchorCurrency={book.settings.anchor_currency}
                            drafts={drafts}
                            onDraft={setDraft}
                          />
                        ))}
                    </AnimatePresence>
                  </Fragment>
                );
              })}
              {book.addons.length > 0 && (
                <SectionHeader
                  label={t("pricing.matrix.addonsSection")}
                  count={book.addons.length}
                  isCollapsed={collapsedSections.has("addons")}
                  onToggle={() => toggleSection("addons")}
                />
              )}
              <AnimatePresence initial={false}>
                {!collapsedSections.has("addons") &&
                  book.addons.map((row, index) => (
                    <MatrixRow
                      key={`addon-${row.ref_id}`}
                      row={row}
                      isLast={index === book.addons.length - 1}
                      anchorCurrency={book.settings.anchor_currency}
                      drafts={drafts}
                      onDraft={setDraft}
                    />
                  ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      )}

      {blocker.state === "blocked" && (
        <ConfirmDialog
          title={t("pricing.matrix.leave.title")}
          message={t("pricing.matrix.leave.message")}
          confirmLabel={t("pricing.matrix.leave.confirm")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => blocker.proceed()}
          onCancel={() => blocker.reset()}
        />
      )}
    </Section>
  );
}

function SectionHeader({
  label,
  count,
  isCollapsed,
  onToggle,
}: {
  label: string;
  count: number;
  isCollapsed: boolean;
  onToggle: () => void;
}) {
  return (
    <tr>
      <td colSpan={2 + CURRENCIES.length} className="pb-1 pt-3">
        <GroupToggle open={!isCollapsed} onToggle={onToggle} label={label} count={count} />
      </td>
    </tr>
  );
}

// Row height can't animate on a <tr>, so each cell's content collapses instead;
// the vertical padding lives inside it so the row shrinks to nothing.
function Cell({ className, children }: { className?: string; children?: ReactNode }) {
  return (
    <td className={className}>
      <motion.div {...COLLAPSE_MOTION} className="py-3">
        {children}
      </motion.div>
    </td>
  );
}

function MatrixRow({
  row,
  isLast,
  anchorCurrency,
  drafts,
  onDraft,
}: {
  row: PriceBookRow;
  isLast: boolean;
  anchorCurrency: Currency;
  drafts: Drafts;
  onDraft: (key: string, value: string | null | undefined) => void;
}) {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const isAddon = row.kind === "addon";
  const canSave = permissions.includes("PRICING_MATRIX_MANAGE");
  // a free trial is free in every currency: pricing it here would turn it into a paid one
  const canEditBase =
    !row.is_free_trial &&
    canSave &&
    permissions.includes(isAddon ? "ADDONS_PRICES_MANAGE" : "PLANS_DURATION_BASE_PRICE_MANAGE");
  const canOverride =
    !row.is_free_trial &&
    canSave &&
    permissions.includes(isAddon ? "ADDONS_PRICE_OVERRIDE_MANAGE" : "PLANS_PRICE_OVERRIDE_MANAGE");

  const baseDraft = drafts[baseKey(row)];
  const baseValue = typeof baseDraft === "string" ? baseDraft : row.base_price;

  return (
    <tr
      // border on every row but the section's last, same as divide-y (which borders the bottom);
      // it takes 1px of the padding: every row stays 60px
      className={`[&>td]:border-border/50 [&>td]:px-3 [&>td]:transition-colors hover:[&>td]:bg-white/[0.04] [&>td:first-child]:rounded-l-full [&>td:last-child]:rounded-r-full ${
        isLast ? "" : "[&>td]:border-b [&>td>div]:pb-[11px]"
      }`}
    >
      <Cell className="min-w-40 font-medium text-foreground">
        {row.days === null ? row.name : formatDuration(row.days, t)}
        {row.is_free_trial && (
          <span className="block text-xs font-normal text-muted-foreground">{t("pricing.matrix.freeTrial")}</span>
        )}
      </Cell>
      <Cell>
        <Input
          type="number"
          onKeyDown={blockNonDecimalKeys}
          step="0.01"
          min="0"
          value={baseValue}
          onChange={(event) =>
            onDraft(baseKey(row), event.target.value === row.base_price ? undefined : event.target.value)
          }
          aria-invalid={baseDraft !== undefined && !isValidPrice(baseValue)}
          disabled={!canEditBase}
          className={`${cellInputClassName} ${baseDraft === undefined ? "" : EDITED_CLASS}`}
        />
      </Cell>
      {CURRENCIES.map((currency) => {
        const cell = row.cells.find((c) => c.currency === currency);
        if (!cell) return <Cell key={currency} />;
        if (currency === anchorCurrency) {
          return (
            <Cell key={currency}>
              <div className="flex items-center gap-1">
                <Input type="number" value={cell.amount} disabled className={cellInputClassName} />
                {/* pin-sized gap, so the anchor column lines up with the others */}
                <span className="size-6 shrink-0" />
              </div>
            </Cell>
          );
        }
        return (
          <Cell key={currency}>
            <OverrideCell row={row} cell={cell} draft={drafts[cellKey(row, currency)]} canOverride={canOverride} onDraft={onDraft} />
          </Cell>
        );
      })}
    </tr>
  );
}

function OverrideCell({
  row,
  cell,
  draft,
  canOverride,
  onDraft,
}: {
  row: PriceBookRow;
  cell: PriceBookCell;
  draft: string | null | undefined;
  canOverride: boolean;
  onDraft: (key: string, value: string | null | undefined) => void;
}) {
  const key = cellKey(row, cell.currency);
  const isPinned = draft === undefined ? cell.is_pinned : draft !== null;
  const value = typeof draft === "string" ? draft : cell.amount;

  const handleChange = (next: string) => {
    // typing the shown price back is no edit, whether or not it's pinned
    onDraft(key, next === cell.amount ? undefined : next);
  };
  const handlePin = () => {
    if (isPinned) onDraft(key, cell.is_pinned ? null : undefined);
    else onDraft(key, cell.is_pinned ? undefined : value);
  };

  return (
    <div className="flex items-center gap-1">
      <Input
        type="number"
        onKeyDown={blockNonDecimalKeys}
        step="0.01"
        min="0"
        value={value}
        onChange={(event) => handleChange(event.target.value)}
        aria-invalid={typeof draft === "string" && !isValidPrice(draft)}
        disabled={!canOverride}
        className={`${cellInputClassName} ${
          draft !== undefined
            ? EDITED_CLASS
            : isPinned
              ? "ring-1 ring-primary/35 [&_input]:font-medium [&_input]:text-primary"
              : ""
        }`}
      />
      <IconButton size="6" onClick={handlePin} disabled={!canOverride}>
        {isPinned ? <Pin className="size-4 text-primary" /> : <PinOff className="size-4" />}
      </IconButton>
    </div>
  );
}
