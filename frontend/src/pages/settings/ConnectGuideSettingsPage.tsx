import {
  AppWindow,
  ArrowDown,
  ArrowUp,
  Check,
  Code,
  Copy,
  Download,
  ExternalLink,
  Globe,
  Info,
  Link,
  MousePointerClick,
  Plus,
  Power,
  QrCode,
  Settings,
  Shield,
  Smartphone,
  Star,
  Trash2,
  type LucideIcon,
} from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  getConnectGuide,
  PLATFORM_IDS,
  resetConnectGuide,
  saveConnectGuide,
  STEP_ICONS,
  SUBSCRIPTION_LINK_TOKEN,
  type ConnectApp,
  type ConnectButton,
  type ConnectCatalog,
  type ConnectGuide,
  type ConnectStep,
  type LocalizedText,
  type PlatformId,
  type StepIcon,
} from "@entities/connect-guide/api";
import { listActiveLocales } from "@entities/translations/api";
import { usePermissions } from "@entities/user/use-current-user";
import { getErrorMessage } from "@shared/api/http";
import { randomId } from "@shared/lib/random-string";
import { toast } from "@shared/lib/toast";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { Button } from "@shared/ui/Button";
import { Card } from "@shared/ui/Card";
import { CardHeader } from "@shared/ui/CardHeader";
import { EYEBROW_CLASS } from "@shared/ui/classes";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/EmptyState";
import { Field } from "@shared/ui/Field";
import { FieldHint } from "@shared/ui/FieldHint";
import { IconButton } from "@shared/ui/IconButton";
import { PillTabs } from "@shared/ui/PillTabs";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Switch } from "@shared/ui/Switch";
import { TextArea, TextInput } from "@shared/ui/TextInput";
import { Pressable } from "@shared/ui/Pressable";

// client-only keys, so a moved step or button keeps its React identity; stripped on save
type DraftButton = ConnectButton & { key: string };
type DraftStep = Omit<ConnectStep, "buttons"> & { key: string; buttons: DraftButton[] };
type DraftApp = Omit<ConnectApp, "steps"> & { steps: DraftStep[] };
// the editor keeps every platform; one without apps is left out on save
type Draft = Record<PlatformId, DraftApp[]>;

const BUTTON_KINDS = ["external", "deep_link", "copy_link"] as const;
const BUTTON_KIND_ICONS: Record<ConnectButton["kind"], LucideIcon> = {
  external: ExternalLink,
  deep_link: AppWindow,
  copy_link: Copy,
};
const STEP_ICON_COMPONENTS: Record<StepIcon, LucideIcon> = {
  download: Download,
  plus: Plus,
  power: Power,
  settings: Settings,
  check: Check,
  link: Link,
  qr: QrCode,
  info: Info,
  shield: Shield,
  globe: Globe,
};
// the backend catalog's limits
const MAX_APPS = 12;
const MAX_STEPS = 10;
const MAX_BUTTONS = 4;
const APP_NAME_MAX_LENGTH = 40;
const LINE_MAX_LENGTH = 120;
const PARAGRAPH_MAX_LENGTH = 1000;
const ADDRESS_MAX_LENGTH = 2000;
const BLOCK_CLASS = "flex flex-col gap-3 rounded-2xl max-md:rounded-card border border-white/[0.08] bg-white/[0.03] p-3.5";

function toDraft(catalog: ConnectCatalog): Draft {
  const draft = Object.fromEntries(PLATFORM_IDS.map((id) => [id, [] as DraftApp[]])) as Draft;
  for (const platform of catalog.platforms)
    draft[platform.id] = platform.apps.map((app) => ({
      ...app,
      steps: app.steps.map((step) => ({
        ...step,
        key: randomId(),
        buttons: step.buttons.map((button) => ({ ...button, key: randomId() })),
      })),
    }));
  return draft;
}

// drops blank languages, so a locale left empty falls back instead of showing nothing
function clean(text: LocalizedText): LocalizedText {
  return Object.fromEntries(Object.entries(text).filter(([, value]) => value.trim() !== ""));
}

function toCatalog(draft: Draft): ConnectCatalog {
  return {
    platforms: PLATFORM_IDS.filter((id) => draft[id].length > 0).map((id) => ({
      id,
      apps: draft[id].map((app) => ({
        ...app,
        steps: app.steps.map(({ key: _stepKey, ...step }) => {
          const body = step.body && clean(step.body);
          return {
            ...step,
            title: clean(step.title),
            body: body && Object.keys(body).length > 0 ? body : null,
            buttons: step.buttons.map(({ key: _buttonKey, ...button }) => ({ ...button, label: clean(button.label) })),
          };
        }),
      })),
    })),
  };
}

function catalogLocales(catalog: ConnectCatalog): string[] {
  const found = new Set<string>();
  for (const platform of catalog.platforms)
    for (const app of platform.apps)
      for (const step of app.steps) {
        Object.keys(step.title).forEach((locale) => found.add(locale));
        Object.keys(step.body ?? {}).forEach((locale) => found.add(locale));
        step.buttons.forEach((button) => Object.keys(button.label).forEach((locale) => found.add(locale)));
      }
  return [...found];
}

function move<T>(items: T[], from: number, to: number): T[] {
  if (to < 0 || to >= items.length) return items;
  const next = [...items];
  const [item] = next.splice(from, 1);
  next.splice(to, 0, item as T);
  return next;
}

function newButton(kind: ConnectButton["kind"], label: LocalizedText, key = randomId()): DraftButton {
  if (kind === "external") return { key, kind, label, url: "https://" };
  if (kind === "deep_link") return { key, kind, label, template: `app://add/${SUBSCRIPTION_LINK_TOKEN}`, encode: "raw" };
  return { key, kind, label };
}

function newStep(title: LocalizedText, icon: StepIcon): DraftStep {
  return { key: randomId(), title, body: null, icon, buttons: [] };
}

function OrderControls({
  index,
  count,
  disabled,
  onMove,
  onRemove,
}: {
  index: number;
  count: number;
  disabled: boolean;
  onMove: (to: number) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center gap-0.5">
      <IconButton size="8" disabled={disabled || index === 0} onClick={() => onMove(index - 1)}>
        <ArrowUp className="size-4" />
      </IconButton>
      <IconButton
        size="8"
        disabled={disabled || index === count - 1}
        onClick={() => onMove(index + 1)}
      >
        <ArrowDown className="size-4" />
      </IconButton>
      <IconButton size="8" tone="danger" disabled={disabled} onClick={onRemove}>
        <Trash2 className="size-4" />
      </IconButton>
    </div>
  );
}

function AddRow({ label, disabled, onClick }: { label: ReactNode; disabled: boolean; onClick: () => void }) {
  return (
    <Pressable
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="flex h-10 items-center gap-2.5 rounded-full px-3 text-[13px] font-medium text-muted-foreground transition-colors hover:bg-white/[0.04] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span className="flex size-6 items-center justify-center rounded-full border border-dashed border-white/[0.18]">
        <Plus className="size-3.5" />
      </span>
      {label}
    </Pressable>
  );
}

function StepEditor({
  step,
  index,
  count,
  locale,
  disabled,
  onChange,
  onMove,
  onRemove,
}: {
  step: DraftStep;
  index: number;
  count: number;
  locale: string;
  disabled: boolean;
  onChange: (step: DraftStep) => void;
  onMove: (to: number) => void;
  onRemove: () => void;
}) {
  const { t } = useTranslation();
  const setButton = (at: number, button: DraftButton) =>
    onChange({ ...step, buttons: step.buttons.map((b, i) => (i === at ? button : b)) });

  return (
    <div className={BLOCK_CLASS}>
      <div className="flex items-center gap-3">
        <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-white/[0.05] text-[12.5px] font-semibold">
          {index + 1}
        </span>
        <div className="w-44">
          <SelectDropdown
            value={step.icon}
            onChange={(icon) => onChange({ ...step, icon: icon as ConnectStep["icon"] })}
            options={STEP_ICONS.map((icon) => ({
              value: icon,
              label: t(`connectGuide.icons.${icon}`),
              icon: STEP_ICON_COMPONENTS[icon],
            }))}
            placeholder={t("connectGuide.stepIcon")}
            icon={Smartphone}
            disabled={disabled}
            size="compact"
            variant="form"
          />
        </div>
        <span className="flex-1" />
        <OrderControls index={index} count={count} disabled={disabled} onMove={onMove} onRemove={onRemove} />
      </div>
      <Field label={t("connectGuide.stepTitle")}>
        <TextInput
          value={step.title[locale] ?? ""}
          disabled={disabled}
          maxLength={LINE_MAX_LENGTH}
          onChange={(event) => onChange({ ...step, title: { ...step.title, [locale]: event.target.value } })}
        />
      </Field>
      <Field label={t("connectGuide.stepBody")}>
        <TextArea
          rows={2}
          value={step.body?.[locale] ?? ""}
          disabled={disabled}
          maxLength={PARAGRAPH_MAX_LENGTH}
          onChange={(event) => onChange({ ...step, body: { ...step.body, [locale]: event.target.value } })}
        />
      </Field>

      <span className={EYEBROW_CLASS}>{t("connectGuide.buttons")}</span>
      {step.buttons.map((button, at) => (
        <div key={button.key} className="flex flex-col gap-2 rounded-xl bg-white/[0.03] p-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <div className="w-48">
              <SelectDropdown
                value={button.kind}
                onChange={(kind) => setButton(at, newButton(kind as ConnectButton["kind"], button.label, button.key))}
                options={BUTTON_KINDS.map((kind) => ({
                  value: kind,
                  label: t(`connectGuide.kinds.${kind}`),
                  icon: BUTTON_KIND_ICONS[kind],
                }))}
                placeholder={t("connectGuide.buttonKind")}
                icon={MousePointerClick}
                disabled={disabled}
                size="compact"
                variant="form"
              />
            </div>
            <TextInput
              className="min-w-40 flex-1"
              placeholder={t("connectGuide.buttonLabel")}
              value={button.label[locale] ?? ""}
              disabled={disabled}
              maxLength={LINE_MAX_LENGTH}
              onChange={(event) => setButton(at, { ...button, label: { ...button.label, [locale]: event.target.value } })}
            />
            <OrderControls
              index={at}
              count={step.buttons.length}
              disabled={disabled}
              onMove={(to) => onChange({ ...step, buttons: move(step.buttons, at, to) })}
              onRemove={() => onChange({ ...step, buttons: step.buttons.filter((_, i) => i !== at) })}
            />
          </div>
          {button.kind === "external" && (
            <TextInput
              placeholder="https://"
              value={button.url}
              disabled={disabled}
              maxLength={ADDRESS_MAX_LENGTH}
              onChange={(event) => setButton(at, { ...button, url: event.target.value })}
            />
          )}
          {button.kind === "deep_link" && (
            <div className="flex flex-wrap items-center gap-2">
              <TextInput
                className="min-w-60 flex-1 font-mono"
                value={button.template}
                disabled={disabled}
                maxLength={ADDRESS_MAX_LENGTH}
                onChange={(event) => setButton(at, { ...button, template: event.target.value })}
              />
              <div className="w-56">
                <SelectDropdown
                  value={button.encode}
                  onChange={(encode) => setButton(at, { ...button, encode: encode as "raw" | "component" })}
                  options={(["raw", "component"] as const).map((encode) => ({
                    value: encode,
                    label: t(`connectGuide.encodes.${encode}`),
                  }))}
                  placeholder={t("connectGuide.encode")}
                  icon={Code}
                  disabled={disabled}
                  size="compact"
                  variant="form"
                />
              </div>
              <span className="w-full text-[12px] text-muted-foreground">
                {t("connectGuide.templateHint", { token: SUBSCRIPTION_LINK_TOKEN })}
              </span>
            </div>
          )}
        </div>
      ))}
      {step.buttons.length < MAX_BUTTONS && (
        <AddRow
          label={t("connectGuide.addButton")}
          disabled={disabled}
          onClick={() => onChange({ ...step, buttons: [...step.buttons, newButton("external", {})] })}
        />
      )}
    </div>
  );
}

export function ConnectGuideSettingsPage() {
  const { t } = useTranslation();
  const permissions = usePermissions();
  const canManage = permissions.includes("CONNECT_GUIDE_MANAGE");
  const canReset = permissions.includes("CONNECT_GUIDE_RESET");
  const [enabled, setEnabled] = useState(true);
  const [isDefault, setIsDefault] = useState(true);
  const [draft, setDraft] = useState<Draft>(() => toDraft({ platforms: [] }));
  const [platform, setPlatform] = useState<PlatformId>("ios");
  const [appIndex, setAppIndex] = useState(0);
  const [locales, setLocales] = useState<string[]>([]);
  const [locale, setLocale] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const disabled = !canManage || isSaving;

  const apply = (guide: ConnectGuide) => {
    setEnabled(guide.enabled);
    setIsDefault(guide.is_default);
    setDraft(toDraft(guide.catalog));
  };

  const load = async (signal?: AbortSignal) => {
    const guide = await getConnectGuide(signal);
    // the shop's languages; without LOCALES_VIEW the catalog's own ones
    const active = await listActiveLocales(signal).then(
      (result) => [result.default, ...result.active.filter((l) => l !== result.default)],
      () => [],
    );
    const all = [...new Set([...active, ...catalogLocales(guide.catalog)])];
    return { guide, locales: all.length > 0 ? all : ["ru", "en"] };
  };
  const [state] = useAsyncResource(load, {
    onSuccess: (result) => {
      apply(result.guide);
      setLocales(result.locales);
      setLocale(result.locales[0] ?? "ru");
    },
  });

  const apps = draft[platform];
  const app = apps[appIndex];
  const setApps = (next: DraftApp[]) => setDraft((prev) => ({ ...prev, [platform]: next }));
  const setApp = (next: DraftApp) => setApps(apps.map((a, i) => (i === appIndex ? next : a)));

  const addApp = () => {
    const name = t("connectGuide.newApp");
    setApps([
      ...apps,
      {
        id: `app-${Date.now().toString(36)}`,
        name,
        featured: false,
        steps: [newStep({ [locale]: t("connectGuide.newStep") }, "download")],
      },
    ]);
    setAppIndex(apps.length);
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setIsSaving(true);
    try {
      apply(await saveConnectGuide({ enabled, catalog: toCatalog(draft) }));
      toast.success(t("connectGuide.saved"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("connectGuide.error")));
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    setIsResetConfirmOpen(false);
    setIsSaving(true);
    try {
      apply(await resetConnectGuide());
      setAppIndex(0);
      toast.success(t("connectGuide.resetSuccess"));
    } catch (err) {
      toast.error(getErrorMessage(err, t("connectGuide.resetError")));
    } finally {
      setIsSaving(false);
    }
  };

  const header = (
    <CardHeader
      icon={Smartphone}
      title={t("connectGuide.title")}
      description={t("connectGuide.description")}
      aside={
        state.kind === "ready" && (
          <>
            <FieldHint text={t("connectGuide.enabledHint")} side="bottom" align="end" />
            <Switch checked={enabled} onChange={setEnabled} disabled={disabled} />
          </>
        )
      }
    />
  );

  if (state.kind === "loading") return <Spinner size="page" />;
  if (state.kind === "error") {
    return (
      <Card>
        {header}
        <ErrorState text={t("common.loadError")} />
      </Card>
    );
  }

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Card className="flex flex-col gap-4">
        {header}
        {isDefault && <p className="text-[12px] text-muted-foreground">{t("connectGuide.defaultNote")}</p>}

        <div className={`flex flex-col gap-4 transition-opacity ${enabled ? "" : "opacity-45"}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <PillTabs
              items={PLATFORM_IDS.map((id) => ({
                key: id,
                label: `${t(`connectGuide.platforms.${id}`)}${draft[id].length ? ` · ${draft[id].length}` : ""}`,
              }))}
              activeKey={platform}
              onSelect={(id) => {
                setPlatform(id);
                setAppIndex(0);
              }}
            />
            {locales.length > 1 && (
              <PillTabs
                items={locales.map((l) => ({ key: l, label: l.toUpperCase() }))}
                activeKey={locale}
                onSelect={setLocale}
              />
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
            <div className="flex flex-col gap-1">
              <span className={`px-3 pb-1 ${EYEBROW_CLASS}`}>{t("connectGuide.apps")}</span>
              {apps.map((candidate, index) => (
                <Pressable
                  key={candidate.id}
                  type="button"
                  onClick={() => setAppIndex(index)}
                  className={`flex h-10 items-center gap-2 rounded-full px-3 text-left text-[13px] font-medium transition-colors ${
                    index === appIndex ? "bg-accent text-primary" : "text-foreground/90 hover:bg-white/[0.04]"
                  }`}
                >
                  <span className="min-w-0 flex-1 truncate">{candidate.name}</span>
                  {candidate.featured && <Star className="size-3.5 shrink-0 fill-warning text-warning" />}
                </Pressable>
              ))}
              {apps.length === 0 && <p className="px-3 text-[12px] text-muted-foreground">{t("connectGuide.noApps")}</p>}
              {apps.length < MAX_APPS && <AddRow label={t("connectGuide.addApp")} disabled={disabled} onClick={addApp} />}
            </div>

            {app && (
              <div className="flex flex-col gap-3">
                <div className={BLOCK_CLASS}>
                  <div className="flex flex-wrap items-end gap-3">
                    <Field label={t("connectGuide.appName")} className="min-w-48 flex-1">
                      <TextInput
                        value={app.name}
                        disabled={disabled}
                        maxLength={APP_NAME_MAX_LENGTH}
                        required
                        onChange={(event) => setApp({ ...app, name: event.target.value })}
                      />
                    </Field>
                    <label className="flex h-9.5 items-center gap-2 text-[13px] text-foreground/80">
                      <Switch
                        checked={app.featured}
                        disabled={disabled}
                        // one recommended app per platform
                        onChange={(featured) =>
                          setApps(apps.map((a, i) => ({ ...a, featured: i === appIndex ? featured : featured ? false : a.featured })))
                        }
                      />
                      {t("connectGuide.featured")}
                    </label>
                    <OrderControls
                      index={appIndex}
                      count={apps.length}
                      disabled={disabled}
                      onMove={(to) => {
                        setApps(move(apps, appIndex, to));
                        setAppIndex(to);
                      }}
                      onRemove={() => {
                        setApps(apps.filter((_, i) => i !== appIndex));
                        setAppIndex(Math.max(0, appIndex - 1));
                      }}
                    />
                  </div>
                </div>

                <span className={`px-1 ${EYEBROW_CLASS}`}>{t("connectGuide.steps")}</span>
                {app.steps.map((step, index) => (
                  <StepEditor
                    key={step.key}
                    step={step}
                    index={index}
                    count={app.steps.length}
                    locale={locale}
                    disabled={disabled}
                    onChange={(next) => setApp({ ...app, steps: app.steps.map((s, i) => (i === index ? next : s)) })}
                    onMove={(to) => setApp({ ...app, steps: move(app.steps, index, to) })}
                    onRemove={() => setApp({ ...app, steps: app.steps.filter((_, i) => i !== index) })}
                  />
                ))}
                {app.steps.length < MAX_STEPS && (
                  <AddRow
                    label={t("connectGuide.addStep")}
                    disabled={disabled}
                    onClick={() =>
                      setApp({ ...app, steps: [...app.steps, newStep({}, "check")] })
                    }
                  />
                )}
              </div>
            )}
          </div>
        </div>

        {(canManage || canReset) && (
          <div className="flex flex-wrap items-center gap-2">
            {canManage && (
              <Button variant="accent" type="submit" disabled={isSaving}>
                {isSaving ? t("common.saving") : t("common.save")}
              </Button>
            )}
            {canReset && !isDefault && (
              <Button variant="outline" type="button" disabled={isSaving} onClick={() => setIsResetConfirmOpen(true)}>
                {t("common.reset")}
              </Button>
            )}
          </div>
        )}
      </Card>

      {isResetConfirmOpen && (
        <ConfirmDialog
          title={t("connectGuide.resetConfirmTitle")}
          message={t("connectGuide.resetConfirmText")}
          confirmLabel={t("common.reset")}
          cancelLabel={t("common.cancel")}
          danger
          onConfirm={() => void handleReset()}
          onCancel={() => setIsResetConfirmOpen(false)}
        />
      )}
    </form>
  );
}
