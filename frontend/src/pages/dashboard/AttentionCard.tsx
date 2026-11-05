import type { ParseKeys, TFunction } from "i18next";
import {
  AlertTriangle,
  ArchiveX,
  Bot,
  CalendarClock,
  CheckCircle2,
  Clock,
  CloudOff,
  CreditCard,
  DatabaseBackup,
  DatabaseZap,
  Hourglass,
  KeyRound,
  MailWarning,
  MailX,
  MegaphoneOff,
  PackageX,
  ServerCrash,
  ServerOff,
} from "lucide-react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import type { BackupKind } from "@entities/backups/api";
import { getAttention } from "@entities/overview/api";
import { UNFULFILLED_STATUS } from "@entities/transactions/api";
import type { AttentionItem, AttentionKind } from "@entities/overview/api";
import { usePermissions } from "@entities/user/use-current-user";
import { formatDateTime } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";
import { Button } from "@shared/ui/Button";
import { CellText } from "@shared/ui/CellText";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Section } from "@shared/ui/glass/Section";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { GLASS_LIST_ROW_CLASS, LIST_BODY_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { NAV_ITEMS, SETTINGS_TABS, isNavItemVisible } from "@widgets/sidebar/nav-items";
import { RUNTIME_PROCESS_LABELS, formatUptime } from "@pages/dashboard/runtime";

const ROW_CLASS = `grid grid-cols-[32px_minmax(0,1fr)_auto] items-center gap-3 ${GLASS_LIST_ROW_CLASS}`;

const SEVERITY_TONE = {
  critical: "error",
  warning: "warning",
} as const;

const KIND_ICON: Record<AttentionKind, ComponentType<{ className?: string }>> = {
  process_down: ServerCrash,
  outbox_stuck: ArchiveX,
  panel_unavailable: CloudOff,
  node_offline: ServerOff,
  gateway_failures: CreditCard,
  smtp_failed: MailX,
  backup_failed: DatabaseZap,
  backup_overdue: DatabaseBackup,
  broadcast_failed: MegaphoneOff,
  paid_not_fulfilled: PackageX,
  stale_pending: Clock,
  broadcast_stalled: Hourglass,
  email_undeliverable: MailWarning,
  expiring_paid: CalendarClock,
  api_token_expiring: KeyRound,
  bot_webhook: Bot,
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
};

function itemText(item: AttentionItem, t: TFunction, language: string): { title: string; sub: string | null } {
  const formatted = item.count.toLocaleString(language);
  const since = item.since ? formatDateTime(item.since, language) : "";
  const counted = (key: ParseKeys) => t(key, { count: item.count, formatted, since });
  switch (item.kind) {
    case "process_down": {
      const process = item.subject ?? "";
      return {
        title: t("dashboard.attention.processDown.title", { process: RUNTIME_PROCESS_LABELS[process] ?? process }),
        sub: process === "worker" || process === "scheduler" ? t(`dashboard.attention.processDown.${process}`) : null,
      };
    }
    case "outbox_stuck":
      return {
        title: t("dashboard.attention.outboxStuck.title"),
        sub: t("dashboard.attention.outboxStuck.sub", {
          count: item.count,
          formatted,
          duration: item.since ? formatUptime(t, (Date.now() - Date.parse(item.since)) / 1000) : "",
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
        title: t("dashboard.attention.broadcastFailed.title"),
        sub: counted("dashboard.attention.broadcastFailed.sub"),
      };
    case "broadcast_stalled":
      return {
        title: t("dashboard.attention.broadcastStalled.title"),
        sub: counted("dashboard.attention.broadcastStalled.sub"),
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
    case "expiring_paid":
      return { title: t("dashboard.attention.expiringPaid.title"), sub: counted("dashboard.attention.expiringPaid.sub") };
    case "api_token_expiring":
      return {
        title: t("dashboard.attention.apiTokenExpiring.title", { name: item.subject ?? "" }),
        sub: since ? t("dashboard.attention.apiTokenExpiring.sub", { since }) : null,
      };
    case "bot_webhook":
      return {
        title: t("dashboard.attention.botWebhook.title"),
        sub: item.subject ?? t("dashboard.attention.botWebhook.noWebhook"),
      };
  }
}

function AttentionRow({ item }: { item: AttentionItem }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const permissions = usePermissions();
  const Icon = KIND_ICON[item.kind];
  const link = KIND_LINK[item.kind];
  const { title, sub } = itemText(item, t, i18n.language);

  return (
    <div className={ROW_CLASS}>
      <IconCircle icon={Icon} tone={SEVERITY_TONE[item.severity]} />
      <CellText title={title} sub={sub} />
      {link && link.allowed(permissions) ? (
        <Button variant="glass" size="sm" onClick={() => navigate(link.to)}>
          {t(link.label)}
        </Button>
      ) : (
        <span />
      )}
    </div>
  );
}

export function AttentionCard({ refreshKey }: { refreshKey: number }) {
  const { t, i18n } = useTranslation();
  const [state] = useAsyncResource(getAttention, { deps: [refreshKey], keepData: true });

  const items = state.kind === "ready" ? state.data.items : [];
  const sorted = [...items].sort((a, b) => Number(a.severity !== "critical") - Number(b.severity !== "critical"));
  const critical = items.filter((item) => item.severity === "critical").length;
  const warning = items.length - critical;

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
            {warning > 0 && <StatusPill tone="warning">{warning.toLocaleString(i18n.language)}</StatusPill>}
          </>
        )
      }
    >
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {state.kind === "ready" && (
        <div className={`${LIST_BODY_CLASS} pt-4`}>
          {sorted.length === 0 ? (
            <div className={ROW_CLASS}>
              <IconCircle icon={CheckCircle2} tone="success" />
              <CellText title={t("dashboard.attention.allClear.title")} sub={t("dashboard.attention.allClear.sub")} />
              <span />
            </div>
          ) : (
            sorted.map((item, index) => <AttentionRow key={`${item.kind}-${item.subject ?? index}`} item={item} />)
          )}
        </div>
      )}
    </Section>
  );
}
