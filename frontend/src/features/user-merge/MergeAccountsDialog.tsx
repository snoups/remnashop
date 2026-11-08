import type { ParseKeys } from "i18next";
import { ArrowLeftRight, GitMerge, Mail, Send, ShieldAlert, Swords, TriangleAlert, UserRound, Users } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { usePermissions } from "@entities/user/use-current-user";
import { getMergePreview, listUsers, mergeUsers, type MergeSide, type UserListItem } from "@entities/user/api";
import { userLabel } from "@entities/user/display";
import { ApiError, getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useDebouncedValue } from "@shared/lib/use-debounced-value";
import { EYEBROW_CLASS, GLASS_DIALOG_BODY_CLASS, GLASS_DIALOG_FOOTER_CLASS } from "@shared/ui/classes";
import { Button } from "@shared/ui/Button";
import { ChoiceChip } from "@shared/ui/ChoiceChip";
import { DialogCard } from "@shared/ui/glass/DialogCard";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { IconButton } from "@shared/ui/IconButton";
import { InfoRow } from "@shared/ui/InfoRow";
import { KpiTile } from "@shared/ui/KpiTile";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { SearchField } from "@shared/ui/SearchField";
import { Spinner } from "@shared/ui/Spinner";
import { Tooltip } from "@shared/ui/Tooltip";
import { UserRow } from "@shared/ui/UserRow";

const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_LIMIT = 6;
const COUNT_KEYS = ["subscriptions", "transactions", "referrals", "passkeys", "oauth_identities"] as const;
const MONO_KEYS = new Set(["telegram", "email", "login"]);

interface MergeAccountsDialogProps {
  user: UserListItem;
  /** skips the search, e.g. the account that already holds a Telegram ID */
  initialOther?: UserListItem;
  /** `removed` is the merged-in account, now deleted */
  onMerged: (merged: UserListItem, removed: UserListItem) => void;
  onClose: () => void;
}

export function MergeAccountsDialog({ user, initialOther, onMerged, onClose }: MergeAccountsDialogProps) {
  const { t } = useTranslation();
  const [other, setOther] = useState<UserListItem | null>(initialOther ?? null);
  const includeStaff = usePermissions().includes("ADMINS_MANAGE");
  return (
    <Modal onClose={onClose} size="lg" scrollable>
      <DialogHeader icon={GitMerge} title={t("users.merge.title")} />
      {other ? (
        <MergePreviewStep user={user} other={other} onMerged={onMerged} onChange={() => setOther(null)} />
      ) : (
        <MergePicker excludeId={user.id} includeStaff={includeStaff} onPick={setOther} />
      )}
    </Modal>
  );
}

function userSubtitle(user: UserListItem): string {
  return [`#${user.id}`, user.username ? `@${user.username}` : user.email].filter(Boolean).join(" · ");
}

function MergePicker({
  excludeId,
  includeStaff,
  onPick,
}: {
  excludeId: number;
  includeStaff: boolean;
  onPick: (user: UserListItem) => void;
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState("");
  const search = useDebouncedValue(query, SEARCH_DEBOUNCE_MS).trim();
  const [resultsState] = useAsyncResource(
    (signal) => (search ? listUsers({ search, pageSize: SEARCH_LIMIT + 1, includeStaff }, signal) : Promise.resolve(null)),
    { deps: [search] },
  );
  const results =
    resultsState.kind === "ready" && resultsState.data
      ? resultsState.data.items.filter((u) => u.id !== excludeId).slice(0, SEARCH_LIMIT)
      : [];

  return (
    <div className={`${GLASS_DIALOG_BODY_CLASS} flex flex-col gap-3`}>
      <SearchField
        id="merge-search"
        placeholder={t("users.merge.search")}
        value={query}
        onChange={setQuery}
      />
      {results.length > 0 && (
        <DialogCard icon={Users} title={t("users.merge.search")}>
          {results.map((candidate) => (
            <UserRow
              key={candidate.id}
              name={userLabel(candidate, candidate.id, t)}
              unnamed={!candidate.name && !candidate.login}
              subtitle={userSubtitle(candidate)}
              onClick={() => onPick(candidate)}
            />
          ))}
        </DialogCard>
      )}
    </div>
  );
}

function AccountColumn({ label, user }: { label: string; user: UserListItem }) {
  const { t } = useTranslation();
  return (
    <div className="min-w-0">
      <DialogCard icon={UserRound} title={label}>
        <InfoRow icon={UserRound} label={`#${user.id}`}>
          <span className="truncate">{userLabel(user, user.id, t)}</span>
        </InfoRow>
        <InfoRow icon={Mail} label={t("users.merge.conflict.email")} mono>
          <span className="truncate">{user.email ?? t("common.none")}</span>
        </InfoRow>
        <InfoRow icon={Send} label={t("users.merge.conflict.telegram")} mono>
          <span className="truncate">{user.telegram_id ?? t("common.none")}</span>
        </InfoRow>
      </DialogCard>
    </div>
  );
}

function MergePreviewStep({
  user,
  other,
  onMerged,
  onChange,
}: {
  user: UserListItem;
  other: UserListItem;
  onMerged: MergeAccountsDialogProps["onMerged"];
  onChange: () => void;
}) {
  const { t } = useTranslation();
  const close = useModalClose();
  // the opened account stays by default
  const [swapped, setSwapped] = useState(false);
  const [choices, setChoices] = useState<Record<string, MergeSide>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const target = swapped ? other : user;
  const source = swapped ? user : other;

  const [preview, reload] = useAsyncResource(
    (signal) =>
      // an API refusal (two staff accounts, no rights) is shown in place of the preview
      getMergePreview(target.id, source.id, signal).catch((err: unknown) => {
        if (err instanceof ApiError) return getErrorMessage(err, t("users.merge.error"));
        throw err;
      }),
    { deps: [target.id, source.id] },
  );
  const data = preview.kind === "ready" && typeof preview.data !== "string" ? preview.data : null;
  // the preview that a refused merge was built on; the button waits for a different one
  const [staleData, setStaleData] = useState<typeof data>(null);
  const isReloading = data !== null && data === staleData;
  const isComplete = data !== null && data.conflicts.every((c) => c.forced !== null || choices[c.key] !== undefined);
  // with a referred_by conflict, only the chosen side's inviter is kept
  const hasReferrerChoice = data?.conflicts.some((c) => c.key === "referred_by") ?? false;
  const droppedReferrers = data
    ? data.referrer_cycles.filter((cycle) => !hasReferrerChoice || choices.referred_by === cycle.side)
    : [];

  const conflictLabel = (key: string): string => {
    if (!key.startsWith("oauth:")) return t(`users.merge.conflict.${key}` as ParseKeys);
    const provider = key.slice("oauth:".length).toLowerCase();
    return t("users.merge.conflict.oauth", {
      provider: t(`profile.oauthAccounts.${provider === "oidc" ? "oidcFallback" : provider}` as ParseKeys),
    });
  };

  const handleMerge = async () => {
    if (!data) return;
    setIsSubmitting(true);
    try {
      const merged = await mergeUsers(data.target.id, data.source.id, choices, data.fingerprint);
      toast.success(t("users.merge.done"));
      onMerged(merged, data.source);
      close();
    } catch (err) {
      toast.error(getErrorMessage(err, t("users.merge.error")));
      // the accounts changed since the preview: show the new conflicts
      if (err instanceof ApiError && (err.code === "MERGE_CHOICE_MISSING" || err.code === "MERGE_PREVIEW_STALE")) {
        setChoices({});
        setStaleData(data);
        reload();
      }
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <div className={`${GLASS_DIALOG_BODY_CLASS} flex flex-col gap-3`}>
        <div className="grid grid-cols-1 items-center gap-2 sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
          <AccountColumn label={t("users.merge.keeps")} user={target} />
          <IconButton
            size="9"
            tone="glass"
            className="group relative justify-self-center"
            disabled={isSubmitting}
            onClick={() => {
              setSwapped((prev) => !prev);
              setChoices({});
            }}
          >
            <ArrowLeftRight className="size-4 rotate-90 sm:rotate-0" />
            <Tooltip text={t("users.merge.swap")} side="top" />
          </IconButton>
          <AccountColumn label={t("users.merge.mergedIn")} user={source} />
        </div>
        <div className="flex justify-end">
          <Button variant="glass" disabled={isSubmitting} onClick={onChange}>
            {t("users.merge.change")}
          </Button>
        </div>

        {preview.kind === "loading" && <Spinner size="card" />}
        {preview.kind === "error" && <ErrorState text={t("common.errors.generic")} />}
        {preview.kind === "ready" && typeof preview.data === "string" && <ErrorState text={preview.data} />}
        {data && (
          <>
            <span className={EYEBROW_CLASS}>{t("users.merge.moves")}</span>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {COUNT_KEYS.map((key) => (
                <KpiTile glass key={key} label={t(`users.merge.counts.${key}`)} value={String(data.source_counts[key])} />
              ))}
            </div>

            {data.conflicts.length > 0 && (
              <DialogCard icon={Swords} title={t("users.merge.conflicts")}>
                {data.conflicts.map((conflict) => (
                  <div key={conflict.key} className="flex flex-col gap-1.5 px-2.5 py-2">
                    <span className="text-[12.5px] text-muted-foreground">{conflictLabel(conflict.key)}</span>
                    <div className="flex flex-wrap gap-2">
                      {(["target", "source"] as const).map((side) => (
                        <ChoiceChip
                          key={side}
                          active={(conflict.forced ?? choices[conflict.key]) === side}
                          disabled={conflict.forced !== null || isSubmitting}
                          onClick={() => setChoices((prev) => ({ ...prev, [conflict.key]: side }))}
                        >
                          <span className={MONO_KEYS.has(conflict.key) ? "font-mono" : ""}>
                            {(side === "target" ? conflict.target_value : conflict.source_value) ?? t("common.none")}
                          </span>
                        </ChoiceChip>
                      ))}
                    </div>
                    {conflict.forced !== null && (
                      <span className="text-[12px] text-muted-foreground">{t("users.merge.forced")}</span>
                    )}
                  </div>
                ))}
              </DialogCard>
            )}

            {droppedReferrers.map((cycle) => (
              <p
                key={cycle.side}
                className="flex items-start gap-2 rounded-xl bg-warning/10 px-3 py-2.5 text-[12.5px] text-warning"
              >
                <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
                {t("users.merge.referrerCycle", { id: cycle.referrer_id })}
              </p>
            ))}

            <div className="flex items-center gap-2 rounded-xl border border-error/30 bg-error/10 px-3.5 py-3 text-[13px] text-error">
              <ShieldAlert className="size-4 shrink-0" />
              {t("users.merge.warning")}
            </div>
          </>
        )}
      </div>
      <div className={`${GLASS_DIALOG_FOOTER_CLASS} shrink-0 justify-end`}>
        <Button variant="glass" onClick={close}>
          {t("common.cancel")}
        </Button>
        <Button variant="glassDanger" disabled={!isComplete || isSubmitting || isReloading} onClick={() => void handleMerge()}>
          {t("users.merge.confirm")}
        </Button>
      </div>
    </>
  );
}
