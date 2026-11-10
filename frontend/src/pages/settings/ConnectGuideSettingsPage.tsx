import {
  AppWindow,
  ArrowDown,
  ArrowUp,
  Check,
  Copy,
  Download,
  ExternalLink,
  Eye,
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
  Upload,
  type LucideIcon,
} from "lucide-react";
import { useRef, useState, type FormEvent, type ReactNode } from "react";
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
import { GLASS_INNER_CARD_CLASS, GLASS_PLATE_CLASS } from "@shared/ui/classes";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { ErrorState } from "@shared/ui/glass/EmptyState";
import { Field } from "@shared/ui/glass/Field";
import { IconCircle } from "@shared/ui/glass/IconCircle";
import { Input, TextArea } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionRows } from "@shared/ui/glass/Section";
import { StatusPill } from "@shared/ui/glass/StatusPill";
import { Switch } from "@shared/ui/glass/Switch";
import { IconButton } from "@shared/ui/IconButton";
import { PillTabs } from "@shared/ui/PillTabs";
import { Pressable } from "@shared/ui/Pressable";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { Spinner } from "@shared/ui/Spinner";
import { Tooltip } from "@shared/ui/Tooltip";

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
const FORBIDDEN_DEEP_LINK_SCHEMES = ["http", "https", "javascript", "data", "vbscript", "file", "blob", "about", "intent"];
const BLOCK_CLASS = `flex flex-col gap-3 p-3.5 ${GLASS_INNER_CARD_CLASS}`;

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

function isObject(value: unknown): value is object {
  return typeof value === "object" && value !== null;
}

function isLocalized(value: unknown): boolean {
  return isObject(value) && Object.values(value).every((text) => typeof text === "string");
}

function isButton(button: { label?: unknown; kind?: unknown; url?: unknown; template?: unknown }): boolean {
  if (!isObject(button) || !isLocalized(button.label)) return false;
  if (button.kind === "external") return typeof button.url === "string";
  if (button.kind === "deep_link") return typeof button.template === "string";
  return button.kind === "copy_link";
}

function isStep(step: { title?: unknown; body?: unknown; buttons?: unknown }): boolean {
  return (
    isObject(step) &&
    isLocalized(step.title) &&
    (step.body === undefined || step.body === null || isLocalized(step.body)) &&
    Array.isArray(step.buttons) &&
    step.buttons.every(isButton)
  );
}

// only what the editor reads; the backend checks the rest on Save
function isCatalog(value: unknown): value is ConnectCatalog {
  if (!isObject(value) || !("platforms" in value) || !Array.isArray(value.platforms)) return false;
  return (value.platforms as { id?: unknown; apps?: unknown }[]).every(
    (platform) =>
      isObject(platform) &&
      PLATFORM_IDS.includes(platform.id as PlatformId) &&
      Array.isArray(platform.apps) &&
      (platform.apps as { name?: unknown; steps?: unknown }[]).every(
        (app) => isObject(app) && typeof app.name === "string" && Array.isArray(app.steps) && app.steps.every(isStep),
      ),
  );
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

const hasText = (text: LocalizedText) => Object.values(text).some((value) => value.trim() !== "");

function isUrlInvalid(url: string): boolean {
  try {
    return new URL(url).protocol !== "https:";
  } catch {
    return true;
  }
}

// mirrors the backend's catalog rules for a deep link
function isTemplateInvalid(template: string): boolean {
  const scheme = /^([a-zA-Z][a-zA-Z0-9+.-]*):/.exec(template)?.[1];
  return (
    !template.includes(SUBSCRIPTION_LINK_TOKEN) ||
    scheme === undefined ||
    FORBIDDEN_DEEP_LINK_SCHEMES.includes(scheme.toLowerCase())
  );
}

function isButtonInvalid(button: DraftButton): boolean {
  if (!hasText(button.label)) return true;
  if (button.kind === "external") return isUrlInvalid(button.url);
  return button.kind === "deep_link" && isTemplateInvalid(button.template);
}

const isStepInvalid = (step: DraftStep) => !hasText(step.title) || step.buttons.some(isButtonInvalid);

const isAppInvalid = (app: DraftApp) => app.name.trim() === "" || app.steps.length === 0 || app.steps.some(isStepInvalid);

function InvalidDot() {
  return <span className="size-1.5 shrink-0 rounded-full bg-error" />;
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
  if (kind === "deep_link") return { key, kind, label, template: `app://add/${SUBSCRIPTION_LINK_TOKEN}` };
  return { key, kind, label };
}

function newStep(title: LocalizedText, icon: StepIcon): DraftStep {
  return { key: randomId(), title, body: null, icon, buttons: [] };
}

function OrderControls({
  index,
  count,
  disabled,
  canRemove = true,
  onMove,
  onRemove,
}: {
  index: number;
  count: number;
  disabled: boolean;
  canRemove?: boolean;
  onMove: (to: number) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center gap-0.5">
      <IconButton size="9" disabled={disabled || index === 0} onClick={() => onMove(index - 1)}>
        <ArrowUp className="size-4" />
      </IconButton>
      <IconButton
        size="9"
        disabled={disabled || index === count - 1}
        onClick={() => onMove(index + 1)}
      >
        <ArrowDown className="size-4" />
      </IconButton>
      <IconButton size="9" tone="danger" disabled={disabled || !canRemove} onClick={onRemove}>
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
      className="flex min-h-11 items-center gap-3 rounded-full px-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-white/[0.04] hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
    >
      <IconCircle icon={Plus} />
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
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-glass-border bg-white/[0.03] text-sm font-semibold">
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
            glassPopover
          />
        </div>
        <span className="flex-1" />
        {/* an app needs at least one step */}
        <OrderControls index={index} count={count} disabled={disabled} canRemove={count > 1} onMove={onMove} onRemove={onRemove} />
      </div>
      <Field label={t("connectGuide.stepTitle")}>
        <Input
          value={step.title[locale] ?? ""}
          disabled={disabled}
          aria-invalid={!hasText(step.title)}
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

      <span className="text-sm font-medium text-foreground">{t("connectGuide.buttons")}</span>
      {step.buttons.map((button, at) => (
        <div key={button.key} className={`${GLASS_PLATE_CLASS} flex flex-col gap-2 p-3`}>
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
                variant="well"
              />
            </div>
            <Input
              className="min-w-40 flex-1"
              placeholder={t("connectGuide.buttonLabel")}
              value={button.label[locale] ?? ""}
              disabled={disabled}
              aria-invalid={!hasText(button.label)}
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
            <Input
              placeholder="https://"
              value={button.url}
              disabled={disabled}
              aria-invalid={isUrlInvalid(button.url)}
              maxLength={ADDRESS_MAX_LENGTH}
              onChange={(event) => setButton(at, { ...button, url: event.target.value })}
            />
          )}
          {button.kind === "deep_link" && (
            <div className="flex flex-wrap items-center gap-2">
              <Input
                className="min-w-60 flex-1"
                mono
                value={button.template}
                disabled={disabled}
                aria-invalid={isTemplateInvalid(button.template)}
                maxLength={ADDRESS_MAX_LENGTH}
                onChange={(event) => setButton(at, { ...button, template: event.target.value })}
              />
              <span className="w-full text-xs text-muted-foreground">
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
  const [saved, setSaved] = useState<ConnectGuide | null>(null);
  const [draft, setDraft] = useState<Draft>(() => toDraft({ platforms: [] }));
  const [platform, setPlatform] = useState<PlatformId>("ios");
  const [appIndex, setAppIndex] = useState(0);
  const [locales, setLocales] = useState<string[]>([]);
  const [locale, setLocale] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isResetConfirmOpen, setIsResetConfirmOpen] = useState(false);
  const [pendingImport, setPendingImport] = useState<ConnectCatalog | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const disabled = !canManage || isSaving;

  const apply = (guide: ConnectGuide) => {
    setEnabled(guide.enabled);
    setIsDefault(guide.is_default);
    setSaved(guide);
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

  const setFeatured = (featured: boolean) =>
    setApps(apps.map((a, i) => ({ ...a, featured: i === appIndex ? featured : featured ? false : a.featured })));

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

  const handleExport = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(toCatalog(draft), null, 2)], { type: "application/json" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `connect-guide-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleFileChosen = async (file: File) => {
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (!isCatalog(parsed)) throw new Error("not a connect guide export");
      setPendingImport(parsed);
    } catch {
      toast.error(t("connectGuide.importInvalid"));
    }
  };

  // into the draft: Save validates and stores it
  const handleImportConfirmed = () => {
    if (pendingImport === null) return;
    setDraft(toDraft(pendingImport));
    setLocales((prev) => [...new Set([...prev, ...catalogLocales(pendingImport)])]);
    setAppIndex(0);
    setPendingImport(null);
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

  const title = t("connectGuide.title");
  const description = t("connectGuide.description");

  if (state.kind !== "ready") {
    return (
      <Section icon={Smartphone} title={title} description={description}>
        {state.kind === "loading" ? <Spinner size="card" /> : <ErrorState text={t("common.loadError")} />}
      </Section>
    );
  }

  const dirty =
    saved !== null &&
    (enabled !== saved.enabled || JSON.stringify(toCatalog(draft)) !== JSON.stringify(toCatalog(toDraft(saved.catalog))));
  const hasInvalid = PLATFORM_IDS.some((id) => draft[id].some(isAppInvalid));
  const resetButton = canReset && (
    <Button variant="glassDanger" disabled={isSaving || isDefault} onClick={() => setIsResetConfirmOpen(true)}>
      {t("common.reset")}
    </Button>
  );

  return (
    <form onSubmit={(event) => void handleSubmit(event)}>
      <Section
        icon={Smartphone}
        title={title}
        description={description}
        aside={
          <>
            <Button variant="glass" icon={Download} onClick={handleExport}>
              {t("dialogs.toolbar.export")}
            </Button>
            {canManage && (
              <Button variant="glass" icon={Upload} onClick={() => fileInputRef.current?.click()}>
                {t("dialogs.toolbar.import")}
              </Button>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                // cleared so picking the same file twice in a row still fires
                event.target.value = "";
                if (file) void handleFileChosen(file);
              }}
            />
            {saved !== null && (
              <StatusPill tone={saved.enabled ? "success" : "warning"}>
                {saved.enabled ? t("connectGuide.status.enabled") : t("connectGuide.status.disabled")}
              </StatusPill>
            )}
          </>
        }
        footer={
          canManage ? (
            <SaveFooter dirty={dirty} saving={isSaving} disabled={hasInvalid} beside={resetButton} />
          ) : (
            resetButton && <div className="mt-4 flex items-center gap-3">{resetButton}</div>
          )
        }
      >
        <SectionRows>
          <Row icon={Eye} label={t("connectGuide.enabledLabel")} hint={t("connectGuide.enabledHint")}>
            <Switch checked={enabled} onChange={setEnabled} disabled={disabled} />
          </Row>
        </SectionRows>

        <div className={`mt-4 flex flex-col gap-3 transition-opacity ${enabled ? "" : "opacity-45"}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <PillTabs
              items={PLATFORM_IDS.map((id) => ({
                key: id,
                label: (
                  <span className="flex items-center gap-1.5">
                    {t(`connectGuide.platforms.${id}`)}
                    {draft[id].length ? ` · ${draft[id].length}` : ""}
                    {draft[id].some(isAppInvalid) && <InvalidDot />}
                  </span>
                ),
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

          <div className="grid gap-3 lg:grid-cols-[16rem_minmax(0,1fr)]">
            <div className="flex flex-col gap-1">
              <span className="px-3 pb-1 text-sm font-medium text-foreground">{t("connectGuide.apps")}</span>
              {apps.map((candidate, index) => (
                <Pressable
                  key={candidate.id}
                  type="button"
                  onClick={() => setAppIndex(index)}
                  className={`flex h-10 items-center gap-2 rounded-full px-3 text-left text-sm font-medium transition-colors ${
                    index === appIndex ? "bg-accent text-primary" : "text-foreground/90 hover:bg-white/[0.04]"
                  } ${isAppInvalid(candidate) ? "ring-1 ring-inset ring-error" : ""}`}
                >
                  <span className="min-w-0 flex-1 truncate">{candidate.name}</span>
                  {candidate.featured && <Star className="size-3.5 shrink-0 fill-primary text-primary" />}
                </Pressable>
              ))}
              {apps.length === 0 && <p className="px-3 text-xs text-muted-foreground">{t("connectGuide.noApps")}</p>}
              {apps.length < MAX_APPS && <AddRow label={t("connectGuide.addApp")} disabled={disabled} onClick={addApp} />}
            </div>

            {app && (
              <div className="flex flex-col gap-3">
                <div className={BLOCK_CLASS}>
                  <div className="flex flex-wrap items-end gap-3">
                    <div className="min-w-48 flex-1">
                    <Field label={t("connectGuide.appName")} required>
                      <Input
                        value={app.name}
                        disabled={disabled}
                        aria-invalid={app.name.trim() === ""}
                        maxLength={APP_NAME_MAX_LENGTH}
                        onChange={(event) => setApp({ ...app, name: event.target.value })}
                      />
                    </Field>
                    </div>
                    <IconButton
                      size="9"
                      className="group relative"
                      disabled={disabled}
                      // one recommended app per platform
                      onClick={() => setFeatured(!app.featured)}
                    >
                      <Star className={`size-4 ${app.featured ? "fill-primary text-primary" : "text-muted-foreground"}`} />
                      <Tooltip text={t("connectGuide.featured")} side="top" />
                    </IconButton>
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

                <span className="px-1 text-sm font-medium text-foreground">{t("connectGuide.steps")}</span>
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

      </Section>

      {pendingImport && (
        <ConfirmDialog
          title={t("dialogs.toolbar.import")}
          icon={Upload}
          message={t("connectGuide.importConfirm")}
          confirmLabel={t("dialogs.toolbar.importConfirmButton")}
          cancelLabel={t("common.cancel")}
          onConfirm={handleImportConfirmed}
          onCancel={() => setPendingImport(null)}
        />
      )}

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
