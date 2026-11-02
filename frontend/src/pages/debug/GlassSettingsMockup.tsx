import {
  BellRing,
  Bot,
  CircleCheck,
  Copy,
  CreditCard,
  FingerprintPattern,
  Globe,
  HelpCircle,
  KeyRound,
  KeySquare,
  Languages,
  Layers,
  Link2,
  MonitorSmartphone,
  RectangleEllipsis,
  Scale,
  Share2,
  ShieldCheck,
  ShoppingBag,
  Smartphone,
  UserPlus,
} from "lucide-react";
import { useId, useState, type ComponentType, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { KIND_ICONS } from "@features/legal-documents-editor/legal-drafts";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { Button } from "@shared/ui/Button";
import { DialogTabs } from "@shared/ui/DialogTabs";
import { FieldHint } from "@shared/ui/FieldHint";
import { DialogHeader } from "@shared/ui/glass/DialogHeader";
import { Field } from "@shared/ui/glass/Field";
import { Input, PasswordInput, TextArea } from "@shared/ui/glass/Input";
import { Row } from "@shared/ui/glass/Row";
import { Section, SectionFields, SectionRows } from "@shared/ui/glass/Section";
import { Switch } from "@shared/ui/glass/Switch";
import { TabBar } from "@shared/ui/glass/TabBar";
import { Tag } from "@shared/ui/glass/Tag";
import { TextWidth } from "@shared/ui/glass/TextWidth";
import { ToggleCapsule } from "@shared/ui/glass/ToggleCapsule";
import { IconButton } from "@shared/ui/IconButton";
import { Modal } from "@shared/ui/Modal";
import { PillTabs } from "@shared/ui/PillTabs";
import { SaveFooter } from "@shared/ui/SaveFooter";
import { SelectDropdown } from "@shared/ui/SelectDropdown";
import { SETTINGS_TABS } from "@widgets/sidebar/nav-items";

// Static mockup of Settings → General in liquid glass, built only from shared/ui/glass: the forms
// take the same pieces with real data. Type scale: 21 / 15 / 13 / 12 / 11.

const SETTINGS_ROOT = "/dashboard/settings";

export function GlassSettingsMockup() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-8">
      <TabBar
        items={SETTINGS_TABS.map((tab) => ({
          key: tab.key,
          to: `${SETTINGS_ROOT}/${tab.to}`,
          icon: tab.icon,
          label: t(`settings.tabs.${tab.key}`),
          isActive: tab.key === "general",
        }))}
      />
      <div className="flex flex-col gap-5">
        <OAuthSection />
        <AccessSection />
        <ShopSection />
        <PushSection />
        <LegalSection />
      </div>
    </div>
  );
}

function SaveBar({ dirty, beside }: { dirty: boolean; beside?: ReactNode }) {
  return <SaveFooter variant="glassAccent" dirty={dirty} saving={false} onSave={() => {}} beside={beside} />;
}

function GuideButton() {
  return (
    <IconButton size="8">
      <HelpCircle className="size-3.5" />
    </IconButton>
  );
}

function OAuthSection() {
  const { t } = useTranslation();
  const [flags, setFlags] = useState({ github: true, telegram: true, oidc: false, passkey: false, password: true });
  const dirty = !flags.github || !flags.telegram || flags.passkey || !flags.password;
  const set = (key: keyof typeof flags) => (value: boolean) => setFlags((prev) => ({ ...prev, [key]: value }));
  return (
    <Section
      icon={KeyRound}
      title={t("settings.oauth.title")}
      description={t("settings.oauth.description")}
      footer={<SaveBar dirty={dirty} />}
    >
      <SectionRows>
        <ProviderRow icon={GithubIcon} label={t("profile.oauthAccounts.github")} configured defaultOpen>
          <Switch checked={flags.github} onChange={set("github")} />
        </ProviderRow>
        <ProviderRow icon={TelegramIcon} label={t("profile.oauthAccounts.telegram")} configured>
          <Switch checked={flags.telegram} onChange={set("telegram")} />
        </ProviderRow>
        <ProviderRow icon={KeySquare} label={t("profile.oauthAccounts.oidcFallback")} configured={false}>
          <Switch checked={flags.oidc} onChange={set("oidc")} disabled />
        </ProviderRow>
        <ProviderRow icon={FingerprintPattern} label={t("settings.oauth.passkeyTitle")} configured>
          <Switch checked={flags.passkey} onChange={set("passkey")} />
        </ProviderRow>
        <Row
          icon={RectangleEllipsis}
          label={t("settings.oauth.passwordLoginLabel")}
          description={t("settings.oauth.passwordLoginDescription")}
        >
          <GuideButton />
          <Switch checked={flags.password} onChange={set("password")} />
        </Row>
      </SectionRows>
    </Section>
  );
}

function ProviderRow({
  icon,
  label,
  configured,
  defaultOpen = false,
  children,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  configured: boolean;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <Row
      icon={icon}
      label={label}
      description={
        <span className={`flex items-center gap-1.5 ${configured ? "text-success" : "text-warning"}`}>
          <span className="size-1.5 rounded-full bg-current" />
          {t(configured ? "settings.oauth.configured" : "settings.oauth.notConfigured")}
        </span>
      }
      expanded={open}
      onClick={() => setOpen((value) => !value)}
      panel={
        <>
          <Field label={t("settings.oauth.clientIdLabel")} htmlFor={`${id}-client-id`}>
            <Input id={`${id}-client-id`} placeholder={t("settings.oauth.placeholder")} autoComplete="off" />
          </Field>
          <Field label={t("settings.oauth.clientSecretLabel")} htmlFor={`${id}-client-secret`}>
            <PasswordInput
              id={`${id}-client-secret`}
              placeholder={t("settings.oauth.placeholder")}
              // "off" is ignored on password fields: the browser would offer the admin's saved password
              autoComplete="new-password"
            />
          </Field>
        </>
      }
    >
      <GuideButton />
      {children}
    </Row>
  );
}

const MODES = ["public", "invited", "restricted"] as const;

function AccessSection() {
  const { t } = useTranslation();
  const [mode, setMode] = useState<(typeof MODES)[number]>("public");
  const [registration, setRegistration] = useState(true);
  const [payments, setPayments] = useState(false);
  return (
    <Section
      icon={ShieldCheck}
      title={t("settings.access.title")}
      description={t("settings.access.description")}
      aside={
        <PillTabs
          items={MODES.map((key) => ({ key, label: t(`settings.access.modes.${key}`) }))}
          activeKey={mode}
          onSelect={setMode}
        />
      }
      footer={<SaveBar dirty={mode !== "public" || !registration || payments} />}
    >
      <SectionRows>
        <Row icon={UserPlus} label={t("settings.access.registrationLabel")}>
          <Switch checked={registration} onChange={setRegistration} />
        </Row>
        <Row icon={CreditCard} label={t("settings.access.paymentsLabel")}>
          {!payments && <Tag>{t("settings.access.waitlist", { count: 12 })}</Tag>}
          <Switch checked={payments} onChange={setPayments} />
        </Row>
      </SectionRows>
    </Section>
  );
}

const RESETS = [
  { key: "deviceSingle", icon: Smartphone, label: "settings.shop.deviceSingleResetLabel", hours: "24" },
  { key: "deviceAll", icon: MonitorSmartphone, label: "settings.shop.deviceAllResetLabel", hours: "168" },
  { key: "link", icon: Link2, label: "settings.shop.linkResetLabel", hours: "72" },
  { key: "referral", icon: Share2, label: "settings.shop.referralResetLabel", hours: "0" },
] as const;

function ShopSection() {
  const { t } = useTranslation();
  const id = useId();
  const [enabled, setEnabled] = useState<Record<string, boolean>>({
    deviceSingle: true,
    deviceAll: true,
    link: false,
    referral: true,
  });
  const unlimited = t("settings.shop.unlimitedPlaceholder");
  return (
    <Section
      icon={ShoppingBag}
      title={t("settings.shop.title")}
      description={t("settings.shop.description")}
      footer={<SaveBar dirty={!enabled.deviceSingle || !enabled.deviceAll || enabled.link || !enabled.referral} />}
    >
      <SectionRows>
        <Row icon={Layers} label={t("settings.shop.maxActiveSubscriptionsLabel")}>
          {/* 2px: the reset rows end 16px in (switch), this one 14px */}
          <TextWidth text={unlimited} className="mr-0.5">
            <Input size="sm" className="flex-1" type="number" min="1" step="1" placeholder={unlimited} />
          </TextWidth>
        </Row>
        {RESETS.map((reset) => (
          <Row key={reset.key} icon={reset.icon} label={t(reset.label)}>
            {/* field + switch as wide as the limit field above */}
            <TextWidth text={unlimited}>
              <Input
                size="sm"
                className="flex-1"
                type="number"
                min="0"
                step="1"
                defaultValue={reset.hours}
                suffix={t("settings.shop.hoursSuffix")}
                disabled={!enabled[reset.key]}
              />
              <Switch
                checked={enabled[reset.key]}
                onChange={(value) => setEnabled((prev) => ({ ...prev, [reset.key]: value }))}
              />
            </TextWidth>
          </Row>
        ))}
      </SectionRows>
      <SectionFields divided>
        <Field label={t("settings.shop.supportTelegramLabel")} htmlFor={`${id}-telegram`}>
          <Input id={`${id}-telegram`} placeholder={t("settings.shop.supportTelegramPlaceholder")} autoComplete="off" />
        </Field>
        <Field label={t("settings.shop.supportUrlLabel")} htmlFor={`${id}-url`}>
          <Input id={`${id}-url`} type="url" placeholder={t("settings.shop.supportUrlPlaceholder")} autoComplete="off" />
        </Field>
      </SectionFields>
    </Section>
  );
}

const PUBLIC_KEY = "BMx7pQ2vR8nK1sT4wY6zA3cF5hJ9lN0oP2qS4uV6xZ8bD1eG3iK5mO7rT9vX1zB3dF5hJ7lN9pR1tV3x";

function PushSection() {
  const { t } = useTranslation();
  const id = useId();
  return (
    <Section
      icon={BellRing}
      title={t("settings.webPush.title")}
      description={t("settings.webPush.description")}
      aside={<Button variant="glass">{t("settings.webPush.test")}</Button>}
      footer={<SaveBar dirty={false} beside={<Button variant="glassDanger">{t("settings.webPush.regenerate")}</Button>} />}
    >
      <SectionFields>
        <Field label={t("settings.webPush.contact")} htmlFor={`${id}-contact`}>
          <Input
            id={`${id}-contact`}
            type="email"
            placeholder={t("settings.webPush.contactPlaceholder")}
            defaultValue="admin@example.com"
          />
        </Field>
        <Field label={t("settings.webPush.publicKey")} htmlFor={`${id}-key`}>
          <Input
            id={`${id}-key`}
            mono
            readOnly
            value={PUBLIC_KEY}
            end={
              <IconButton size="7">
                <Copy className="size-3.5" />
              </IconButton>
            }
          />
        </Field>
      </SectionFields>
    </Section>
  );
}

type LegalKind = (typeof LEGAL)[number]["kind"];
type LegalFlags = { bot: boolean; cabinet: boolean };

const LEGAL = [
  { kind: "OFFER", bot: true, cabinet: true },
  { kind: "USER_AGREEMENT", bot: true, cabinet: false },
  { kind: "PRIVACY_POLICY", bot: false, cabinet: true },
] as const;

function LegalSection() {
  const { t } = useTranslation();
  const [flags, setFlags] = useState<Record<string, LegalFlags>>(
    Object.fromEntries(LEGAL.map(({ kind, bot, cabinet }) => [kind, { bot, cabinet }])),
  );
  const [editing, setEditing] = useState<LegalKind | null>(null);
  const status = ({ bot, cabinet }: LegalFlags) =>
    [bot && t("settings.legal.tabs.BOT"), cabinet && t("settings.legal.tabs.CABINET")].filter(Boolean).join(" · ") ||
    t("settings.legal.hidden");
  return (
    <Section icon={Scale} title={t("settings.legal.title")} description={t("settings.legal.description")}>
      <SectionRows>
        {LEGAL.map(({ kind }) => (
          <Row key={kind} icon={KIND_ICONS[kind]} label={t(`settings.legal.kinds.${kind}`)} description={status(flags[kind])}>
            <Button variant="glass" size="sm" onClick={() => setEditing(kind)}>
              {t("common.edit")}
            </Button>
          </Row>
        ))}
      </SectionRows>
      {editing && (
        <LegalDialog
          kind={editing}
          flags={flags[editing]}
          onSave={(next) => setFlags((prev) => ({ ...prev, [editing]: next }))}
          onClose={() => setEditing(null)}
        />
      )}
    </Section>
  );
}

type LegalTab = "common" | "BOT" | "CABINET";

const TEXT_LIMIT = 32763;
const SAMPLE_BODY = `## 1. Общие положения

1.1. Настоящий документ определяет условия использования сервиса.
1.2. Оплачивая подписку, пользователь принимает условия оферты.

## 2. Стоимость и оплата

2.1. Стоимость тарифов указана в боте и веб-кабинете.`;

function LegalDialog({
  kind,
  flags,
  onSave,
  onClose,
}: {
  kind: LegalKind;
  flags: LegalFlags;
  onSave: (flags: LegalFlags) => void;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const id = useId();
  const initialTitle = t(`settings.legal.kinds.${kind}`);
  const [visibility, setVisibility] = useState(flags);
  const [tab, setTab] = useState<LegalTab>("common");
  const [locale, setLocale] = useState("ru");
  const [title, setTitle] = useState(initialTitle);
  const [body, setBody] = useState(SAMPLE_BODY);
  const [reaccept, setReaccept] = useState(false);
  const dirty =
    body !== SAMPLE_BODY || title !== initialTitle || visibility.bot !== flags.bot || visibility.cabinet !== flags.cabinet;
  return (
    <Modal onClose={onClose} size="xl" scrollable material="glass">
      <DialogHeader icon={KIND_ICONS[kind]} title={initialTitle} />
      <div className="scroll-fade-y flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
        <div className="flex items-center gap-2">
          <div className="min-w-0 flex-1">
            <DialogTabs
              activeKey={tab}
              onSelect={setTab}
              items={[
                { key: "common", label: t("settings.legal.tabs.common"), icon: Layers },
                { key: "BOT", label: t("settings.legal.tabs.BOT"), icon: Bot },
                { key: "CABINET", label: t("settings.legal.tabs.CABINET"), icon: Globe },
              ]}
            />
          </div>
          <div className="w-32 shrink-0">
            <SelectDropdown
              value={locale}
              onChange={setLocale}
              icon={Languages}
              size="lg"
              placeholder=""
              options={[
                { value: "ru", label: "RU", icon: CircleCheck },
                { value: "en", label: "EN" },
              ]}
            />
          </div>
        </div>
        <Field label={t("settings.legal.visibility")}>
          <div className="flex gap-2">
            <ToggleCapsule
              icon={Bot}
              label={t("settings.legal.tabs.BOT")}
              checked={visibility.bot}
              onChange={(bot) => setVisibility((prev) => ({ ...prev, bot }))}
            />
            <ToggleCapsule
              icon={Globe}
              label={t("settings.legal.tabs.CABINET")}
              checked={visibility.cabinet}
              onChange={(cabinet) => setVisibility((prev) => ({ ...prev, cabinet }))}
            />
          </div>
        </Field>
        <Field label={t("settings.legal.titleLabel")} htmlFor={`${id}-title`} required>
          <Input id={`${id}-title`} value={title} onChange={(event) => setTitle(event.target.value)} />
        </Field>
        <Field
          label={t("settings.legal.bodyLabel")}
          htmlFor={`${id}-body`}
          required
          hint={t("settings.legal.bodyHint", { limit: TEXT_LIMIT })}
        >
          <TextArea
            id={`${id}-body`}
            rows={14}
            mono
            value={body}
            onChange={(event) => setBody(event.target.value)}
            corner={`${body.length + title.length} / ${TEXT_LIMIT}`}
          />
        </Field>
        <div className="flex items-center gap-3">
          <p className="flex min-w-0 flex-1 items-center gap-1.5 text-[13px] font-medium text-foreground">
            {t("settings.legal.reaccept")}
            <FieldHint text={t("settings.legal.reacceptHint")} glass />
          </p>
          <Switch checked={reaccept} onChange={setReaccept} />
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2 border-t border-white/[0.08] px-5 py-3.5">
        <div className="min-w-0 flex-1">
          {dirty && (
            <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
              <span className="size-1.5 shrink-0 rounded-full bg-warning" />
              {t("common.unsavedChanges")}
            </span>
          )}
        </div>
        <Button variant="glass">{t("settings.legal.insertTemplate")}</Button>
        <Button variant="glassAccent" disabled={!dirty} onClick={() => onSave(visibility)}>
          {t("common.save")}
        </Button>
      </div>
    </Modal>
  );
}
