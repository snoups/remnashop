import type { ParseKeys } from "i18next";
import { CircleCheck, RefreshCw, Server, Store, type LucideIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  SUBSCRIPTION_STATUS_BADGE_TONE,
  getSubscriptionPanelDiff,
  pullSubscriptionFromPanel,
  pushSubscriptionToPanel,
  type PanelFieldDiff,
  type SquadReplacements,
  type SubscriptionListItem,
  type SubscriptionPanelDiff,
  type SubscriptionStatus,
} from "@entities/subscriptions/api";
import { useAccountPermissions } from "@entities/user/use-current-user";
import { dropAllSquads } from "@features/panel-sync/drop-all-squads";
import { SquadReplacementsField } from "@features/panel-sync/SquadReplacements";
import { getErrorMessage } from "@shared/api/http";
import { DAY_MS } from "@shared/lib/period";
import { formatDateTime } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { GLASS_DIALOG_FOOTER_CLASS, GLASS_DIALOG_PAD_CLASS, GLASS_PLATE_CLASS } from "@shared/ui/classes";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { useSquadName } from "@features/subscription-edit/use-squad-name";
import { Spinner } from "@shared/ui/Spinner";

// machine values the panel and the shop store verbatim
const MONO_FIELDS: ReadonlySet<string> = new Set(["url", "telegram_id"]);
const SQUAD_FIELDS: ReadonlySet<string> = new Set(["internal_squads", "external_squad"]);

type SquadMark = "plain" | "gone" | "onlyShop" | "onlyPanel";

const SQUAD_CLASS: Record<SquadMark, string> = {
  plain: "border-white/[0.08] bg-white/[0.04] text-foreground",
  gone: "border-error/35 bg-error/[0.08] text-error line-through decoration-error/60",
  onlyShop: "border-warning/35 bg-warning/[0.08] text-warning",
  onlyPanel: "border-primary/35 bg-accent text-accent-foreground",
};


const splitSquads = (value: string) => (value ? value.split(",") : []);

type DiffState = { kind: "loading" } | { kind: "error" } | { kind: "ready"; diff: SubscriptionPanelDiff };

interface PanelSyncDialogProps {
  subscription: SubscriptionListItem;
  onApplied: (updated: SubscriptionListItem) => void;
  onClose: () => void;
}

export function PanelSyncDialog({ subscription, onApplied, onClose }: PanelSyncDialogProps) {
  return (
    <Modal onClose={onClose} size="lg">
      <PanelSyncBody subscription={subscription} onApplied={onApplied} />
    </Modal>
  );
}

function PanelSyncBody({ subscription, onApplied }: Omit<PanelSyncDialogProps, "onClose">) {
  const { t } = useTranslation();
  const permissions = useAccountPermissions(subscription.user_id);
  const close = useModalClose();
  const [state, setState] = useState<DiffState>({ kind: "loading" });
  const [busy, setBusy] = useState(false);
  const [replacements, setReplacements] = useState<SquadReplacements>({});

  useEffect(() => {
    const controller = new AbortController();
    getSubscriptionPanelDiff(subscription.id, controller.signal).then(
      (diff) => {
        setReplacements(dropAllSquads(diff.missing_squads));
        setState({ kind: "ready", diff });
      },
      () => {
        if (!controller.signal.aborted) setState({ kind: "error" });
      },
    );
    return () => controller.abort();
  }, [subscription.id]);

  const run = async (action: () => Promise<SubscriptionListItem>, done: string) => {
    setBusy(true);
    try {
      onApplied(await action());
      toast.success(done);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("subscriptions.panelSync.error")));
    } finally {
      setBusy(false);
    }
  };

  const canPull = permissions.includes("SUBSCRIPTIONS_PULL_FROM_PANEL");
  const canPush = permissions.includes("SUBSCRIPTIONS_PUSH_TO_PANEL");
  const missing = state.kind === "ready" && state.diff.missing_in_panel;
  const inSync = state.kind === "ready" && !missing && state.diff.fields.length === 0;

  return (
    <>
      <DialogHeader icon={RefreshCw} title={t("subscriptions.panelSync.title")} />

      <div className={GLASS_DIALOG_PAD_CLASS}>
        {state.kind === "loading" && <Spinner size="card" />}
        {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
        {missing && <p className="text-sm leading-relaxed text-foreground/80">{t("subscriptions.panelSync.missing")}</p>}
        {inSync && <EmptyState text={t("subscriptions.panelSync.inSync")} icon={CircleCheck} />}
        {state.kind === "ready" && state.diff.fields.length > 0 && (
          <PanelDiffTable
            diff={state.diff}
            replacements={
              canPush && state.diff.missing_squads.length > 0 && (
                <SquadReplacementsField
                  missing={state.diff.missing_squads}
                  value={replacements}
                  onChange={setReplacements}
                />
              )
            }
          />
        )}
      </div>

      <div className={GLASS_DIALOG_FOOTER_CLASS}>
        {canPull && (
          <Button
            variant="glass"
            className="flex-1"
            disabled={busy || state.kind !== "ready" || inSync}
            onClick={() =>
              void run(() => pullSubscriptionFromPanel(subscription.id), t("subscriptions.panelSync.pulled"))
            }
          >
            {t("subscriptions.panelSync.pull")}
          </Button>
        )}
        {canPush && (
          <Button
            variant="glassAccent"
            className="flex-1"
            disabled={busy || state.kind !== "ready" || inSync}
            onClick={() =>
              void run(
                () => pushSubscriptionToPanel(subscription.id, replacements),
                t("subscriptions.panelSync.pushed"),
              )
            }
          >
            {t("subscriptions.panelSync.push")}
          </Button>
        )}
      </div>
    </>
  );
}

/** The fields that differ: Remnashop's value beside Remnawave's, squads marked by where they are. */
function PanelDiffTable({ diff, replacements }: { diff: SubscriptionPanelDiff; replacements: ReactNode }) {
  const { t, i18n } = useTranslation();
  // a squad the panel doesn't name is shown whole, so it can be looked up
  const squadName = useSquadName((uuid) => uuid);
  const gone = new Set(diff.missing_squads.map((squad) => squad.uuid));

  const squadMark = (uuid: string, other: string[], side: "shop" | "panel"): SquadMark => {
    if (gone.has(uuid)) return "gone";
    if (other.includes(uuid)) return "plain";
    return side === "shop" ? "onlyShop" : "onlyPanel";
  };

  const renderValue = (field: PanelFieldDiff, side: "shop" | "panel"): ReactNode => {
    const raw = field[side];
    if (SQUAD_FIELDS.has(field.field)) {
      const other = splitSquads(field[side === "shop" ? "panel" : "shop"]);
      const squads = splitSquads(raw);
      if (squads.length === 0) return <span className="text-muted-foreground">{t("common.none")}</span>;
      return (
        <span className="flex flex-wrap gap-1">
          {squads.map((uuid) => {
            const mark = squadMark(uuid, other, side);
            const name = squadName(uuid);
            const isNamed = name !== uuid;
            return (
              <span
                key={uuid}
                className={`inline-flex min-h-6 items-center rounded-lg border px-2.5 py-0.5 text-xs ${
                  isNamed ? "whitespace-nowrap" : "break-all font-mono"
                } ${SQUAD_CLASS[mark]}`}
              >
                {name}
              </span>
            );
          })}
        </span>
      );
    }
    if (!raw) return <span className="text-muted-foreground">{t("common.none")}</span>;
    switch (field.field) {
      case "status": {
        const status = raw as SubscriptionStatus;
        return (
          <span>
            <Badge tone={SUBSCRIPTION_STATUS_BADGE_TONE[status]}>{t(`subscriptions.status.${status}`)}</Badge>
          </span>
        );
      }
      case "expire_at":
        return <span className="tabular-nums">{formatDateTime(raw, i18n.language)}</span>;
      case "traffic_limit":
        return (
          <span className="tabular-nums">
            {raw === "0" ? t("subscriptions.unlimited") : t("subscriptions.panelSync.gb", { value: raw })}
          </span>
        );
      case "device_limit":
        return <span className="tabular-nums">{raw === "0" ? t("subscriptions.unlimited") : raw}</span>;
      case "traffic_limit_strategy":
        return <span>{t(`subscriptions.edit.strategy.${raw}` as ParseKeys)}</span>;
      default:
        return <span className={`break-all ${MONO_FIELDS.has(field.field) ? "font-mono text-xs" : ""}`}>{raw}</span>;
    }
  };

  const expiryShift = (field: PanelFieldDiff): string | null => {
    if (field.field !== "expire_at" || !field.shop || !field.panel) return null;
    const days = Math.round((new Date(field.panel).getTime() - new Date(field.shop).getTime()) / DAY_MS);
    if (days === 0) return null;
    return t(days < 0 ? "subscriptions.panelSync.earlier" : "subscriptions.panelSync.later", { days: Math.abs(days) });
  };

  const rows = diff.fields.map((field) => {
    const shift = expiryShift(field);
    return (
      <div
        key={field.field}
        className="col-span-3 grid grid-cols-subgrid items-start border-t border-white/[0.06] py-2.5 text-sm"
      >
        <span className="pt-0.5 text-xs text-muted-foreground">
          {t(`subscriptions.panelSync.fieldNames.${field.field}` as ParseKeys)}
        </span>
        {renderValue(field, "shop")}
        <span className="flex flex-col gap-0.5">
          {renderValue(field, "panel")}
          {shift && <span className="text-xs text-muted-foreground">{shift}</span>}
        </span>
      </div>
    );
  });

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm leading-relaxed text-foreground/80">{t("subscriptions.panelSync.differs", { count: diff.fields.length })}</p>
      <div className={GLASS_PLATE_CLASS}>
        <div className="grid grid-cols-[96px_minmax(0,1fr)_minmax(0,1fr)] gap-x-3 px-3 pt-3">
          <span />
          <ColumnHead icon={Store}>{t("subscriptions.panelSync.columns.shop")}</ColumnHead>
          <ColumnHead icon={Server}>{t("subscriptions.panelSync.columns.panel")}</ColumnHead>
          {rows}
        </div>
        {replacements && <div className="px-2.5 pb-2.5">{replacements}</div>}
      </div>
    </div>
  );
}

function ColumnHead({ icon: Icon, children }: { icon: LucideIcon; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 pb-1.5 text-xs text-muted-foreground">
      <Icon className="size-3.5" />
      {children}
    </span>
  );
}
