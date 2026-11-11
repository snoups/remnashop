import type { ParseKeys, TFunction } from "i18next";
import {
  AlertTriangle,
  ArrowRight,
  BotOff,
  CalendarClock,
  CloudOff,
  Coins,
  CreditCard,
  DatabaseBackup,
  DatabaseX,
  Gauge,
  HardDrive,
  Hourglass,
  Info,
  KeyRound,
  ListX,
  MailWarning,
  MailX,
  MegaphoneOff,
  MemoryStick,
  Network,
  PackageX,
  ServerCrash,
  ServerOff,
  TimerOff,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import type { BackupKind } from "@entities/backups/api";
import { getAttention } from "@entities/overview/api";
import { UNFULFILLED_STATUS } from "@entities/transactions/api";
import type { AttentionItem, AttentionKind } from "@entities/overview/api";
import { usePermissions } from "@entities/user/use-current-user";
import { formatDateTime } from "@shared/lib/relative-time";
import { readStorage, writeStorage } from "@shared/lib/safe-storage";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";
import { Button } from "@shared/ui/Button";
import { CellText } from "@shared/ui/CellText";
import { IconButton } from "@shared/ui/IconButton";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Section } from "@shared/ui/glass/Section";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import {
  GLASS_DIALOG_BODY_CLASS,
  GLASS_DIALOG_FOOTER_CLASS,
  LIST_BODY_CLASS,
} from "@shared/ui/classes";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { ListRow } from "@shared/ui/ListRow";
import { Modal } from "@shared/ui/Modal";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { NAV_ITEMS, SETTINGS_TABS, isNavItemVisible } from "@widgets/sidebar/nav-items";
import { RUNTIME_PROCESS_LABELS, formatUptime } from "@pages/dashboard/runtime";

// the last column keeps the text clear of the hide button laid over the row
const OPEN_ROW_CLASS = "grid grid-cols-[32px_minmax(0,1fr)_32px] items-center gap-3";

const DISMISSED_KEY = "remnashop_attention_dismissed";

const SEVERITY_TONE = {
  critical: "error",
  warning: "warning",
} as const;

const KIND_ICON: Record<AttentionKind, ComponentType<{ className?: string }>> = {
  process_down: ServerCrash,
  host_disk_full: HardDrive,
  host_memory_high: MemoryStick,
  event_loop_lag: Gauge,
  outbox_stuck: ListX,
  panel_unavailable: CloudOff,
  node_offline: ServerOff,
  gateway_failures: CreditCard,
  smtp_failed: MailX,
  backup_failed: DatabaseX,
  backup_overdue: DatabaseBackup,
  broadcast_failed: MegaphoneOff,
  paid_not_fulfilled: PackageX,
  stale_pending: TimerOff,
  broadcast_stalled: Hourglass,
  email_undeliverable: MailWarning,
  expiring_paid: CalendarClock,
  api_token_expiring: KeyRound,
  bot_webhook: BotOff,
  plan_squads_missing: Network,
  unrated_anchor_amounts: Coins,
};

interface AttentionLink {
  to: string;
  label: ParseKeys;
  allowed: (permissions: Permission[]) => boolean;
}

function settingsTabAllowed(key: (typeof SETTINGS_TABS)[number]["key"]) {
  return (permissions: Permission[]) =>
    SETTINGS_TABS.some((tab) => tab.key === key && tab.anyOf.some((p) => permissions.includes(p)));
}

// `status` is read once by the transactions page's status filter
const transactionsLink = (status: string): AttentionLink => ({
  to: `/dashboard/transactions?status=${status}`,
  label: "dashboard.attention.actions.transactions",
  allowed: (permissions) => NAV_ITEMS.some((item) => item.key === "transactions" && isNavItemVisible(item, permissions)),
});

const broadcastsLink: AttentionLink = {
  to: "/dashboard/broadcasts",
  label: "dashboard.attention.actions.broadcasts",
  allowed: (permissions) => NAV_ITEMS.some((item) => item.key === "broadcasts" && isNavItemVisible(item, permissions)),
};

const backupsLink: AttentionLink = {
  to: "/dashboard/settings/backups",
  label: "dashboard.attention.actions.backups",
  allowed: settingsTabAllowed("backups"),
};

// node and panel items have none: those are managed in Remnawave; processes and
// the event queue are fixed on the server
const KIND_LINK: Partial<Record<AttentionKind, AttentionLink>> = {
  gateway_failures: {
    to: "/dashboard/settings/gateways",
    label: "dashboard.attention.actions.gateways",
    allowed: settingsTabAllowed("gateways"),
  },
  smtp_failed: {
    to: "/dashboard/settings/cabinet",
    label: "dashboard.attention.actions.email",
    allowed: settingsTabAllowed("cabinet"),
  },
  backup_failed: backupsLink,
  backup_overdue: backupsLink,
  broadcast_failed: broadcastsLink,
  broadcast_stalled: broadcastsLink,
  paid_not_fulfilled: transactionsLink(UNFULFILLED_STATUS),
  stale_pending: transactionsLink("PENDING"),
  expiring_paid: {
    to: "/dashboard/analytics/retention",
    label: "dashboard.attention.actions.retention",
    allowed: (permissions) => permissions.includes("ANALYTICS_RETENTION_VIEW"),
  },
  api_token_expiring: {
    to: "/dashboard/settings/api-tokens",
    label: "dashboard.attention.actions.apiTokens",
    allowed: settingsTabAllowed("apiTokens"),
  },
  bot_webhook: {
    to: "/dashboard/settings/bot",
    label: "dashboard.attention.actions.bot",
    allowed: settingsTabAllowed("bot"),
  },
  plan_squads_missing: {
    to: "/dashboard/plans",
    label: "dashboard.attention.actions.plans",
    allowed: (permissions) => NAV_ITEMS.some((item) => item.key === "plans" && isNavItemVisible(item, permissions)),
  },
  unrated_anchor_amounts: {
    to: "/dashboard/settings/pricing",
    label: "dashboard.attention.actions.pricing",
    allowed: settingsTabAllowed("pricing"),
  },
};

function itemText(item: AttentionItem, t: TFunction, language: string): { title: string; sub: string | null } {
  const formatted = item.count.toLocaleString(language);
  const since = item.since ? formatDateTime(item.since, language) : "";
  const counted = (key: ParseKeys) => t(key, { count: item.count, formatted, since });
  // how long ago `since` was, in the form that follows «более»
  const waited = item.since ? formatUptime(t, (Date.now() - Date.parse(item.since)) / 1000, "after") : "";
  switch (item.kind) {
    case "process_down": {
      const process = item.subject ?? "";
      return {
        title: t("dashboard.attention.processDown.title", { process: RUNTIME_PROCESS_LABELS[process] ?? process }),
        sub: process === "worker" || process === "scheduler" ? t(`dashboard.attention.processDown.${process}`) : null,
      };
    }
    case "host_disk_full":
    case "host_memory_high":
      // count: the percent used
      return {
        title: t(`dashboard.attention.${KIND_KEY[item.kind]}.title` as ParseKeys),
        sub: t(`dashboard.attention.${KIND_KEY[item.kind]}.sub` as ParseKeys, { percent: item.count }),
      };
    case "event_loop_lag": {
      const process = item.subject ?? "";
      return {
        title: t("dashboard.attention.eventLoopLag.title", { process: RUNTIME_PROCESS_LABELS[process] ?? process }),
        sub: t("dashboard.attention.eventLoopLag.sub"),
      };
    }
    case "outbox_stuck":
      return {
        title: t("dashboard.attention.outboxStuck.title"),
        sub: t("dashboard.attention.outboxStuck.sub", {
          count: item.count,
          formatted,
          duration: waited,
        }),
      };
    case "panel_unavailable":
      return {
        title: t("dashboard.attention.panelUnavailable.title"),
        sub: t("dashboard.attention.panelUnavailable.sub"),
      };
    case "node_offline":
      return {
        title: t("dashboard.attention.nodeOffline.title", { node: item.subject ?? "" }),
        sub: since ? t("dashboard.attention.nodeOffline.sub", { since }) : null,
      };
    case "gateway_failures":
      return {
        title: t("dashboard.attention.gatewayFailures.title", {
          gateway: t(`settings.gateways.types.${item.subject}` as ParseKeys, { defaultValue: item.subject ?? "" }),
        }),
        sub: counted("dashboard.attention.gatewayFailures.sub"),
      };
    case "smtp_failed":
      return {
        title: t("dashboard.attention.smtpFailed.title"),
        sub: t("dashboard.attention.smtpFailed.sub", {
          profile: t(item.subject === "bulk" ? "dashboard.attention.smtpFailed.bulk" : "dashboard.attention.smtpFailed.main"),
          since,
        }),
      };
    case "backup_failed": {
      const kind = item.subject ? t(`backups.kind.${item.subject as BackupKind}`) : null;
      return {
        title: t("dashboard.attention.backupFailed.title"),
        sub: [kind, since].filter(Boolean).join(" · ") || null,
      };
    }
    case "backup_overdue":
      return {
        title: t("dashboard.attention.backupOverdue.title"),
        sub: since ? t("dashboard.attention.backupOverdue.sub", { since }) : t("dashboard.attention.backupOverdue.never"),
      };
    case "broadcast_failed":
      return {
        title: t("dashboard.attention.broadcastFailed.title", { name: item.subject ?? "" }),
        sub: since ? t("dashboard.attention.broadcastFailed.sub", { since }) : null,
      };
    case "broadcast_stalled":
      return {
        title: t("dashboard.attention.broadcastStalled.title", { name: item.subject ?? "" }),
        sub: waited ? t("dashboard.attention.broadcastStalled.sub", { duration: waited }) : null,
      };
    case "paid_not_fulfilled":
      return {
        title: t("dashboard.attention.paidNotFulfilled.title"),
        sub: counted("dashboard.attention.paidNotFulfilled.sub"),
      };
    case "stale_pending":
      return { title: t("dashboard.attention.stalePending.title"), sub: counted("dashboard.attention.stalePending.sub") };
    case "email_undeliverable":
      return {
        title: t("dashboard.attention.emailUndeliverable.title"),
        sub: counted("dashboard.attention.emailUndeliverable.sub"),
      };
    case "expiring_paid": {
      // subject: how many of them end within a day
      const urgent = Number(item.subject ?? 0);
      const base = counted("dashboard.attention.expiringPaid.sub");
      return {
        title: t("dashboard.attention.expiringPaid.title"),
        sub: urgent > 0 ? t("dashboard.attention.expiringPaid.urgent", { base, urgent: urgent.toLocaleString(language) }) : base,
      };
    }
    case "api_token_expiring":
      return {
        title: t("dashboard.attention.apiTokenExpiring.title", { name: item.subject ?? "" }),
        sub:
          item.since && since
            ? t("dashboard.attention.apiTokenExpiring.sub", {
                duration: formatUptime(t, Math.max(0, Date.parse(item.since) - Date.now()) / 1000, "in"),
                since,
              })
            : null,
      };
    case "bot_webhook":
      return {
        title: t("dashboard.attention.botWebhook.title"),
        sub: item.subject
          ? t("dashboard.attention.botWebhook.error", { error: item.subject })
          : t("dashboard.attention.botWebhook.noWebhook"),
      };
    case "plan_squads_missing":
      return {
        title: t("dashboard.attention.planSquadsMissing.title", { name: item.subject ?? "" }),
        sub: t(
          item.count === 1
            ? "dashboard.attention.planSquadsMissing.subOne"
            : "dashboard.attention.planSquadsMissing.subMany",
        ),
      };
    case "unrated_anchor_amounts":
      // subject: their currencies
      return {
        title: t("dashboard.attention.unratedAnchorAmounts.title"),
        sub: t("dashboard.attention.unratedAnchorAmounts.sub", {
          count: item.count,
          formatted,
          currencies: item.subject ?? "",
        }),
      };
  }
}

// i18n key of each kind under dashboard.attention
const KIND_KEY: Record<AttentionKind, string> = {
  process_down: "processDown",
  host_disk_full: "hostDiskFull",
  host_memory_high: "hostMemoryHigh",
  event_loop_lag: "eventLoopLag",
  outbox_stuck: "outboxStuck",
  panel_unavailable: "panelUnavailable",
  node_offline: "nodeOffline",
  gateway_failures: "gatewayFailures",
  smtp_failed: "smtpFailed",
  backup_failed: "backupFailed",
  backup_overdue: "backupOverdue",
  broadcast_failed: "broadcastFailed",
  broadcast_stalled: "broadcastStalled",
  paid_not_fulfilled: "paidNotFulfilled",
  stale_pending: "stalePending",
  email_undeliverable: "emailUndeliverable",
  expiring_paid: "expiringPaid",
  api_token_expiring: "apiTokenExpiring",
  bot_webhook: "botWebhook",
  plan_squads_missing: "planSquadsMissing",
  unrated_anchor_amounts: "unratedAnchorAmounts",
};

function ExplainBlock({ icon, title, text }: { icon: ComponentType<{ className?: string }>; title: string; text: string }) {
  return (
    <DialogCard variant="form" title={title} icon={icon}>
      <p className="text-sm leading-relaxed text-foreground/80">{text}</p>
    </DialogCard>
  );
}

function AttentionDialog({ item, onClose }: { item: AttentionItem; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const permissions = usePermissions();
  const link = KIND_LINK[item.kind];
  const { title, sub } = itemText(item, t, i18n.language);
  const key = `dashboard.attention.${KIND_KEY[item.kind]}`;
  const why =
    item.kind === "process_down"
      ? `${key}.${item.subject === "scheduler" ? "whyScheduler" : "whyWorker"}`
      : `${key}.why`;

  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <DialogHeader
        icon={KIND_ICON[item.kind]}
        title={title}
        subtitle={sub}
        danger={item.severity === "critical"}
        warning={item.severity === "warning"}
      />
      <div className={GLASS_DIALOG_BODY_CLASS}>
        <div className="flex flex-col gap-3">
          <ExplainBlock icon={Info} title={t("dashboard.attention.sections.what")} text={t(`${key}.what` as ParseKeys)} />
          <ExplainBlock icon={AlertTriangle} title={t("dashboard.attention.sections.why")} text={t(why as ParseKeys)} />
          <ExplainBlock icon={Wrench} title={t("dashboard.attention.sections.fix")} text={t(`${key}.fix` as ParseKeys)} />
        </div>
      </div>
      {link && link.allowed(permissions) && (
        <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0`}>
          <Button variant="glassAccent" className="flex-1" onClick={() => navigate(link.to)}>
            {t(link.label)}
            <ArrowRight className="size-4" />
          </Button>
        </div>
      )}
    </Modal>
  );
}

// a hidden item comes back once its object or start time changes, or its count grows
const fingerprint = (item: AttentionItem) => `${item.kind}|${item.subject ?? ""}|${item.since ?? ""}`;

// fingerprint → count when hidden
function readDismissed(): Record<string, number> {
  try {
    return JSON.parse(readStorage(DISMISSED_KEY) ?? "{}") as Record<string, number>;
  } catch {
    return {};
  }
}

function AttentionRow({ item, onDismiss }: { item: AttentionItem; onDismiss: () => void }) {
  const { t, i18n } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const { title, sub } = itemText(item, t, i18n.language);

  return (
    <>
      {/* rounded like the row: the list's divider shadow lands on this wrapper */}
      <div className="relative rounded-full">
        <ListRow className={OPEN_ROW_CLASS} onClick={() => setIsOpen(true)}>
          <IconCircle icon={KIND_ICON[item.kind]} tone={SEVERITY_TONE[item.severity]} />
          <CellText title={title} sub={sub} />
        </ListRow>
        <IconButton size="8" className="absolute right-3.5 top-1/2 -translate-y-1/2" onClick={onDismiss}>
          <X className="size-4" />
        </IconButton>
      </div>
      {isOpen && <AttentionDialog item={item} onClose={() => setIsOpen(false)} />}
    </>
  );
}

export function AttentionCard({ refreshKey }: { refreshKey: number }) {
  const { t, i18n } = useTranslation();
  const [state] = useAsyncResource(getAttention, { deps: [refreshKey], keepData: true });

  const [dismissed, setDismissed] = useState(readDismissed);

  const all = state.kind === "ready" ? state.data.items : [];
  // an item that went away is forgotten, so the same problem shows again when it returns
  const live = new Set(all.map(fingerprint));
  const active = Object.fromEntries(Object.entries(dismissed).filter(([key]) => live.has(key)));
  const items = all.filter((item) => !(fingerprint(item) in active && item.count <= active[fingerprint(item)]));
  const critical = items.filter((item) => item.severity === "critical").length;
  const warning = items.length - critical;
  const activeJson = JSON.stringify(active);

  useEffect(() => {
    if (state.kind === "ready") writeStorage(DISMISSED_KEY, activeJson);
  }, [state.kind, activeJson]);

  const dismiss = (item: AttentionItem) => setDismissed({ ...active, [fingerprint(item)]: item.count });

  // only when something needs a look: nothing while loading or when the list comes back empty
  if (state.kind === "loading" || (state.kind === "ready" && items.length === 0)) return null;

  return (
    <Section
      icon={AlertTriangle}
      title={t("dashboard.attention.title")}
      description={t("dashboard.attention.description")}
      aside={
        (critical > 0 || warning > 0) && (
          <>
            {critical > 0 && (
              <StatusPill tone="error">
                {t("dashboard.attention.critical", { value: critical.toLocaleString(i18n.language) })}
              </StatusPill>
            )}
            {warning > 0 && (
              <StatusPill tone="warning">
                {t("dashboard.attention.warning", { value: warning.toLocaleString(i18n.language) })}
              </StatusPill>
            )}
          </>
        )
      }
    >
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <div className={`${LIST_BODY_CLASS} pt-4`}>
          {items.map((item, index) => (
            <AttentionRow key={`${item.kind}-${item.subject ?? index}`} item={item} onDismiss={() => dismiss(item)} />
          ))}
        </div>
      )}
    </Section>
  );
}
