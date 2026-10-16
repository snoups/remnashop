import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { EMPTY_AUDIENCE } from "@entities/broadcasts/api";
import type { BroadcastAudience, SubscriptionFilter } from "@entities/broadcasts/api";
import type { AdLink } from "@entities/advertising/api";
import type { Plan } from "@entities/plans/api";
import { listUsers } from "@entities/user/api";
import { normalizePositiveInt } from "@shared/lib/chip-normalizers";
import { formatDate } from "@shared/lib/relative-time";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { Card } from "@shared/ui/Card";
import { ChipsInput } from "@shared/ui/ChipsInput";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { DatePickerField } from "@shared/ui/DatePickerField";
import { Field } from "@shared/ui/Field";
import { SegmentedPills } from "@shared/ui/SegmentedPills";
import { TextInput } from "@shared/ui/TextInput";
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

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[170px_minmax(0,1fr)] sm:gap-3">
      <span className="text-[13px] text-foreground/80">{label}</span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
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
        <TextInput
          id="broadcast-user-search"
          type="search"
          value={query}
          placeholder={t("broadcasts.editor.audience.searchPlaceholder")}
          onChange={(event) => setQuery(event.target.value)}
        />
      </Field>
      {results.length > 0 && (
        <Card variant="list">
          {results.map((user) => (
            <UserRow
              key={user.id}
              name={user.name}
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
        </Card>
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

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className={EYEBROW_CLASS}>{t("broadcasts.editor.audience.title")}</span>
        <div className="ml-auto">
          <SegmentedPills
            value={mode}
            disabled={disabled}
            onChange={(next) => {
              onModeChange(next);
              onChange(next === "users" ? { ...EMPTY_AUDIENCE, user_ids: audience.user_ids } : EMPTY_AUDIENCE);
            }}
            options={[
              { value: "filters", label: t("broadcasts.editor.audience.byFilters") },
              { value: "users", label: t("broadcasts.editor.audience.byUsers") },
            ]}
          />
        </div>
      </div>

      {mode === "users" ? (
        <UserPicker userIds={audience.user_ids} onChange={(user_ids) => set({ user_ids })} disabled={disabled} />
      ) : (
        <>
          <Row label={t("broadcasts.editor.audience.subscription")}>
            {SUBSCRIPTIONS.map((s) =>
              chip(s, audience.subscription.includes(s), t(`broadcasts.editor.audience.subscriptionChip.${s}`), () =>
                set({ subscription: toggle(audience.subscription, s) }),
              ),
            )}
          </Row>
          {plans.length > 0 && (
            <Row label={t("broadcasts.editor.audience.plans")}>
              {chip("all", audience.plan_ids.length === 0, t("broadcasts.editor.audience.all"), () =>
                set({ plan_ids: [] }),
              )}
              {plans.map((plan) =>
                chip(plan.id, audience.plan_ids.includes(plan.id), plan.name, () =>
                  set({ plan_ids: toggle(audience.plan_ids, plan.id) }),
                ),
              )}
            </Row>
          )}
          <Row label={t("broadcasts.editor.audience.expires")}>
            {dayChips(audience.expires_within_days, (days) => set({ expires_within_days: days }))}
          </Row>
          <Row label={t("broadcasts.editor.audience.expired")}>
            {dayChips(audience.expired_within_days, (days) => set({ expired_within_days: days }))}
          </Row>
          <Row label={t("broadcasts.editor.audience.notConnected")}>
            <div className="w-24">
              <TextInput
                type="number"
                min={1}
                max={MAX_NOT_CONNECTED_DAYS}
                inputMode="numeric"
                disabled={disabled}
                value={audience.not_connected_within_days ?? ""}
                placeholder={t("broadcasts.editor.audience.any")}
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
          </Row>
          <Row label={t("broadcasts.editor.audience.paid")}>
            {triState("paid", audience.paid, (paid) => set({ paid }))}
          </Row>
          <Row label={t("broadcasts.editor.audience.hasTelegram")}>
            {triState("telegram", audience.has_telegram, (has_telegram) => set({ has_telegram }))}
          </Row>
          <Row label={t("broadcasts.editor.audience.hasEmail")}>
            {triState("email", audience.has_email, (has_email) => set({ has_email }))}
          </Row>
          {botLocales.length > 1 && (
            <Row label={t("broadcasts.editor.audience.language")}>
              {chip("all", audience.locales.length === 0, t("broadcasts.editor.audience.all"), () =>
                set({ locales: [] }),
              )}
              {botLocales.map((locale) =>
                chip(locale, audience.locales.includes(locale), locale.toUpperCase(), () =>
                  set({ locales: toggle(audience.locales, locale) }),
                ),
              )}
            </Row>
          )}
          <Row label={t("broadcasts.editor.audience.source")}>
            {chip(
              "any",
              audience.referred === null && audience.ad_link_ids.length === 0,
              t("broadcasts.editor.audience.anySource"),
              () => set({ referred: null, ad_link_ids: [] }),
            )}
            {chip("referred", audience.referred === true, t("broadcasts.editor.audience.referred"), () =>
              set({ referred: audience.referred === true ? null : true }),
            )}
            {adLinks.map((link) =>
              chip(
                link.id,
                audience.ad_link_ids.includes(link.id),
                t("broadcasts.editor.audience.adLink", { name: link.name }),
                () => set({ ad_link_ids: toggle(audience.ad_link_ids, link.id) }),
              ),
            )}
          </Row>
          <div className="grid grid-cols-1 items-start gap-2 sm:grid-cols-[170px_minmax(0,1fr)] sm:gap-3">
            <span className="pt-2.5 text-[13px] text-foreground/80">{t("broadcasts.editor.audience.registered")}</span>
            <div className="flex flex-col gap-1">
              {disabled ? (
                <span className="pt-2.5 text-[13px] text-foreground">
                  {audience.registered_from || audience.registered_to
                    ? `${audience.registered_from ? formatDate(audience.registered_from, i18n.language) : "…"} – ${
                        audience.registered_to ? formatDate(audience.registered_to, i18n.language) : "…"
                      }`
                    : t("broadcasts.editor.audience.any")}
                </span>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <DatePickerField
                    variant="form"
                    value={audience.registered_from ?? ""}
                    placeholder={t("broadcasts.editor.audience.from")}
                    onChange={(value) => set({ registered_from: value || null })}
                  />
                  <DatePickerField
                    variant="form"
                    value={audience.registered_to ?? ""}
                    placeholder={t("broadcasts.editor.audience.to")}
                    onChange={(value) => set({ registered_to: value || null })}
                  />
                </div>
              )}
              {oneDateOnly && (
                <span className="text-[12px] text-error">{t("broadcasts.editor.audience.bothDates")}</span>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
