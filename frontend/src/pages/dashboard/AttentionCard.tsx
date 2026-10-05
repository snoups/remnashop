import type { ParseKeys, TFunction } from "i18next";
import {
  AlertTriangle,
  Bot,
  CalendarClock,
  CheckCircle2,
  Clock,
  CreditCard,
  DatabaseZap,
  PackageX,
  ServerOff,
} from "lucide-react";
import type { ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import type { BackupKind } from "@entities/backups/api";
import { getAttention } from "@entities/overview/api";
import type { AttentionItem, AttentionKind } from "@entities/overview/api";
import { usePermissions } from "@entities/user/use-current-user";
import { formatDateTime } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import type { Permission } from "@shared/types/rbac";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { LIST_BODY_CLASS, LIST_ROW_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/EmptyState";
import { Spinner } from "@shared/ui/Spinner";
import { NAV_ITEMS, SETTINGS_TABS, isNavItemVisible } from "@widgets/sidebar/nav-items";

const ROW_CLASS = `grid grid-cols-[36px_minmax(0,1fr)_auto] items-center gap-3 ${LIST_ROW_CLASS}`;

const SEVERITY_ICON_CLASS = {
  critical: "bg-error/12 text-error",
  warning: "bg-warning/12 text-warning",
} as const;

const KIND_ICON: Record<AttentionKind, ComponentType<{ className?: string }>> = {
  node_offline: ServerOff,
  gateway_failures: CreditCard,
  backup_failed: DatabaseZap,
  paid_not_fulfilled: PackageX,
  stale_pending: Clock,
  expiring_paid: CalendarClock,
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

const transactionsLink: AttentionLink = {
  to: "/dashboard/transactions",
  label: "dashboard.attention.actions.transactions",
  allowed: (permissions) => NAV_ITEMS.some((item) => item.key === "transactions" && isNavItemVisible(item, permissions)),
};

// node_offline has none: nodes are managed in Remnawave
const KIND_LINK: Partial<Record<AttentionKind, AttentionLink>> = {
  gateway_failures: {
    to: "/dashboard/settings/gateways",
    label: "dashboard.attention.actions.gateways",
    allowed: settingsTabAllowed("gateways"),
  },
  backup_failed: {
    to: "/dashboard/settings/backups",
    label: "dashboard.attention.actions.backups",
    allowed: settingsTabAllowed("backups"),
  },
  paid_not_fulfilled: transactionsLink,
  stale_pending: transactionsLink,
  expiring_paid: {
    to: "/dashboard/analytics/retention",
    label: "dashboard.attention.actions.retention",
    allowed: (permissions) => permissions.includes("ANALYTICS_RETENTION_VIEW"),
  },
  bot_webhook: {
    to: "/dashboard/settings/bot",
    label: "dashboard.attention.actions.bot",
    allowed: settingsTabAllowed("bot"),
  },
};

function itemText(item: AttentionItem, t: TFunction, language: string): { title: string; sub: string | null } {
  const formatted = item.count.toLocaleString(language);
  const since = item.since && formatDateTime(item.since, language);
  switch (item.kind) {
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
        sub: t("dashboard.attention.gatewayFailures.sub", { count: item.count, formatted }),
      };
    case "backup_failed": {
      const kind = item.subject ? t(`backups.kind.${item.subject as BackupKind}`) : null;
      return {
        title: t("dashboard.attention.backupFailed.title"),
        sub: [kind, since].filter(Boolean).join(" · ") || null,
      };
    }
    case "paid_not_fulfilled":
      return {
        title: t("dashboard.attention.paidNotFulfilled.title"),
        sub: t("dashboard.attention.paidNotFulfilled.sub", { count: item.count, formatted }),
      };
    case "stale_pending":
      return {
        title: t("dashboard.attention.stalePending.title"),
        sub: t("dashboard.attention.stalePending.sub", { formatted }),
      };
    case "expiring_paid":
      return {
        title: t("dashboard.attention.expiringPaid.title"),
        sub: t("dashboard.attention.expiringPaid.sub", { formatted }),
      };
    case "bot_webhook":
      return { title: t("dashboard.attention.botWebhook.title"), sub: item.subject };
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
      <span className={`flex size-9 items-center justify-center rounded-full ${SEVERITY_ICON_CLASS[item.severity]}`}>
        <Icon className="size-4" />
      </span>
      <span className="min-w-0">
        <span className="block truncate text-[13.5px] font-medium text-foreground">{title}</span>
        {sub && <span className="block truncate text-[12px] text-muted-foreground">{sub}</span>}
      </span>
      {link && link.allowed(permissions) ? (
        <Button variant="secondary" size="sm" onClick={() => navigate(link.to)}>
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
    <Card>
      <CardHeader
        icon={AlertTriangle}
        title={t("dashboard.attention.title")}
        description={t("dashboard.attention.description")}
        aside={
          (critical > 0 || warning > 0) && (
            <>
              {critical > 0 && (
                <Badge tone="error">
                  {t("dashboard.attention.critical", { value: critical.toLocaleString(i18n.language) })}
                </Badge>
              )}
              {warning > 0 && <Badge tone="warning">{warning.toLocaleString(i18n.language)}</Badge>}
            </>
          )
        }
      />
      {state.kind === "loading" && <Spinner size="card" />}
      {state.kind === "error" && <ErrorState text={t("dashboard.loadError")} />}
      {state.kind === "ready" && (
        <div className={`${LIST_BODY_CLASS} pt-1.5`}>
          {sorted.length === 0 ? (
            <div className={ROW_CLASS}>
              <span className="flex size-9 items-center justify-center rounded-full bg-success/12 text-success">
                <CheckCircle2 className="size-4" />
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[13.5px] font-medium text-foreground">
                  {t("dashboard.attention.allClear.title")}
                </span>
                <span className="block truncate text-[12px] text-muted-foreground">
                  {t("dashboard.attention.allClear.sub")}
                </span>
              </span>
              <span />
            </div>
          ) : (
            sorted.map((item, index) => <AttentionRow key={`${item.kind}-${item.subject ?? index}`} item={item} />)
          )}
        </div>
      )}
    </Card>
  );
}
