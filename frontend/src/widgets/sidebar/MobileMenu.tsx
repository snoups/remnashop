import { X } from "lucide-react";
import { motion } from "motion/react";
import { useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useMatch, useResolvedPath } from "react-router-dom";

import { BrandMark } from "@entities/appearance/BrandMark";
import { useBrandName } from "@entities/appearance/use-appearance";
import { usePermissions } from "@entities/user/use-current-user";
import { IconButton } from "@shared/ui/IconButton";
import { useDialogFocus } from "@shared/ui/modal-hooks";
import { Pressable } from "@shared/ui/Pressable";
import { BuildInfoBadge } from "@widgets/build-info/BuildInfoBadge";
import { DonateButton } from "@widgets/build-info/DonateButton";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";
import { isNavItemVisible, NAV_ITEMS } from "./nav-items";
import { MOBILE_NAV_ROW_CLASSNAME } from "./nav-pill";

export function MobileMenu({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const brandName = useBrandName();
  const permissions = usePermissions();
  const panelRef = useRef<HTMLDivElement>(null);
  useDialogFocus(panelRef, onClose);

  return createPortal(
    <div className="fixed inset-0 z-50 md:hidden">
      <motion.button
        type="button"
        tabIndex={-1}
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
        onClick={onClose}
      />
      <motion.div
        ref={panelRef}
        tabIndex={-1}
        initial={{ x: "-110%" }}
        animate={{ x: 0 }}
        exit={{ x: "-110%", transition: { duration: 0.2, ease: "easeIn" } }}
        transition={{ type: "spring", stiffness: 400, damping: 36 }}
        // a floating card 8px off the screen, as the header bar
        className="absolute bottom-[calc(8px+env(safe-area-inset-bottom))] left-2 top-[calc(8px+env(safe-area-inset-top))] flex w-[min(320px,85vw)] flex-col overflow-hidden rounded-card border border-glass-border bg-surface/50 text-foreground shadow-2xl outline-none backdrop-blur-[28px] backdrop-saturate-150"
      >
        <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-border pl-4 pr-3">
          <BrandMark className="size-8 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <span className="block truncate text-base font-bold leading-[22px] tracking-tight">{brandName}</span>
            <span className="block truncate text-xs font-medium leading-4 text-muted-foreground">{t("sidebar.tagline")}</span>
          </div>
          <IconButton size="9" tone="glass" onClick={onClose}><X className="size-4" /></IconButton>
        </div>
        <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto overscroll-contain p-3">
          {NAV_ITEMS.filter((item) => isNavItemVisible(item, permissions)).map(({ key, to, end, icon: Icon }) => (
            <MobileNavLink key={key} to={to} end={end} onClick={onClose}>
              <Icon className="size-4 shrink-0" />
              {t(`sidebar.${key}`)}
            </MobileNavLink>
          ))}
        </nav>
        <div className="flex shrink-0 flex-col gap-0.5 border-t border-border p-3">
          <LanguagePicker row />
          <BuildInfoBadge mobile />
          <DonateButton mobile />
        </div>
      </motion.div>
    </div>,
    document.body,
  );
}

function MobileNavLink({ to, end, onClick, children }: { to: string; end?: boolean; onClick: () => void; children: ReactNode }) {
  // NavLink's rule: the path itself, or below it unless `end`
  const isActive = useMatch({ path: useResolvedPath(to).pathname, end: end ?? false }) !== null;
  return (
    <Pressable
      as="link"
      to={to}
      onClick={onClick}
      className={isActive ? "flex min-h-11 shrink-0 items-center gap-2.5 rounded-full bg-accent px-3.5 text-sm font-semibold text-primary" : MOBILE_NAV_ROW_CLASSNAME}
    >
      {children}
    </Pressable>
  );
}
