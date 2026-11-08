import { X } from "lucide-react";
import { motion } from "motion/react";
import { useRef } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { NavLink } from "react-router-dom";

import { BrandMark } from "@entities/appearance/BrandMark";
import { useBrandName } from "@entities/appearance/use-appearance";
import { usePermissions } from "@entities/user/use-current-user";
import { IconButton } from "@shared/ui/IconButton";
import { useDialogFocus } from "@shared/ui/modal-hooks";
import { BuildInfoBadge } from "@widgets/build-info/BuildInfoBadge";
import { DonateButton } from "@widgets/build-info/DonateButton";
import { LanguagePicker } from "@widgets/language-picker/LanguagePicker";
import { isNavItemVisible, NAV_ITEMS } from "./nav-items";

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
        initial={{ x: "-100%" }}
        animate={{ x: 0 }}
        exit={{ x: "-100%", transition: { duration: 0.2, ease: "easeIn" } }}
        transition={{ type: "spring", stiffness: 400, damping: 36 }}
        className="relative flex h-dvh w-[min(320px,85vw)] flex-col border-r border-glass-border bg-surface/50 pt-[env(safe-area-inset-top)] text-foreground shadow-[0_24px_48px_-20px_rgba(4,8,20,0.6),inset_-1px_0_0_rgba(232,236,251,0.08)] outline-none backdrop-blur-[28px] backdrop-saturate-150"
      >
        <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-border px-4">
          <BrandMark className="size-7 shrink-0 text-primary" />
          <span className="min-w-0 flex-1 truncate text-base font-bold">{brandName}</span>
          <IconButton size="9" onClick={onClose}><X className="size-5" /></IconButton>
        </div>
        <nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto overscroll-contain p-3">
          {NAV_ITEMS.filter((item) => isNavItemVisible(item, permissions)).map(({ key, to, end, icon: Icon }) => (
            <NavLink
              key={key}
              to={to}
              end={end}
              onClick={onClose}
              className={({ isActive }) => `flex min-h-11 shrink-0 items-center gap-3 rounded-full px-4 text-sm font-medium ${isActive ? "bg-accent text-primary" : "text-muted-foreground hover:bg-white/[0.06] hover:text-foreground"}`}
            >
              <Icon className="size-5 shrink-0" />
              {t(`sidebar.${key}`)}
            </NavLink>
          ))}
        </nav>
        <div className="flex shrink-0 items-center gap-3 border-t border-border px-3 pt-3 pb-[max(12px,env(safe-area-inset-bottom))]">
          <BuildInfoBadge mobile />
          <DonateButton mobile />
          <LanguagePicker iconOnly />
        </div>
      </motion.div>
    </div>,
    document.body,
  );
}
