import type { ParseKeys } from "i18next";
import {
  BadgePercent,
  Ban,
  BarChart3,
  BellRing,
  BookOpen,
  Bot,
  Check,
  Coins,
  CreditCard,
  Database,
  FileCheck,
  FileText,
  Globe,
  Image,
  KeyRound,
  Languages,
  Layers,
  Link2,
  LogIn,
  Mail,
  Megaphone,
  MessagesSquare,
  Minus,
  Monitor,
  Package,
  PackagePlus,
  Palette,
  Receipt,
  ScrollText,
  Server,
  Share2,
  Shield,
  ShieldCheck,
  Smile,
  Store,
  Ticket,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { usePermissionCatalog, groupCatalogByResource, resourceCategoryKey } from "@entities/admin/use-permission-catalog";
import { Button } from "@shared/ui/Button";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Row } from "@shared/ui/glass/Row";
import { SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { Spinner } from "@shared/ui/Spinner";
import type { LucideIcon } from "lucide-react";
import type { Permission } from "@shared/types/rbac";

interface PermissionPickerProps {
  selected: Set<Permission>;
  onToggle: (permission: Permission) => void;
  /** Rows whose state differs from this set get a "changed" mark (an admin's role defaults). */
  baseline?: Set<Permission>;
  disabled?: boolean;
  /** Only permissions an API token may carry. */
  tokenGrantableOnly?: boolean;
}

const RESOURCE_ICONS: Record<string, LucideIcon> = {
  bot_settings: Bot,
  access_settings: ShieldCheck,
  oauth_settings: KeyRound,
  banners: Image,
  emoji_packs: Smile,
  dialogs: MessagesSquare,
  locales: Globe,
  translations: Languages,
  event_log: ScrollText,
  notification_settings: BellRing,
  analytics: BarChart3,
  remnawave: Server,
  users: Users,
  user_sessions: Monitor,
  appearance: Palette,
  gateways: CreditCard,
  blacklist: Ban,
  shop_settings: Store,
  plans: Package,
  pricing: Coins,
  subscriptions: Layers,
  addons: PackagePlus,
  promocodes: Ticket,
  transactions: Receipt,
  referrals: Share2,
  backups: Database,
  ad_links: Link2,
  broadcasts: Megaphone,
  loyalty: BadgePercent,
  cabinet_auth_settings: LogIn,
  email_settings: Mail,
  legal_documents: FileText,
  legal_acceptances: FileCheck,
  connect_guide: BookOpen,
};

function getResourceIcon(resource: string): LucideIcon {
  return RESOURCE_ICONS[resource] ?? Shield;
}

type KindState = "off" | "partial" | "on";

function getKindState(keys: Permission[], active: Set<Permission>): KindState {
  const activeCount = keys.filter((key) => active.has(key)).length;
  if (activeCount === 0) return "off";
  if (activeCount === keys.length) return "on";
  return "partial";
}

function toggleKind(props: PermissionPickerProps, keys: Permission[], state: KindState): void {
  const turnOn = state !== "on";
  for (const key of keys) {
    if (props.selected.has(key) !== turnOn) {
      props.onToggle(key);
    }
  }
}

export function PermissionPicker(props: PermissionPickerProps) {
  const { t } = useTranslation();
  const catalogState = usePermissionCatalog();
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  if (catalogState.kind === "loading") {
    return <Spinner size="card" />;
  }
  if (catalogState.kind === "error") {
    return <ErrorState text={t("common.loadError")} />;
  }

  const groups = groupCatalogByResource(
    props.tokenGrantableOnly ? catalogState.data.filter((entry) => entry.token_grantable) : catalogState.data,
  );
  const active = props.selected;

  const toggleExpand = (resource: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(resource)) {
        next.delete(resource);
      } else {
        next.add(resource);
      }
      return next;
    });
  };

  return (
    <SectionRows flush>
      {groups.map((group) => {
        const allKeys = [...group.read, ...group.write];
        const selectedCount = allKeys.filter((key) => active.has(key)).length;
        const readState = getKindState(group.read, active);
        const writeState = getKindState(group.write, active);

        return (
          <Row
            key={group.resource}
            icon={getResourceIcon(group.resource)}
            label={t(`permissionCategories.${resourceCategoryKey(group.resource)}` as ParseKeys)}
            description={`${selectedCount}/${allKeys.length}`}
            expanded={expanded.has(group.resource)}
            chevron={false}
            onClick={() => toggleExpand(group.resource)}
            panel={[...group.read, ...group.write].map((permission) => (
              <PermissionRow key={permission} permission={permission} {...props} />
            ))}
          >
            {group.read.length > 0 && (
              <KindPill
                label={t("permissionPicker.read")}
                state={readState}
                disabled={props.disabled}
                onClick={() => toggleKind(props, group.read, readState)}
              />
            )}
            {group.write.length > 0 && (
              <KindPill
                label={t("permissionPicker.write")}
                state={writeState}
                disabled={props.disabled}
                onClick={() => toggleKind(props, group.write, writeState)}
              />
            )}
          </Row>
        );
      })}
    </SectionRows>
  );
}

interface KindPillProps {
  label: string;
  state: KindState;
  disabled?: boolean;
  onClick: () => void;
}

function KindPill({ label, state, disabled, onClick }: KindPillProps) {
  return (
    <Button variant={state === "off" ? "glass" : "glassAccent"} size="sm" disabled={disabled} onClick={onClick}>
      {/* an icon in every state keeps the pill one width as it toggles */}
      {state === "on" && <Check className="size-3.5" />}
      {state === "partial" && <Minus className="size-3.5" />}
      {state === "off" && <X className="size-3.5" />}
      {label}
    </Button>
  );
}

function PermissionRow({ permission, ...props }: { permission: Permission } & PermissionPickerProps) {
  const { t } = useTranslation();
  const label = t(`permissions.${permission}`);
  const isChanged = props.baseline !== undefined && props.baseline.has(permission) !== props.selected.has(permission);

  return (
    <div className="flex items-center justify-between gap-3">
      <span className="flex min-w-0 items-center gap-2 text-sm text-foreground/90">
        {props.baseline !== undefined && (
          // slot kept on every row so labels stay aligned
          <span
            className={`size-1.5 shrink-0 rounded-full ${isChanged ? "bg-warning" : ""}`}
          />
        )}
        {label}
      </span>
      <Switch
        checked={props.selected.has(permission)}
        onChange={() => props.onToggle(permission)}
        disabled={props.disabled}
      />
    </div>
  );
}
