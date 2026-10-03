import { Coins, Copy, Download, Forward, Hash, Layers, Pencil, SearchX, Settings, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { Announcement } from "@entities/announcements/api";
import { DebugSection, Specimen } from "@pages/debug/debug-ui";
import { useKit } from "@pages/debug/use-kit";
import { AnnouncementsCarousel } from "@widgets/announcements/AnnouncementsCarousel";
import { ActionMenu } from "@shared/ui/ActionMenu";
import { Badge } from "@shared/ui/Badge";
import { GithubIcon, TelegramIcon } from "@shared/ui/BrandIcons";
import { BrandLogo } from "@shared/ui/BrandLogo";
import { Button } from "@shared/ui/Button";
import { POPOVER_CLASS } from "@shared/ui/classes";
import { Collapse } from "@shared/ui/Collapse";
import { ConfirmDialog } from "@shared/ui/ConfirmDialog";
import { CopyableValue } from "@shared/ui/CopyableValue";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { EmptyState } from "@shared/ui/EmptyState";
import { FieldHint } from "@shared/ui/FieldHint";
import { GuideDialog } from "@shared/ui/GuideDialog";
import { IconButton } from "@shared/ui/IconButton";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Spinner } from "@shared/ui/Spinner";
import { Tooltip } from "@shared/ui/Tooltip";
import { initials } from "@shared/lib/initials";

const TOOLTIP_SIDES = ["right", "bottom", "top", "top-start", "top-end"] as const;
const MENU_ITEM =
  "flex h-9 w-full items-center gap-2.5 rounded-popover-item px-2.5 text-left text-[13px] font-medium text-foreground transition-colors hover:bg-white/[0.07]";
const noop = () => undefined;

const SAMPLE_STORIES: Announcement[] = [
  {
    id: "sample-info",
    icon: "sparkles",
    severity: "info",
    title: { en: "Sample announcement", ru: "Пример объявления" },
    text: { en: "Sample announcement", ru: "Пример объявления" },
    url: null,
    url_label: {},
    notify_at: "2026-01-01T00:00:00Z",
    auto_open: false,
    seen: false,
    slides: [
      { image_url: null, text: { en: "First slide of a sample announcement", ru: "Первый слайд примера объявления" }, url: null, url_label: {} },
      { image_url: null, text: { en: "Second slide of a sample announcement", ru: "Второй слайд примера объявления" }, url: null, url_label: {} },
      {
        image_url: null,
        text: { en: "Last slide with a link", ru: "Последний слайд со ссылкой" },
        url: "https://github.com/remnashop/remnashop/releases",
        url_label: {},
      },
    ],
  },
  {
    id: "sample-critical",
    icon: "warning",
    severity: "critical",
    title: { en: "Sample critical announcement", ru: "Пример важного объявления" },
    text: { en: "Sample critical announcement", ru: "Пример важного объявления" },
    url: null,
    url_label: {},
    notify_at: "2026-01-02T00:00:00Z",
    auto_open: false,
    seen: false,
    slides: [{ image_url: null, text: { en: "Something needs your attention", ru: "Нужно ваше внимание" }, url: null, url_label: {} }],
  },
];

function DemoModalBody() {
  const k = useKit();
  const close = useModalClose();
  return (
    <>
      <DialogHeader icon={Layers} title="Modal" />
      <div className="flex flex-col gap-4 p-5">
        <p className="text-[12.5px] text-muted-foreground">{k("s.modalText")}</p>
        <Button variant="outline" onClick={close}>
          {k("s.close")}
        </Button>
      </div>
    </>
  );
}

export function DialogsSection() {
  const k = useKit();
  const { t } = useTranslation();
  const [modalSize, setModalSize] = useState<"sm" | "lg" | null>(null);
  const [confirm, setConfirm] = useState<"accent" | "danger" | null>(null);
  const [carouselOpen, setCarouselOpen] = useState(false);
  const frame = "overflow-hidden rounded-dialog border border-white/[0.14] bg-popover/60";

  return (
    <DebugSection id="dialogs">
      <Specimen name="DialogHeader" usage={k("u.dialogHeader")} stage="stretch" wide>
        <div className="grid gap-3 lg:grid-cols-2">
          <div className={frame}>
            <DialogHeader icon={Pencil} title={k("s.editProfile")} onClose={noop} />
          </div>
          <div className={frame}>
            <DialogHeader
              glyph={<span className="text-[11px] font-bold">{initials(k("s.person"))}</span>}
              title={k("s.person")}
              badges={<Badge tone="accent">{t("roles.OWNER")}</Badge>}
              subtitle={<span className="font-mono">anna</span>}
              onClose={noop}
            />
          </div>
          <div className={frame}>
            <DialogHeader icon={Layers} tone="primary" title={k("s.subscription")} subtitle="#1042" onClose={noop} />
          </div>
          <div className={frame}>
            <DialogHeader icon={Trash2} tone="danger" title={k("s.confirmTitle")} onClose={noop} />
          </div>
          <div className={frame}>
            <DialogHeader
              icon={Hash}
              title={k("s.botLogs")}
              actions={<Button variant="outline" size="sm">{k("s.refresh")}</Button>}
              onClose={noop}
            />
          </div>
          <div className={frame}>
            <DialogHeader icon={Coins} title={k("s.noClose")} onClose={null} />
          </div>
        </div>
      </Specimen>
      <Specimen name='Modal · size="sm | lg"' usage={k("u.modal")}>
        <Button variant="outline" onClick={() => setModalSize("sm")}>
          sm
        </Button>
        <Button variant="outline" onClick={() => setModalSize("lg")}>
          lg
        </Button>
      </Specimen>
      <Specimen name="ConfirmDialog · danger" usage={k("u.confirm")}>
        <Button variant="accent" onClick={() => setConfirm("accent")}>
          {k("s.save")}
        </Button>
        <Button variant="danger" onClick={() => setConfirm("danger")}>
          <Trash2 className="size-3.5" />
          {k("s.delete")}
        </Button>
      </Specimen>
      <Specimen name="AnnouncementsCarousel" usage={k("u.announcementsCarousel")}>
        <Button variant="outline" onClick={() => setCarouselOpen(true)}>
          {k("s.openCarousel")}
        </Button>
      </Specimen>

      {carouselOpen && (
        <AnnouncementsCarousel stories={SAMPLE_STORIES} startIndex={0} onClose={() => setCarouselOpen(false)} />
      )}
      {modalSize && (
        <Modal onClose={() => setModalSize(null)} size={modalSize}>
          <DemoModalBody />
        </Modal>
      )}
      {confirm && (
        <ConfirmDialog
          title={k("s.confirmTitle")}
          message={k("s.confirmText")}
          confirmLabel={confirm === "danger" ? k("s.delete") : k("s.save")}
          cancelLabel={k("s.cancel")}
          danger={confirm === "danger"}
          icon={confirm === "danger" ? Trash2 : undefined}
          onConfirm={() => setConfirm(null)}
          onCancel={() => setConfirm(null)}
        />
      )}
    </DebugSection>
  );
}

export function HintsSection() {
  const k = useKit();
  const { t } = useTranslation();
  const long = k("s.hintLong");

  return (
    <DebugSection id="hints">
      <Specimen name='FieldHint · side · align' usage={k("u.fieldHint")} stage="stretch">
        <span className="flex items-center gap-1.5 text-sm font-medium text-foreground/80">
          {k("s.hintTop")}
          <FieldHint text={long} />
        </span>
        <span className="flex items-center gap-1.5 text-sm font-medium text-foreground/80">
          {k("s.hintBottom")}
          <FieldHint text={k("s.hintShort")} side="bottom" />
        </span>
        <h3 className="flex items-center gap-1.5 text-sm font-bold text-foreground">
          {k("s.hintHeading")}
          <FieldHint text={long} side="bottom" />
        </h3>
        <div className="flex items-center justify-between rounded-full bg-white/[0.04] px-3 py-2">
          <span className="text-sm text-foreground/80">{k("s.hintEnd")}</span>
          <FieldHint text={long} side="bottom" align="end" />
        </div>
      </Specimen>
      <Specimen name="GuideDialog" usage={k("u.guide")} stage="stretch">
        <div className="flex items-center justify-between rounded-full bg-white/[0.04] px-3 py-2">
          <span className="text-sm text-foreground/80">{k("s.guideRow")}</span>
          <GuideDialog title={k("s.guideTitle")}>
            <div>
              <h3 className="text-sm font-bold text-foreground">{k("s.guideStep")}</h3>
              <p className="mt-2">{k("s.guideStepText")}</p>
              <div className="mt-3">
                <CopyableValue
                  label={k("s.guideValue")}
                  value="https://shop.example.com/oauth2/callback/github"
                />
              </div>
              <p className="mt-2 text-[12px] text-muted-foreground">{k("s.guideNote")}</p>
            </div>
          </GuideDialog>
        </div>
      </Specimen>
      <Specimen name='Tooltip side="…"' usage={k("u.tooltip")} wide>
        <div className="flex flex-wrap items-center justify-center gap-6 px-24 py-8">
          {TOOLTIP_SIDES.map((side) => (
            <div key={side} className="flex flex-col items-center gap-1.5">
              <IconButton size="9" tone="glass" className="group relative">
                <Settings className="size-4" />
                <Tooltip text={k("s.tooltipSide", { side })} side={side} />
              </IconButton>
              <span className="font-mono text-[11px] text-muted-foreground">{side}</span>
            </div>
          ))}
          <IconButton size="9" tone="glass" className="group relative">
            <Trash2 className="size-4" />
            <Tooltip text={k("s.tooltipLong")} side="top" />
          </IconButton>
          <Badge tone="warning" tabIndex={0} className="group relative outline-none">
            {t("dialogs.beta")}
            <Tooltip text={k("s.tooltipBadge")} side="bottom" />
          </Badge>
        </div>
      </Specimen>
    </DebugSection>
  );
}

export function MenusSection() {
  const k = useKit();
  const items = (
    <>
      <button type="button" className={`${MENU_ITEM} bg-white/[0.07]`}>
        <Pencil className="size-4 shrink-0" />
        {k("s.edit")}
      </button>
      <button type="button" className={MENU_ITEM}>
        <Copy className="size-4 shrink-0" />
        {k("s.copy")}
      </button>
    </>
  );

  return (
    <DebugSection id="menus">
      <Specimen name="ActionMenu" usage={k("u.actionMenu")}>
        <ActionMenu
          items={[
            { label: k("s.edit"), icon: Pencil, onClick: noop },
            { label: k("s.copy"), icon: Copy, onClick: noop },
            { label: k("s.delete"), icon: Trash2, onClick: noop, variant: "danger", separatorBefore: true },
          ]}
        />
      </Specimen>
      <Specimen name="ActionMenu trigger" usage={k("u.actionMenuTrigger")}>
        <ActionMenu
          trigger={{ label: k("s.share"), icon: Forward }}
          items={[
            { label: k("s.copyBotLink"), icon: Copy, onClick: noop },
            { label: k("s.copyWebLink"), icon: Copy, onClick: noop, disabled: true, hint: k("s.webUnavailable") },
            { label: k("s.qrBot"), icon: Download, onClick: noop, separatorBefore: true },
            { label: k("s.qrWeb"), icon: Download, onClick: noop, disabled: true, hint: k("s.webUnavailable") },
          ]}
        />
      </Specimen>
      <Specimen name="POPOVER_CLASS · p-1.5 · p-3 · solid" usage={k("u.popover")}>
        <div className={`${POPOVER_CLASS} w-44 p-1.5`}>{items}</div>
        <div className={`${POPOVER_CLASS} w-44 p-3 text-[12.5px] text-muted-foreground`}>{k("s.body")}</div>
        <div className="w-44 rounded-popover border border-white/[0.14] bg-popover p-1.5">{items}</div>
      </Specimen>
    </DebugSection>
  );
}

export function StatesSection() {
  const k = useKit();
  const [isOpen, setIsOpen] = useState(false);

  return (
    <DebugSection id="states">
      <Specimen name='Spinner size="card"' usage={k("u.spinner")} stage="stretch">
        <Spinner size="card" />
      </Specimen>
      <Specimen name="Collapse" usage={k("u.collapse")} stage="stretch">
        <Button variant="outline" className="w-fit" onClick={() => setIsOpen((value) => !value)}>
          {isOpen ? k("s.hide") : k("s.show")}
        </Button>
        <Collapse open={isOpen}>
          <p className="rounded-xl bg-white/[0.04] p-3 text-[13px] text-foreground/80">{k("s.collapseText")}</p>
        </Collapse>
      </Specimen>
      <Specimen name='EmptyState size="page | card" · icon' usage={k("u.empty")} stage="stretch" wide>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-dashed border-white/[0.12]">
            <EmptyState text={k("s.emptyPage")} size="page" />
          </div>
          <div className="rounded-xl border border-dashed border-white/[0.12]">
            <EmptyState text={k("s.emptyCard")} size="card" />
          </div>
          <div className="rounded-xl border border-dashed border-white/[0.12]">
            <EmptyState text={k("s.emptySearch")} icon={SearchX} size="card" />
          </div>
        </div>
      </Specimen>
      <Specimen name="BrandLogo · BrandIcons" usage={k("u.brand")} wide>
        <BrandLogo className="h-8 w-auto" />
        <span className="mx-3 h-6 w-px bg-border" />
        <GithubIcon className="size-5 text-foreground" />
        <TelegramIcon className="size-5 text-foreground" />
      </Specimen>
    </DebugSection>
  );
}
