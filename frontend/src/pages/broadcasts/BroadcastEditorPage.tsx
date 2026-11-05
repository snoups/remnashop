import { ChevronLeft, Mail, MailOpen, MessageSquareText, Send, Settings2 } from "lucide-react";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate, useBlocker, useNavigate, useParams } from "react-router-dom";

import { listAdLinks } from "@entities/advertising/api";
import {
  createBroadcast,
  deleteBroadcast,
  getBroadcast,
  sendBroadcast,
  sendTestBroadcast,
  updateBroadcast,
} from "@entities/broadcasts/api";
import type { Broadcast } from "@entities/broadcasts/api";
import { BROADCAST_STATUS_TONE, broadcastTitle, isEditable } from "@entities/broadcasts/display";
import { listPlans } from "@entities/plans/api";
import { listPromocodes } from "@entities/promocodes/api";
import { getBotRequirements } from "@entities/settings/api";
import { listActiveLocales } from "@entities/translations/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { formatDateTime } from "@shared/lib/relative-time";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Badge } from "@shared/ui/Badge";
import { Collapse } from "@shared/ui/Collapse";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { PAGE_CLASS, PAGE_SCROLL_UNDER_BAR_CLASS, PAGE_TOOLBAR_CLASS } from "@shared/ui/classes";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Input } from "@shared/ui/glass/Input";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { IconButton } from "@shared/ui/IconButton";
import { PillTabs } from "@shared/ui/PillTabs";
import { Spinner } from "@shared/ui/Spinner";

import { AudienceEditor } from "@pages/broadcasts/editor/AudienceEditor";
import type { AudienceMode } from "@pages/broadcasts/editor/AudienceEditor";
import { ButtonsEditor } from "@pages/broadcasts/editor/ButtonsEditor";
import { CategoryPicker } from "@pages/broadcasts/editor/CategoryPicker";
import { ContentEditor } from "@pages/broadcasts/editor/ContentEditor";
import { DeliveryPicker } from "@pages/broadcasts/editor/DeliveryPicker";
import { EditorActions } from "@pages/broadcasts/editor/EditorActions";
import { EmailPreview } from "@pages/broadcasts/editor/EmailPreview";
import { isDirty, sendsEmail, sendsTelegram, toForm } from "@pages/broadcasts/editor/form";
import type { EditorForm } from "@pages/broadcasts/editor/form";
import { MediaField } from "@pages/broadcasts/editor/MediaField";
import { RecipientsPreview } from "@pages/broadcasts/editor/RecipientsPreview";
import { TelegramPreview } from "@pages/broadcasts/editor/TelegramPreview";
import { useAudiencePreview } from "@pages/broadcasts/editor/use-audience-preview";

// TipTap is only needed here, and only for broadcasts with email
const EmailEditor = lazy(() =>
  import("@pages/broadcasts/editor/EmailEditor").then((m) => ({ default: m.EmailEditor })),
);

const LIST_PATH = "/dashboard/broadcasts";
// first page only; a picker with search once a shop has more than this
const PICKER_PAGE_SIZE = 100;
const CHANNEL_NAME_RE = /t\.me\/([A-Za-z0-9_]{4,})\/?$/;

// "2026-10-08T18:30" in local time, what <input type="datetime-local"> takes
function toLocalInput(iso: string): string {
  const d = new Date(iso);
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function BroadcastEditorPage() {
  const { id } = useParams();
  const permissions = usePermissions();
  if (!permissions.includes(id ? "BROADCASTS_DETAIL_VIEW" : "BROADCASTS_CREATE")) {
    return <Navigate to="/dashboard" replace />;
  }
  // a new broadcast moves to /:id/edit on its first save; a fresh mount picks up the saved one
  return <BroadcastEditorLoader key={id ?? "new"} id={id ? Number(id) : null} />;
}

function BroadcastEditorLoader({ id }: { id: number | null }) {
  const { t, i18n } = useTranslation();
  const [broadcastState] = useAsyncResource((signal) => (id === null ? Promise.resolve(null) : getBroadcast(id, signal)));
  const [localesState] = useAsyncResource(listActiveLocales);

  if (broadcastState.kind === "loading" || localesState.kind === "loading") return <Spinner size="page" />;
  if (broadcastState.kind === "error") {
    return (
      <div className="glass-panel rounded-3xl p-4">
        <ErrorState text={t("common.loadError")} size="page" />
      </div>
    );
  }
  const broadcast = broadcastState.data;
  if (broadcast && !isEditable(broadcast)) return <Navigate to={`${LIST_PATH}/${broadcast.id}`} replace />;

  const botLocales = localesState.kind === "ready" ? localesState.data.active : [];
  const defaultLocale = botLocales.includes(i18n.language) ? i18n.language : (botLocales[0] ?? "en");
  return <BroadcastEditor initial={broadcast} botLocales={botLocales} defaultLocale={defaultLocale} />;
}

interface BroadcastEditorProps {
  initial: Broadcast | null;
  botLocales: string[];
  defaultLocale: string;
}

function BroadcastEditor({ initial, botLocales, defaultLocale }: BroadcastEditorProps) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const permissions = usePermissions();
  const can = (permission: (typeof permissions)[number]) => permissions.includes(permission);

  const [broadcast, setBroadcast] = useState(initial);
  const [form, setForm] = useState<EditorForm>(() => toForm(initial, defaultLocale));
  const [baseline, setBaseline] = useState(form);
  const [activeLocale, setActiveLocale] = useState(form.default_locale);
  const [mode, setMode] = useState<AudienceMode>(form.audience.user_ids.length > 0 ? "users" : "filters");
  const [mediaName, setMediaName] = useState<string | null>(null);
  const [scheduleAt, setScheduleAt] = useState(initial?.scheduled_at ? toLocalInput(initial.scheduled_at) : "");
  const [isBusy, setIsBusy] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [contentTab, setContentTab] = useState<"TELEGRAM" | "EMAIL">("TELEGRAM");
  const [previewTab, setPreviewTab] = useState<"TELEGRAM" | "EMAIL">("TELEGRAM");
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);

  const dirty = isDirty(form, baseline);
  // a scheduled broadcast's date field is its schedule: clearing or moving it is a change to save
  const savedScheduleAt = broadcast?.status === "SCHEDULED" && broadcast.scheduled_at ? toLocalInput(broadcast.scheduled_at) : null;
  const scheduleChanged = savedScheduleAt !== null && scheduleAt !== savedScheduleAt;
  // read when a navigation starts, after a save that cleared it in the same tick
  const dirtyRef = useRef(dirty);
  dirtyRef.current = dirty;

  const canEdit = can(broadcast ? "BROADCASTS_UPDATE" : "BROADCASTS_CREATE");

  const [plansState] = useAsyncResource((signal) => (can("PLANS_VIEW") ? listPlans(signal) : Promise.resolve([])));
  const [adLinksState] = useAsyncResource((signal) => listAdLinks({ pageSize: PICKER_PAGE_SIZE }, signal));
  const [promocodesState] = useAsyncResource((signal) =>
    can("PROMOCODES_VIEW")
      ? listPromocodes({ status: "ACTIVE", pageSize: PICKER_PAGE_SIZE }, signal)
      : Promise.resolve({ items: [], total: 0 }),
  );
  const [requirementsState] = useAsyncResource((signal) =>
    can("BOT_REQUIREMENTS_VIEW") ? getBotRequirements(signal) : Promise.resolve(null),
  );
  const plans = plansState.kind === "ready" ? plansState.data : [];
  const adLinks = adLinksState.kind === "ready" ? adLinksState.data.items : [];
  const promocodes = promocodesState.kind === "ready" ? promocodesState.data.items : [];
  const requirements = requirementsState.kind === "ready" ? requirementsState.data : null;
  const channelMissing = requirements !== null && requirements.channel_id === null;
  const channelMatch = requirements?.channel_url ? CHANNEL_NAME_RE.exec(requirements.channel_url) : null;
  const channelName = channelMatch ? `@${channelMatch[1]}` : null;
  const promocodeCode = promocodes.find((p) => p.id === form.promocode_id)?.code ?? null;

  const audience = form.audience;
  const audienceReady =
    mode === "users"
      ? audience.user_ids.length > 0
      : (audience.registered_from === null) === (audience.registered_to === null);
  const { state: previewState, freshTotal: recipients } = useAudiencePreview(
    audience,
    form.category,
    form.delivery,
    form.email_fallback,
    audienceReady && can("BROADCASTS_AUDIENCE_PREVIEW"),
  );

  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) => dirtyRef.current && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  // a save or media change drops a SCHEDULED broadcast to DRAFT; put it back on its slot while that is still ahead
  const keepSchedule = async (saved: Broadcast, previousAt: string | null): Promise<Broadcast> => {
    if (!previousAt || saved.status !== "DRAFT") return saved;
    if (can("BROADCASTS_SEND") && new Date(previousAt).getTime() > Date.now()) {
      try {
        const rescheduled = await sendBroadcast(saved.id, previousAt);
        setBroadcast(rescheduled);
        toast.success(t("broadcasts.editor.savedStillScheduled", { date: formatDateTime(previousAt, i18n.language) }));
        return rescheduled;
      } catch {
        // falls through to the off-schedule notice
      }
    }
    toast.warning(t("broadcasts.editor.savedUnscheduled"));
    return saved;
  };

  const persist = async (forSend = false): Promise<Broadcast> => {
    // only a DRAFT can be sent, so a SCHEDULED one is saved first to drop back to it
    if (broadcast && !dirty && !(forSend && broadcast.status === "SCHEDULED")) return broadcast;
    const previousAt = broadcast?.status === "SCHEDULED" ? broadcast.scheduled_at : null;
    const submitted = form;
    const saved = broadcast ? await updateBroadcast(broadcast.id, submitted) : await createBroadcast(submitted);
    setBroadcast(saved);
    setBaseline(submitted);
    dirtyRef.current = false;
    if (!broadcast) navigate(`${LIST_PATH}/${saved.id}/edit`, { replace: true });
    return forSend ? saved : keepSchedule(saved, previousAt);
  };

  const run = async (action: () => Promise<void>) => {
    setIsBusy(true);
    try {
      await action();
    } catch (err) {
      toast.error(getErrorMessage(err, t("common.errors.generic")));
    } finally {
      setIsBusy(false);
    }
  };

  const handleSave = () =>
    run(async () => {
      if (broadcast?.status !== "SCHEDULED") {
        await persist();
        toast.success(t("common.saved"));
        return;
      }
      // saving drops it to a draft; the date field then says where it goes: back on a slot, or nowhere
      const saved = await persist(true);
      if (!scheduleAt) {
        toast.success(t("broadcasts.editor.unscheduled"));
        return;
      }
      await keepSchedule(saved, new Date(scheduleAt).toISOString());
    });

  const handleTest = async () => {
    setIsTesting(true);
    await run(async () => {
      const saved = await persist();
      await sendTestBroadcast(saved.id);
      toast.success(t("broadcasts.editor.testSent"));
    });
    setIsTesting(false);
  };

  const handleSend = () =>
    run(async () => {
      const saved = await persist(true);
      await sendBroadcast(saved.id, scheduleAt ? new Date(scheduleAt).toISOString() : null);
      toast.success(t(scheduleAt ? "broadcasts.editor.scheduled" : "broadcasts.editor.sent"));
      navigate(`${LIST_PATH}/${saved.id}`, { replace: true });
    });

  const handleDelete = () =>
    run(async () => {
      if (!broadcast) return;
      await deleteBroadcast(broadcast.id);
      dirtyRef.current = false;
      toast.success(t("broadcasts.details.actions.delete.done"));
      navigate(LIST_PATH, { replace: true });
    });

  const status = broadcast?.status ?? "DRAFT";
  // both channels: one content card, a switch in its header picks the Telegram text or the email
  const bothChannels = sendsTelegram(form) && sendsEmail(form);
  const showTelegram = sendsTelegram(form) && (!bothChannels || contentTab === "TELEGRAM");
  const showEmail = sendsEmail(form) && (!bothChannels || contentTab === "EMAIL");
  const previewTelegram = sendsTelegram(form) && (!bothChannels || previewTab === "TELEGRAM");
  const previewEmail = sendsEmail(form) && (!bothChannels || previewTab === "EMAIL");
  const channelTabs = (active: "TELEGRAM" | "EMAIL", onSelect: (key: "TELEGRAM" | "EMAIL") => void) =>
    bothChannels ? (
      <PillTabs
        items={(["TELEGRAM", "EMAIL"] as const).map((key) => ({ key, label: t(`broadcasts.channel.${key}`) }))}
        activeKey={active}
        onSelect={onSelect}
      />
    ) : undefined;
  const previewTabs = channelTabs(previewTab, setPreviewTab);
  const contentTabs = channelTabs(contentTab, setContentTab);

  return (
    // as the settings pages: the title bar, the actions in it, floats over a scroller of its own,
    // whose fade clears it
    <div data-fills-main className={PAGE_CLASS}>
      <div className={PAGE_TOOLBAR_CLASS}>
        <IconButton size="9" tone="glass" onClick={() => navigate(LIST_PATH)}>
          <ChevronLeft className="size-4 text-foreground" />
        </IconButton>
        <Input
          type="text"
          value={form.title ?? ""}
          maxLength={120}
          disabled={!canEdit}
          placeholder={broadcastTitle({ ...form, title: null }, t("broadcasts.untitled"))}
          onChange={(event) => setForm({ ...form, title: event.target.value || null })}
          className="min-w-40 flex-1"
          // the status inside the field's end: a ~20px badge 8px in, on the 36px well's curve
          end={
            <span className="flex shrink-0 pr-1">
              <Badge borderless tone={BROADCAST_STATUS_TONE[status]}>{t(`broadcasts.status.${status}`)}</Badge>
            </span>
          }
        />
        <EditorActions
          isDirty={dirty || scheduleChanged}
          isBusy={isBusy}
          canSave={canEdit}
          canSend={can("BROADCASTS_SEND") && (canEdit || !dirty)}
          sendBlocked={!audienceReady}
          scheduleAt={scheduleAt}
          onScheduleChange={setScheduleAt}
          onSave={() => void handleSave()}
          onSend={() => setIsConfirmOpen(true)}
          onDelete={broadcast && can("BROADCASTS_DELETE") ? () => setIsDeleteOpen(true) : null}
        />
      </div>

      <div className={`${PAGE_SCROLL_UNDER_BAR_CLASS} flex flex-col gap-5`}>
      {/* full width: the rows read better long, and both columns follow from them */}
      <Section
        icon={Settings2}
        title={t("broadcasts.editor.sending.title")}
        description={t("broadcasts.editor.sending.description")}
      >
        <SectionRows>
          <CategoryPicker
            value={form.category}
            disabled={!canEdit}
            onChange={(category) => setForm({ ...form, category })}
          />
          <DeliveryPicker
            form={form}
            onChange={setForm}
            channelName={channelName}
            channelMissing={channelMissing}
            disabled={!canEdit}
          />
        </SectionRows>
      </Section>
      <div className="flex flex-wrap items-start gap-5">
        {/* cards that come and go (delivery, the content tabs) fold like the settings' spoilers: height
            and opacity together; their 20px gap rides inside them, so it folds away too */}
        <div className="flex min-w-0 flex-[999_1_560px] flex-col">
          {/* one card for the content, as a settings Section: switching Telegram | email swaps its body
              and the card eases to the new height */}
          <Collapse open={sendsTelegram(form) || sendsEmail(form)} className="pb-5">
            <Section
              icon={showEmail ? Mail : MessageSquareText}
              title={t(showEmail ? "broadcasts.editor.email.title" : "broadcasts.editor.text")}
              description={t("broadcasts.editor.fallbackHint")}
              aside={contentTabs}
            >
              {showTelegram && (
                <ContentEditor
                  form={form}
                  onChange={setForm}
                  activeLocale={activeLocale}
                  onLocaleChange={setActiveLocale}
                  botLocales={botLocales}
                  hasMedia={Boolean(broadcast?.media_type)}
                  disabled={!canEdit}
                >
                  <MediaField
                    broadcast={broadcast}
                    fileName={mediaName}
                    canSet={can("BROADCASTS_MEDIA_SET")}
                    canDelete={can("BROADCASTS_MEDIA_DELETE")}
                    onChanged={(updated, name) => {
                      const previousAt = broadcast?.status === "SCHEDULED" ? broadcast.scheduled_at : null;
                      setBroadcast(updated);
                      setMediaName(name);
                      void run(async () => void (await keepSchedule(updated, previousAt)));
                    }}
                  />
                </ContentEditor>
              )}
              {showEmail && (
                <Suspense fallback={<Spinner size="card" />}>
                  <EmailEditor
                    form={form}
                    onChange={setForm}
                    activeLocale={activeLocale}
                    onLocaleChange={setActiveLocale}
                    botLocales={botLocales}
                    broadcastId={broadcast?.id ?? null}
                    canAddImage={can("BROADCASTS_EMAIL_IMAGE_ADD")}
                    canViewImages={can("BROADCASTS_EMAIL_IMAGE_VIEW")}
                    disabled={!canEdit}
                  />
                </Suspense>
              )}
            </Section>
          </Collapse>
          <Collapse open={sendsTelegram(form)} className="pb-5">
            <ButtonsEditor
              form={form}
              onChange={setForm}
              activeLocale={activeLocale}
              promocodes={promocodes}
              disabled={!canEdit}
            />
          </Collapse>
          {/* one preview card under the buttons, its own Telegram | email switch, apart from the content card's */}
          <Section
            icon={previewEmail ? MailOpen : Send}
            title={t(previewEmail ? "broadcasts.editor.emailPreview.title" : "broadcasts.editor.preview.title")}
            description={t("broadcasts.editor.preview.as", { name: t("broadcasts.editor.preview.sampleName"), locale: activeLocale.toUpperCase() })}
            aside={previewTabs}
          >
            {previewTelegram && (
              <TelegramPreview
                  form={form}
                  locale={activeLocale}
                  mediaType={broadcast?.media_type ?? null}
                  mediaName={mediaName}
                  promocodeCode={promocodeCode}
                  onTest={can("BROADCASTS_TEST_SEND") && (canEdit || !dirty) ? () => void handleTest() : undefined}
                  isTesting={isTesting}
                  isSaved={broadcast !== null}
                />
            )}
            {/* kept mounted behind the Telegram tab: the letter is fetched already when its tab opens */}
            {sendsEmail(form) && (
              <EmailPreview
                  visible={previewEmail}
                  broadcastId={broadcast?.id ?? null}
                  savedAt={broadcast?.updated_at ?? null}
                  dirty={dirty}
                  locale={activeLocale}
                  canPreview={can("BROADCASTS_EMAIL_PREVIEW")}
                  canTestSend={can("BROADCASTS_EMAIL_TEST_SEND")}
                />
            )}
          </Section>
        </div>

        <div className="flex min-w-0 flex-[1_1_360px] flex-col">
          {/* beside the text: who gets it, next to what they get */}
          <div className="pb-5">
          <AudienceEditor
                audience={audience}
                onChange={(next) => setForm({ ...form, audience: next })}
                mode={mode}
                onModeChange={setMode}
                plans={plans}
                adLinks={adLinks}
                botLocales={botLocales}
                disabled={!canEdit}
              />
          </div>
          {can("BROADCASTS_AUDIENCE_PREVIEW") && (
            <RecipientsPreview
              state={previewState}
              category={form.category}
              defaultLocale={form.default_locale}
              contentLocales={Object.keys(form.contents)}
            />
          )}
        </div>
      </div>

      </div>

      {isDeleteOpen && (
        <ConfirmDialog
          title={t("broadcasts.details.actions.delete.title")}
          message={t("broadcasts.details.actions.delete.message")}
          confirmLabel={t("broadcasts.details.actions.delete.confirm")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => {
            setIsDeleteOpen(false);
            void handleDelete();
          }}
          onCancel={() => setIsDeleteOpen(false)}
        />
      )}

      {isConfirmOpen && (
        <ConfirmDialog
          title={t(scheduleAt ? "broadcasts.editor.confirm.scheduleTitle" : "broadcasts.editor.confirm.sendTitle")}
          message={(() => {
            const date = formatDateTime(new Date(scheduleAt || Date.now()).toISOString(), i18n.language);
            if (recipients === null) {
              return scheduleAt
                ? t("broadcasts.editor.confirm.scheduleUncounted", { date })
                : t("broadcasts.editor.confirm.sendUncounted");
            }
            return scheduleAt
              ? t("broadcasts.editor.confirm.schedule", { date, count: recipients })
              : t("broadcasts.editor.confirm.send", { count: recipients });
          })()}
          icon={Send}
          confirmLabel={t(scheduleAt ? "broadcasts.editor.footer.schedule" : "broadcasts.editor.footer.sendNow")}
          cancelLabel={t("common.cancel")}
          onConfirm={() => {
            setIsConfirmOpen(false);
            void handleSend();
          }}
          onCancel={() => setIsConfirmOpen(false)}
        />
      )}

      {blocker.state === "blocked" && (
        <ConfirmDialog
          title={t("broadcasts.editor.leave.title")}
          message={t("broadcasts.editor.leave.message")}
          confirmLabel={t("broadcasts.editor.leave.confirm")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => blocker.proceed()}
          onCancel={() => blocker.reset()}
        />
      )}
    </div>
  );
}
