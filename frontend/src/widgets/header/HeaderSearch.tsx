import {
  CornerDownLeft,
  CreditCard,
  Layers,
  Loader2,
  Package,
  ScrollText,
  Search,
  Ticket,
  User as UserIcon,
} from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { listTransactions, type TransactionItem } from "@entities/transactions/api";
import { listPlans, type Plan } from "@entities/plans/api";
import { listPromocodes, type Promocode } from "@entities/promocodes/api";
import { listSubscriptions, type SubscriptionListItem } from "@entities/subscriptions/api";
import { listUsers, type UserListItem } from "@entities/user/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { useOpenEntity } from "@shared/lib/entity-dialogs";
import { isNavItemVisible, NAV_ITEMS, SETTINGS_TABS } from "@widgets/sidebar/nav-items";
import { PortalPopover } from "@shared/ui/PortalPopover";
import { SearchClearButton } from "@shared/ui/SearchField";
import { Ripple } from "@shared/ui/Ripple";
import { Pressable } from "@shared/ui/Pressable";

const DEBOUNCE_MS = 250;
const USER_LIMIT = 5;
const RESULT_LIMIT = 3;
// max-h-96 list plus the popover padding
const POPOVER_MAX_HEIGHT = 400;
interface Entry {
  id: string;
  label: string;
  hint?: string;
  icon: ComponentType<{ className?: string }>;
  /** a page to go to, or a dialog to open on top of the current one */
  to?: string;
  open?: () => void;
}

const matches = (haystack: string, tokens: string[]) => {
  const lower = haystack.toLowerCase();
  return tokens.every((token) => lower.includes(token));
};

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function highlight(text: string, tokens: string[]) {
  if (tokens.length === 0) return text;
  const pattern = new RegExp(`(${tokens.map(escapeRegExp).join("|")})`, "gi");
  // split with a capture group puts matches at odd indexes
  return text.split(pattern).map((part, index) =>
    index % 2 === 1 ? (
      <span key={index} className="underline underline-offset-2">
        {part}
      </span>
    ) : (
      part
    ),
  );
}

export function HeaderSearch() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { openUser, openOrder, openSubscription, openPromocode, openPlan } = useOpenEntity();
  const permissions = usePermissions();
  const canViewUsers = permissions.includes("USERS_VIEW");

  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [orders, setOrders] = useState<TransactionItem[]>([]);
  const [subscriptions, setSubscriptions] = useState<SubscriptionListItem[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [promocodes, setPromocodes] = useState<Promocode[]>([]);
  const rootRef = useRef<HTMLDivElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  useClickOutside([rootRef, popoverRef], open, () => setOpen(false));

  const debounced = useDebouncedValue(query.trim(), DEBOUNCE_MS);
  const [isFetching, setIsFetching] = useState(false);

  // Paginated lists are searched server-side per query; plans are a small
  // unpaginated list, fetched once on first use and filtered here.
  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    const ignore = () => {};
    const search = debounced;
    if (!search) {
      setUsers([]);
      setOrders([]);
      setSubscriptions([]);
      setPromocodes([]);
      setIsFetching(false);
      return;
    }
    const requests: Promise<unknown>[] = [];
    if (canViewUsers)
      requests.push(listUsers({ search, pageSize: USER_LIMIT }, signal).then((p) => setUsers(p.items)).catch(ignore));
    if (permissions.includes("TRANSACTIONS_VIEW"))
      requests.push(
        listTransactions({ search, pageSize: RESULT_LIMIT }, signal).then((p) => setOrders(p.items)).catch(ignore),
      );
    if (permissions.includes("SUBSCRIPTIONS_VIEW"))
      requests.push(
        listSubscriptions({ search, pageSize: RESULT_LIMIT }, signal)
          .then((p) => setSubscriptions(p.items))
          .catch(ignore),
      );
    if (permissions.includes("PROMOCODES_VIEW"))
      requests.push(
        listPromocodes({ search, pageSize: RESULT_LIMIT }, signal).then((p) => setPromocodes(p.items)).catch(ignore),
      );
    setIsFetching(requests.length > 0);
    void Promise.all(requests).then(() => {
      if (!signal.aborted) setIsFetching(false);
    });
    return () => controller.abort();
  }, [debounced, canViewUsers, permissions]);

  const wantsCatalog = debounced !== "";
  useEffect(() => {
    if (!wantsCatalog) return;
    if (permissions.includes("PLANS_VIEW") && plans.length === 0) listPlans().then(setPlans).catch(() => {});
  }, [wantsCatalog, permissions, plans.length]);

  const pages = useMemo<Entry[]>(() => {
    const nav = NAV_ITEMS.filter((item) => isNavItemVisible(item, permissions)).map(
      (item) => ({ id: `nav:${item.key}`, label: t(`sidebar.${item.key}`), to: item.to, icon: item.icon }),
    );
    const settings = NAV_ITEMS.find((item) => item.key === "settings");
    const tabs = settings
      ? SETTINGS_TABS.filter((tab) => tab.anyOf.some((permission) => permissions.includes(permission))).map(
          (tab) => ({
            id: `settings:${tab.key}`,
            label: t(`settings.tabs.${tab.key}`),
            hint: t("sidebar.settings"),
            to: tab.to ? `${settings.to}/${tab.to}` : settings.to,
            icon: tab.icon,
          }),
        )
      : [];
    return [...nav, ...tabs];
  }, [t, permissions]);

  const entries = useMemo<Entry[]>(() => {
    const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    if (tokens.length === 0) return [];
    const found = pages.filter((entry) => matches(`${entry.label} ${entry.hint ?? ""}`, tokens));
    const people = users.map((user) => ({
      id: `user:${user.id}`,
      label: user.name,
      hint: [user.username && `@${user.username}`, user.login, user.email, user.telegram_id]
        .filter(Boolean)
        .join(" · "),
      open: () => openUser(user.id, { data: user }),
      icon: UserIcon,
    }));
    const link = (path: string) => `${path}?search=${encodeURIComponent(debounced)}`;
    const orderEntries = orders.map((order) => ({
      id: `order:${order.id}`,
      label: `${t("header.searchOrders")} #${order.id}`,
      hint: [order.plan_snapshot.name, order.status].filter(Boolean).join(" · "),
      open: () => openOrder(order.id, { data: order }),
      icon: CreditCard,
    }));
    const subscriptionEntries = subscriptions.map((sub) => ({
      id: `subscription:${sub.id}`,
      label: `${t("header.searchSubscriptions")} #${sub.id}`,
      hint: [sub.tag, t("header.searchSubscriptionUser", { id: sub.user_id })].filter(Boolean).join(" · "),
      open: () => openSubscription(sub.id, { data: sub }),
      icon: Layers,
    }));
    const planEntries = plans
      .filter((plan) => matches(`${plan.name} ${plan.public_code} ${plan.tag ?? ""}`, tokens))
      .slice(0, RESULT_LIMIT)
      .map((plan) => ({
        id: `plan:${plan.id}`,
        label: plan.name,
        hint: t("header.searchPlan"),
        // the plan dialog is an edit form; without the right the plans page is the read-only view
        ...(permissions.includes("PLANS_UPDATE")
          ? { open: () => openPlan(plan.id, { data: plan }) }
          : { to: "/dashboard/plans" }),
        icon: Package,
      }));
    const promocodeEntries = promocodes.map((promocode) => ({
      id: `promocode:${promocode.id}`,
      label: promocode.code,
      hint: t("header.searchPromocode"),
      open: () => openPromocode(promocode.id, { data: promocode }),
      icon: Ticket,
    }));
    const eventEntries = permissions.includes("EVENT_LOG_VIEW")
      ? [
          {
            id: "events",
            label: t("header.searchEvents"),
            hint: debounced,
            to: link("/dashboard/events"),
            icon: ScrollText,
          },
        ]
      : [];
    return [
      ...found,
      ...people,
      ...orderEntries,
      ...subscriptionEntries,
      ...planEntries,
      ...promocodeEntries,
      ...eventEntries,
    ];
  }, [
    query,
    pages,
    users,
    orders,
    subscriptions,
    plans,
    promocodes,
    debounced,
    t,
    permissions,
    openUser,
    openOrder,
    openSubscription,
    openPromocode,
    openPlan,
  ]);

  useEffect(() => setActive(0), [entries]);

  const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);

  const go = (entry: Entry) => {
    if (entry.open) entry.open();
    else if (entry.to) navigate(entry.to);
    setOpen(false);
    setQuery("");
  };

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Escape") setOpen(false);
    else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((index) => (index + step + entries.length) % Math.max(entries.length, 1));
    } else if (event.key === "Enter" && entries[active]) go(entries[active]);
  };

  return (
    <div ref={rootRef} className="relative flex min-w-40 max-w-80 flex-1">
      <motion.label
        className="group relative flex w-full items-center gap-2 rounded-full border border-glass-border bg-white/[0.05] h-9 px-3.5 transition-colors not-focus-within:hover:bg-white/[0.07] focus-within:border-primary"
      >
        <Ripple />
        <Search className="size-4 shrink-0 text-muted-foreground transition-colors group-not-focus-within:group-hover:text-foreground group-focus-within:text-primary" />
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={t("header.searchPlaceholder")}
          className="w-full min-w-0 border-0 bg-transparent text-[13px] text-foreground outline-none focus-visible:outline-none placeholder:text-muted-foreground placeholder:transition-colors group-not-focus-within:group-hover:placeholder:text-foreground"
        />
        {query && (
          // 26px in the 34px inner height: 4px inset (px-3.5 minus 10)
          <SearchClearButton
            size="26px"
            className="-mr-2.5"
            onClear={() => {
              setQuery("");
              setOpen(false);
            }}
          />
        )}
      </motion.label>

      <PortalPopover
        open={open && query.trim() !== ""}
        // the field stays usable while results are open
        modal={false}
        triggerRef={rootRef}
        popoverRef={popoverRef}
        align="left"
        maxHeight={POPOVER_MAX_HEIGHT}
        initial={{ opacity: 0, scale: 0.96, y: -4 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: -4 }}
        transition={{ duration: 0.15, ease: "easeOut" }}
        className="w-80 p-1.5"
      >
        {/* scroll lives inside the padding: on the popover itself the
            scrollbar column paints over the rounded corners */}
        <div className="max-h-96 overflow-y-auto">
        {entries.length === 0 && (isFetching || query.trim() !== debounced) ? (
          <p className="flex items-center gap-2 px-3 py-2 text-[12.5px] text-muted-foreground">
            <Loader2 className="size-3.5 animate-spin" />
            {t("header.searching")}
          </p>
        ) : entries.length === 0 ? (
          <p className="px-3 py-2 text-[12.5px] text-muted-foreground">{t("header.searchEmpty")}</p>
        ) : (
          entries.map((entry, index) => (
            <Pressable
              key={entry.id}
              type="button"
              onMouseEnter={() => setActive(index)}
              onClick={() => go(entry)}
              animate={index === active ? "hover" : "rest"}
              className={`flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] ${
                index === active ? "bg-accent text-primary" : "text-foreground"
              }`}
            >
              <entry.icon className="size-4 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{highlight(entry.label, tokens)}</span>
              {entry.hint && <span className="max-w-32 truncate text-[11px] text-muted-foreground">{highlight(entry.hint, tokens)}</span>}
              {index === active && <CornerDownLeft className="size-3.5 shrink-0" />}
            </Pressable>
          ))
        )}
        </div>
      </PortalPopover>
    </div>
  );
}
