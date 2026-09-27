import {
  Ban,
  Bot,
  Check,
  ChevronRight,
  Coins,
  CreditCard,
  Database,
  Gift,
  Globe,
  Image,
  KeyRound,
  Languages,
  Layers,
  Link2,
  Minus,
  Monitor,
  Package,
  Palette,
  ScrollText,
  Shield,
  Store,
  Tag,
  Ticket,
  Users,
  Wallet,
} from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { usePermissionCatalog, groupCatalogByResource } from "@entities/admin/use-permission-catalog";
import { bounceTap, useBounceStrength } from "@shared/lib/bounceState";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import type { LucideIcon } from "lucide-react";
import type { Permission } from "@shared/types/rbac";

interface PermissionPickerProps {
  selected: Set<Permission>;
  onToggle: (permission: Permission) => void;
  /** Rows whose state differs from this set get a "changed" mark (an admin's role defaults). */
  baseline?: Set<Permission>;
  disabled?: boolean;
}

const RESOURCE_ICONS: Record<string, LucideIcon> = {
  bot_settings: Bot,
  oauth_settings: KeyRound,
  banners: Image,
  locales: Globe,
  translations: Languages,
  event_log: ScrollText,
  users: Users,
  user_sessions: Monitor,
  appearance: Palette,
  gateways: CreditCard,
  blacklist: Ban,
  shop_settings: Store,
  plans: Tag,
  pricing: Coins,
  subscriptions: Layers,
  addons: Package,
  promocodes: Ticket,
  payments: Wallet,
  referrals: Gift,
  backups: Database,
  ad_links: Link2,
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
    return <Spinner />;
  }
  if (catalogState.kind === "error") {
    return <p className="text-sm text-error">{t("apiTokens.loadError")}</p>;
  }

  const groups = groupCatalogByResource(catalogState.data);
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
    <div className="flex flex-col gap-1.5">
      {groups.map((group) => {
        const allKeys = [...group.read, ...group.write];
        const selectedCount = allKeys.filter((key) => active.has(key)).length;
        const isExpanded = expanded.has(group.resource);
        const ResourceIcon = getResourceIcon(group.resource);
        const readState = getKindState(group.read, active);
        const writeState = getKindState(group.write, active);
        const categoryKey = group.resource.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase());

        return (
          <div key={group.resource} className="flex flex-col">
            <div className="-mx-2 flex h-[41px] items-center gap-2 rounded-full px-2 transition-colors hover:bg-white/[0.04]">
              <button
                type="button"
                onClick={() => toggleExpand(group.resource)}
                className="flex min-w-0 flex-1 items-center gap-2"
              >
                <ChevronRight
                  className={`size-3.5 shrink-0 text-muted-foreground transition-transform ${isExpanded ? "rotate-90" : ""}`}
                />
                <ResourceIcon className="size-4 shrink-0 text-muted-foreground" />
                <span className="truncate text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t(`permissionCategories.${categoryKey}`)}
                </span>
                <span className="shrink-0 font-mono text-[11px] text-muted-foreground/70">
                  {selectedCount}/{allKeys.length}
                </span>
              </button>

              <div className="flex shrink-0 items-center gap-1.5">
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
              </div>
            </div>

            {isExpanded && (
              <div className="flex flex-col divide-y divide-border/50 pl-6">
                {group.read.map((permission) => (
                  <PermissionRow key={permission} permission={permission} {...props} />
                ))}
                {group.write.map((permission) => (
                  <PermissionRow key={permission} permission={permission} {...props} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface KindPillProps {
  label: string;
  state: KindState;
  disabled?: boolean;
  onClick: () => void;
}

function KindPill({ label, state, disabled, onClick }: KindPillProps) {
  const bounceStrength = useBounceStrength();
  const isActive = state === "on" || state === "partial";
  return (
    <motion.button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      disabled={disabled}
      {...bounceTap(bounceStrength)}
      className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[11px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
        isActive
          ? "border-primary/40 bg-accent text-primary"
          : "border-border text-muted-foreground hover:bg-white/5"
      }`}
    >
      {state === "on" && <Check className="size-3.5" />}
      {state === "partial" && <Minus className="size-3.5" />}
      {label}
    </motion.button>
  );
}

function PermissionRow({ permission, ...props }: { permission: Permission } & PermissionPickerProps) {
  const { t } = useTranslation();
  const label = t(`permissions.${permission}`);
  const isChanged = props.baseline !== undefined && props.baseline.has(permission) !== props.selected.has(permission);

  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <span className="flex min-w-0 items-center gap-2 text-[13px] text-foreground/90">
        {props.baseline !== undefined && (
          // slot kept on every row so labels stay aligned
          <span
            role={isChanged ? "img" : undefined}
            aria-label={isChanged ? t("permissionPicker.changed") : undefined}
            className={`size-1.5 shrink-0 rounded-full ${isChanged ? "bg-warning" : ""}`}
          />
        )}
        {label}
      </span>
      <Switch
        checked={props.selected.has(permission)}
        onChange={() => props.onToggle(permission)}
        disabled={props.disabled}
        ariaLabel={label}
      />
    </div>
  );
}
