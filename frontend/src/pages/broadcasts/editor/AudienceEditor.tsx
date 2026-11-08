import {
  CalendarClock,
  CalendarDays,
  CalendarX,
  Languages,
  Layers,
  Mail,
  Package,
  Send,
  UserCheck,
  UserPlus,
  Wallet,
  WifiOff,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { EMPTY_AUDIENCE } from "@entities/broadcasts/api";
import type { BroadcastAudience, SubscriptionFilter } from "@entities/broadcasts/api";
import type { AdLink } from "@entities/advertising/api";
import type { Plan } from "@entities/plans/api";
import { listUsers } from "@entities/user/api";
import { userLabel } from "@entities/user/display";
import { normalizePositiveInt } from "@shared/lib/chip-normalizers";
import { formatDate } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { Field } from "@shared/ui/glass/Field";
import { Input } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { PillTabs } from "@shared/ui/PillTabs";
import { UserRow } from "@shared/ui/UserRow";

export type AudienceMode = "filters" | "users";

const SUBSCRIPTIONS: SubscriptionFilter[] = ["ACTIVE", "TRIAL", "EXPIRED", "LIMITED", "NONE"];
const MAX_NOT_CONNECTED_DAYS = 30;
const DAY_PRESETS = [3, 7, 30, 90];
const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_LIMIT = 6;

function toggle<T>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function UserPicker({
  userIds,
  onChange,
  disabled,
}: {
  userIds: number[];
  onChange: (ids: number[]) => void;
  disabled: boolean;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const search = useDebouncedValue(query, SEARCH_DEBOUNCE_MS).trim();
  const [resultsState] = useAsyncResource(
    (signal) => (search ? listUsers({ search, pageSize: SEARCH_LIMIT }, signal) : Promise.resolve(null)),
    { deps: [search] },
  );
  const results = resultsState.kind === "ready" && resultsState.data ? resultsState.data.items : [];

  // ChipsInput has no disabled state: read-only shows the ids as text
  if (disabled) {
    return (
      <Field label={t("broadcasts.editor.audience.userIds")}>
        <span className="text-[13px] tabular-nums text-foreground">
          {userIds.length > 0 ? userIds.map((id) => `#${id}`).join(", ") : t("common.none")}
        </span>
      </Field>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <Field label={t("broadcasts.editor.audience.search")} htmlFor="broadcast-user-search">
        <Input
          id="broadcast-user-search"
          type="search"
          value={query}
          placeholder={t("broadcasts.editor.audience.searchPlaceholder")}
          onChange={(event) => setQuery(event.target.value)}
        />
      </Field>
      {results.length > 0 && (
        <DialogCard>
          {results.map((user) => (
            <UserRow
              key={user.id}
              name={userLabel(user, user.id, t)}
              unnamed={!user.name && !user.login}
              subtitle={[`#${user.id}`, user.username ? `@${user.username}` : null].filter(Boolean).join(" · ")}
              onClick={
                userIds.includes(user.id)
                  ? undefined
                  : () => {
                      onChange([...userIds, user.id]);
                      setQuery("");
                    }
              }
            />
          ))}
        </DialogCard>
      )}
      <Field
        label={t("broadcasts.editor.audience.userIds")}
        htmlFor="broadcast-user-ids"
        hint={t("broadcasts.editor.audience.userIdsHint")}
      >
        <ChipsInput
          id="broadcast-user-ids"
          values={userIds.map(String)}
          onChange={(ids) => onChange(ids.map(Number))}
          normalize={normalizePositiveInt}
          inputMode="numeric"
          placeholder={t("broadcasts.editor.audience.userIdsPlaceholder")}
        />
      </Field>
    </div>
  );
}

interface AudienceEditorProps {
  audience: BroadcastAudience;
  onChange: (audience: BroadcastAudience) => void;
  mode: AudienceMode;
  onModeChange: (mode: AudienceMode) => void;
  plans: Plan[];
  adLinks: AdLink[];
  botLocales: string[];
  disabled: boolean;
}

export function AudienceEditor({
  audience,
  onChange,
  mode,
  onModeChange,
  plans,
  adLinks,
  botLocales,
  disabled,
}: AudienceEditorProps) {
  const { t, i18n } = useTranslation();
  const set = (patch: Partial<BroadcastAudience>) => onChange({ ...audience, ...patch });
  const chip = (key: string | number, active: boolean, label: string, onClick: () => void) => (
    <ChoiceChip key={key} active={active} disabled={disabled} onClick={onClick}>
      {label}
    </ChoiceChip>
  );
  const dayChips = (value: number | null, apply: (days: number | null) => void) => [
    chip("any", value === null, t("broadcasts.editor.audience.any"), () => apply(null)),
    ...DAY_PRESETS.map((days) =>
      chip(days, value === days, t("broadcasts.editor.audience.withinDays", { count: days }), () => apply(days)),
    ),
  ];
  const triState = (id: string, value: boolean | null, apply: (next: boolean | null) => void) => [
    chip(`${id}-any`, value === null, t("broadcasts.editor.audience.any"), () => apply(null)),
    chip(`${id}-yes`, value === true, t("common.yes"), () => apply(true)),
    chip(`${id}-no`, value === false, t("common.no"), () => apply(false)),
  ];
  const oneDateOnly = (audience.registered_from === null) !== (audience.registered_to === null);
  const [openKey, setOpenKey] = useState<string | null>(null);

  const any = t("broadcasts.editor.audience.any");
  const listSummary = (labels: string[]) => (labels.length ? labels.join(", ") : any);
  const daysSummary = (value: number | null) =>
    value === null ? any : t("broadcasts.editor.audience.withinDays", { count: value });
  const triSummary = (value: boolean | null) => (value === null ? any : value ? t("common.yes") : t("common.no"));
  const date = (iso: string | null) => (iso ? formatDate(iso, i18n.language) : "…");

  // one row per filter: its choice under the label, its controls folded out under it, one open at a time
  const filters: { key: string; icon: LucideIcon; label: string; summary: string; panel: ReactNode }[] = [
    {
      key: "subscription",
      icon: Layers,
      label: t("broadcasts.editor.audience.subscription"),
      summary: listSummary(audience.subscription.map((s) => t(`broadcasts.editor.audience.subscriptionChip.${s}`))),
      panel: SUBSCRIPTIONS.map((s) =>
        chip(s, audience.subscription.includes(s), t(`broadcasts.editor.audience.subscriptionChip.${s}`), () =>
          set({ subscription: toggle(audience.subscription, s) }),
        ),
      ),
    },
    ...(plans.length > 0
      ? [
          {
            key: "plans",
            icon: Package,
            label: t("broadcasts.editor.audience.plans"),
            summary: listSummary(plans.filter((plan) => audience.plan_ids.includes(plan.id)).map((plan) => plan.name)),
            panel: [
              chip("all", audience.plan_ids.length === 0, t("broadcasts.editor.audience.all"), () => set({ plan_ids: [] })),
              ...plans.map((plan) =>
                chip(plan.id, audience.plan_ids.includes(plan.id), plan.name, () =>
                  set({ plan_ids: toggle(audience.plan_ids, plan.id) }),
                ),
              ),
            ],
          },
        ]
      : []),
    {
      key: "expires",
      icon: CalendarClock,
      label: t("broadcasts.editor.audience.expires"),
      summary: daysSummary(audience.expires_within_days),
      panel: dayChips(audience.expires_within_days, (days) => set({ expires_within_days: days })),
    },
    {
      key: "expired",
      icon: CalendarX,
      label: t("broadcasts.editor.audience.expired"),
      summary: daysSummary(audience.expired_within_days),
      panel: dayChips(audience.expired_within_days, (days) => set({ expired_within_days: days })),
    },
    {
      key: "notConnected",
      icon: WifiOff,
      label: t("broadcasts.editor.audience.notConnected"),
      summary: daysSummary(audience.not_connected_within_days),
      panel: (
        <div className="w-28">
          <Input
            type="number"
            min={1}
            max={MAX_NOT_CONNECTED_DAYS}
            inputMode="numeric"
            disabled={disabled}
            value={audience.not_connected_within_days ?? ""}
            placeholder={any}
            // no "(days)" in the label: the unit sits in the field
            suffix={t("broadcasts.editor.audience.daysSuffix")}
            onChange={(event) => {
              const days = Math.trunc(Number(event.target.value));
              set({
                not_connected_within_days:
                  event.target.value === "" || !Number.isFinite(days)
                    ? null
                    : Math.min(Math.max(days, 1), MAX_NOT_CONNECTED_DAYS),
              });
            }}
          />
        </div>
      ),
    },
    {
      key: "paid",
      icon: Wallet,
      label: t("broadcasts.editor.audience.paid"),
      summary: triSummary(audience.paid),
      panel: triState("paid", audience.paid, (paid) => set({ paid })),
    },
    {
      key: "telegram",
      icon: Send,
      label: t("broadcasts.editor.audience.hasTelegram"),
      summary: triSummary(audience.has_telegram),
      panel: triState("telegram", audience.has_telegram, (has_telegram) => set({ has_telegram })),
    },
    {
      key: "email",
      icon: Mail,
      label: t("broadcasts.editor.audience.hasEmail"),
      summary: triSummary(audience.has_email),
      panel: triState("email", audience.has_email, (has_email) => set({ has_email })),
    },
    ...(botLocales.length > 1
      ? [
          {
            key: "language",
            icon: Languages,
            label: t("broadcasts.editor.audience.language"),
            summary: listSummary(audience.locales.map((locale) => locale.toUpperCase())),
            panel: [
              chip("all", audience.locales.length === 0, t("broadcasts.editor.audience.all"), () => set({ locales: [] })),
              ...botLocales.map((locale) =>
                chip(locale, audience.locales.includes(locale), locale.toUpperCase(), () =>
                  set({ locales: toggle(audience.locales, locale) }),
                ),
              ),
            ],
          },
        ]
      : []),
    {
      key: "source",
      icon: UserPlus,
      label: t("broadcasts.editor.audience.source"),
      summary: listSummary([
        ...(audience.referred ? [t("broadcasts.editor.audience.referred")] : []),
        ...adLinks.filter((link) => audience.ad_link_ids.includes(link.id)).map((link) => link.name),
      ]),
      panel: [
        chip(
          "any",
          audience.referred === null && audience.ad_link_ids.length === 0,
          t("broadcasts.editor.audience.anySource"),
          () => set({ referred: null, ad_link_ids: [] }),
        ),
        chip("referred", audience.referred === true, t("broadcasts.editor.audience.referred"), () =>
          set({ referred: audience.referred === true ? null : true }),
        ),
        ...adLinks.map((link) =>
          chip(link.id, audience.ad_link_ids.includes(link.id), t("broadcasts.editor.audience.adLink", { name: link.name }), () =>
            set({ ad_link_ids: toggle(audience.ad_link_ids, link.id) }),
          ),
        ),
      ],
    },
    {
      key: "registered",
      icon: CalendarDays,
      label: t("broadcasts.editor.audience.registered"),
      summary:
        audience.registered_from || audience.registered_to
          ? `${date(audience.registered_from)} – ${date(audience.registered_to)}`
          : any,
      panel: disabled ? null : (
        <div className="flex w-full flex-col gap-1">
          <div className="grid grid-cols-2 gap-2">
            <DatePickerField
              value={audience.registered_from ?? ""}
              placeholder={t("broadcasts.editor.audience.from")}
              onChange={(value) => set({ registered_from: value || null })}
            />
            <DatePickerField
              value={audience.registered_to ?? ""}
              placeholder={t("broadcasts.editor.audience.to")}
              onChange={(value) => set({ registered_to: value || null })}
            />
          </div>
          {oneDateOnly && <span className="text-[12px] text-error">{t("broadcasts.editor.audience.bothDates")}</span>}
        </div>
      ),
    },
  ];

  return (
    <Section
      icon={UserCheck}
      title={t("broadcasts.editor.audience.title")}
      description={t("broadcasts.editor.audience.description")}
      aside={
        <PillTabs
          items={[
            { key: "filters" as const, label: t("broadcasts.editor.audience.byFilters") },
            { key: "users" as const, label: t("broadcasts.editor.audience.byUsers") },
          ]}
          activeKey={mode}
          disabled={disabled}
          onSelect={(next) => {
            onModeChange(next);
            onChange(next === "users" ? { ...EMPTY_AUDIENCE, user_ids: audience.user_ids } : EMPTY_AUDIENCE);
          }}
        />
      }
    >
      {mode === "users" ? (
        <div className="mt-5 flex flex-col gap-3 px-3.5 pb-2">
          <UserPicker userIds={audience.user_ids} onChange={(user_ids) => set({ user_ids })} disabled={disabled} />
        </div>
      ) : (
        <SectionRows>
          {filters.map((filter) => (
            <Row
              key={filter.key}
              icon={filter.icon}
              label={filter.label}
              description={filter.summary}
              expanded={openKey === filter.key}
              onClick={() => setOpenKey(openKey === filter.key ? null : filter.key)}
              panel={filter.panel && <div className="flex flex-wrap gap-1.5">{filter.panel}</div>}
            />
          ))}
        </SectionRows>
      )}
    </Section>
  );
}
