import { CalendarClock, ChevronLeft, Image, Languages, Mail, Megaphone, RotateCcw, Send, Tag, Ticket, Trash2, User, Users } from "lucide-react";
import type { ParseKeys } from "i18next";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useNavigate, useParams } from "react-router-dom";

import {
  cancelBroadcast,
  deleteBroadcast,
  getBroadcast,
  recallBroadcast,
  retryBroadcast,
} from "@entities/broadcasts/api";
import type { Broadcast } from "@entities/broadcasts/api";
import {
  audienceSummary,
  BROADCAST_STATUS_TONE,
  broadcastTitle,
  canRecall,
  isRecallRunning,
  isEditable,
} from "@entities/broadcasts/display";
import { listPlans } from "@entities/plans/api";
import { getPromocode } from "@entities/promocodes/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { formatBytes } from "@shared/lib/format";
import { formatDateTime } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { Button } from "@shared/ui/Button";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { IconButton } from "@shared/ui/IconButton";
import { InfoRow } from "@shared/ui/InfoRow";
import { Spinner } from "@shared/ui/Spinner";
import { Tooltip } from "@shared/ui/Tooltip";

import { DeliveryProgress } from "@pages/broadcasts/details/DeliveryProgress";
import { RecipientsTable } from "@pages/broadcasts/details/RecipientsTable";

const LIST_PATH = "/dashboard/broadcasts";
const POLL_INTERVAL_MS = 5000;
const MAX_TIMEOUT_MS = 2 ** 31 - 1;

type Action = "cancel" | "retry" | "recall" | "delete";

const ACTION_REQUEST: Record<Exclude<Action, "delete">, (id: number) => Promise<Broadcast>> = {
  cancel: cancelBroadcast,
  retry: retryBroadcast,
  recall: recallBroadcast,
};

function isPolling(b: Broadcast | null, now: number): boolean {
  if (!b) return false;
  // a running recall moves rows to RECALLED, and the button comes back once it may repeat
  return (
    b.status === "SENDING" ||
    (b.status === "SCHEDULED" && !!b.scheduled_at && new Date(b.scheduled_at).getTime() <= now) ||
    isRecallRunning(b, now)
  );
}

export function BroadcastDetailsPage() {
  const { id } = useParams();
  const permissions = usePermissions();
  return permissions.includes("BROADCASTS_DETAIL_VIEW") ? (
    <BroadcastDetails key={id} id={Number(id)} />
  ) : (
    <Navigate to="/dashboard" replace />
  );
}

function BroadcastDetails({ id }: { id: number }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const permissions = usePermissions();
  const can = (permission: (typeof permissions)[number]) => permissions.includes(permission);

  const [loaded, setLoaded] = useState<{ kind: "loading" } | { kind: "error" } | { kind: "ready"; data: Broadcast }>({
    kind: "loading",
  });
  const [refreshKey, setRefreshKey] = useState(0);
  const [pending, setPending] = useState<Action | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [, setClock] = useState(0);
  // bumped when an action lands; a poll started earlier drops its response
  const actionEpochRef = useRef(0);
  const broadcast = loaded.kind === "ready" ? loaded.data : null;
  const polling = isPolling(broadcast, Date.now());

  useEffect(() => {
    const controller = new AbortController();
    getBroadcast(id, controller.signal)
      .then((data) => !controller.signal.aborted && setLoaded({ kind: "ready", data }))
      .catch(() => !controller.signal.aborted && setLoaded({ kind: "error" }));
    return () => controller.abort();
  }, [id]);

  const scheduledAt = broadcast?.status === "SCHEDULED" ? broadcast.scheduled_at : null;
  useEffect(() => {
    if (!scheduledAt) return;
    const delay = new Date(scheduledAt).getTime() - Date.now();
    if (delay <= 0) return;
    const timer = setTimeout(() => setClock((n) => n + 1), Math.min(delay, MAX_TIMEOUT_MS));
    return () => clearTimeout(timer);
  }, [scheduledAt]);

  useEffect(() => {
    if (!polling) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const epoch = actionEpochRef.current;
      if (document.hidden) {
        timer = setTimeout(() => void tick(), POLL_INTERVAL_MS);
        return;
      }
      try {
        const data = await getBroadcast(id, controller.signal);
        if (controller.signal.aborted || epoch !== actionEpochRef.current) return;
        setLoaded({ kind: "ready", data });
        setRefreshKey((key) => key + 1);
      } catch {
        // the next tick retries
      }
      if (!controller.signal.aborted) timer = setTimeout(() => void tick(), POLL_INTERVAL_MS);
    };
    timer = setTimeout(() => void tick(), POLL_INTERVAL_MS);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [id, polling]);

  const [plansState] = useAsyncResource((signal) => (can("PLANS_VIEW") ? listPlans(signal) : Promise.resolve([])));
  const [promocodeState] = useAsyncResource(
    (signal) =>
      broadcast?.promocode_id != null && can("PROMOCODES_DETAIL_VIEW")
        ? getPromocode(broadcast.promocode_id, signal)
        : Promise.resolve(null),
    { deps: [broadcast?.promocode_id] },
  );

  if (loaded.kind === "loading") return <Spinner size="page" />;
  if (loaded.kind === "error" || !broadcast) {
    return (
      <div className="glass-panel rounded-3xl p-4">
        <ErrorState text={t("common.loadError")} size="page" />
      </div>
    );
  }
  const b = broadcast;

  const now = Date.now();
  const plans = plansState.kind === "ready" ? plansState.data : [];
  const promocodeCode = promocodeState.kind === "ready" ? promocodeState.data?.code : undefined;
  const none = t("common.none");

  const canCancel = (b.status === "SCHEDULED" || b.status === "SENDING") && can("BROADCASTS_CANCEL");
  const retryable =
    (b.status === "COMPLETED" || b.status === "CANCELED" || b.status === "FAILED") &&
    b.failed_count > 0 &&
    b.recalled_count === 0 &&
    !b.recall_requested;
  // only with failed recipients to retry; a recall still shows it, greyed with the reason
  const showRetry =
    can("BROADCASTS_RETRY") &&
    (b.status === "COMPLETED" || b.status === "CANCELED" || b.status === "FAILED") &&
    b.failed_count > 0;
  // only while a recall can run: within 48h, not already running, something left in Telegram
  const showRecall = can("BROADCASTS_RECALL") && canRecall(b, now);
  const canEdit = isEditable(b) && can("BROADCASTS_UPDATE");
  const canDelete = b.status !== "SENDING" && can("BROADCASTS_DELETE");

  const run = async (action: Action) => {
    setPending(null);
    setIsBusy(true);
    try {
      if (action === "delete") {
        await deleteBroadcast(b.id);
        toast.success(t("broadcasts.details.actions.delete.done"));
        navigate(LIST_PATH, { replace: true });
        return;
      }
      const data = await ACTION_REQUEST[action](b.id);
      actionEpochRef.current += 1;
      setLoaded({ kind: "ready", data });
      setRefreshKey((key) => key + 1);
      toast.success(t(`broadcasts.details.actions.${action}.done` as ParseKeys));
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsBusy(false);
    }
  };

  return (
    // as the editor: the title bar, the actions in it, floats over a scroller of its own
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <IconButton size="9" tone="glass" onClick={() => navigate(LIST_PATH)}>
          <ChevronLeft className="size-4 text-foreground" />
        </IconButton>
        {/* the status right after the title, the actions pushed to the end */}
        <span className="flex min-w-0 flex-1 items-center gap-2 px-1.5">
          <span className="min-w-0 truncate text-[15px] font-semibold tracking-tight text-foreground">
            {broadcastTitle(b, t("broadcasts.untitled"))}
          </span>
          <span className="flex shrink-0">
            <Badge tone={BROADCAST_STATUS_TONE[b.status]}>{t(`broadcasts.status.${b.status}`)}</Badge>
          </span>
        </span>
        <div className="flex shrink-0 flex-wrap gap-2">
          {canEdit && (
            <Button variant="glass" onClick={() => navigate(`${LIST_PATH}/${b.id}/edit`)}>
              {t("common.edit")}
            </Button>
          )}
          {canCancel && (
            <Button variant="glass" disabled={isBusy} onClick={() => setPending("cancel")}>
              {t("broadcasts.details.actions.cancel.button")}
            </Button>
          )}
          {showRetry && (
            <span className="group relative">
              <Button variant="glass" disabled={isBusy || !retryable} onClick={() => setPending("retry")}>
                {t("broadcasts.details.actions.retry.button")}
              </Button>
              {!retryable && <Tooltip side="bottom" text={t("broadcasts.details.actions.retry.unavailable")} />}
            </span>
          )}
          {canDelete && (
            <IconButton size="9" tone="glass" disabled={isBusy} onClick={() => setPending("delete")}>
              {/* a glassDanger button's look, square: the bin in the error tone */}
              <Trash2 className="size-4 text-error" />
            </IconButton>
          )}
          {showRecall && (
            <span className="group relative">
              <Button variant="glassDanger" disabled={isBusy} onClick={() => setPending("recall")}>
                {t("broadcasts.details.actions.recall.button")}
              </Button>
              <Tooltip side="bottom-end" text={t("broadcasts.details.actions.recall.hint")} />
            </span>
          )}
        </div>
      </div>

      <div className={`${PAGE_SCROLL_UNDER_BAR_CLASS} flex flex-col gap-5`}>
      <DeliveryProgress broadcast={b} now={now}>
          <div className="grid lg:grid-cols-2 lg:gap-x-2">
            <InfoRow icon={Tag} label={t("broadcasts.details.params.category")}>
              {t(`broadcasts.category.${b.category}`)}
            </InfoRow>
            <InfoRow icon={b.delivery === "EMAIL" ? Mail : b.delivery === "ALL" ? Megaphone : Send} label={t("broadcasts.editor.delivery.title")}>
              {t(`broadcasts.editor.delivery.option.${b.delivery}`)}
            </InfoRow>
            <InfoRow icon={Languages} label={t("broadcasts.details.params.locales")}>
              {Object.keys(b.contents)
                .map((locale) => (locale === b.default_locale ? `${locale.toUpperCase()} ${t("broadcasts.details.params.main")}` : locale.toUpperCase()))
                .join(", ")}
            </InfoRow>
            <InfoRow icon={Users} label={t("broadcasts.details.params.audience")}>
              <span className="truncate">{audienceSummary(b.audience, t, plans)}</span>
            </InfoRow>
            {b.promocode_id !== null && (
              <InfoRow icon={Ticket} label={t("broadcasts.details.params.promocode")} mono>
                {promocodeCode ?? `#${b.promocode_id}`}
              </InfoRow>
            )}
            {b.media_type && (
              <InfoRow icon={Image} label={t("broadcasts.details.params.media")}>
                {t(`broadcasts.media.${b.media_type}` as ParseKeys)}
                {b.media_size_bytes !== null && ` · ${formatBytes(b.media_size_bytes, i18n.language)}`}
              </InfoRow>
            )}
            <InfoRow icon={User} label={t("broadcasts.details.params.createdBy")}>
              {[b.created_by_name, b.created_at ? formatDateTime(b.created_at, i18n.language) : null].filter(Boolean).join(" · ") || none}
            </InfoRow>
            {b.scheduled_at && (
              <InfoRow icon={CalendarClock} label={t("broadcasts.details.params.scheduledAt")}>
                {formatDateTime(b.scheduled_at, i18n.language)}
              </InfoRow>
            )}
            {(b.has_channel_post || b.post_to_channel) && (
              <InfoRow icon={Megaphone} label={t("broadcasts.details.channel.title")}>
                {b.has_channel_post ? t("broadcasts.details.channel.posted") : t("broadcasts.details.channel.planned")}
              </InfoRow>
            )}
          </div>
      </DeliveryProgress>

      {can("BROADCASTS_RECIPIENTS_VIEW") && <RecipientsTable broadcast={b} refreshKey={refreshKey} />}
      </div>

      {pending && (
        <ConfirmDialog
          title={t(`broadcasts.details.actions.${pending}.title` as ParseKeys)}
          message={t(`broadcasts.details.actions.${pending}.message` as ParseKeys)}
          confirmLabel={t(`broadcasts.details.actions.${pending}.confirm` as ParseKeys)}
          cancelLabel={t("common.cancel")}
          icon={RotateCcw}
          danger={pending !== "retry"}
          onConfirm={() => void run(pending)}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  );
}
