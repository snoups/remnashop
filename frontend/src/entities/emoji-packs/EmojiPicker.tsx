import { Plus, Smile, X } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { listEmojiPacks } from "@entities/emoji-packs/api";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { TAP_PILL_SCALE } from "@shared/lib/bounceState";
import { scrollToEmojiPacks } from "@shared/lib/emoji-packs-anchor";
import { useClickOutside } from "@shared/lib/use-click-outside";
import { useCloseOnScroll } from "@shared/lib/use-close-on-scroll";
import { useHorizontalWheelScroll } from "@shared/lib/use-horizontal-wheel-scroll";
import { PremiumEmoji } from "@entities/emoji-packs/PremiumEmoji";
import { STANDARD_EMOJI } from "@shared/ui/standard-emoji";
import { IconButton } from "@shared/ui/IconButton";
import { PortalPopover } from "@shared/ui/PortalPopover";

/** A standard emoji is a glyph the bot puts in the button's own label; a premium
 * one is an id Telegram renders itself, and only for a bot whose owner has
 * Premium. Exactly one of the two is ever set. */
export type PickedEmoji = { glyph: string } | { customEmojiId: string; fallback: string };

interface EmojiPickerProps {
  /** What the trigger shows: the chosen emoji, or null for none. */
  current: ReactNode;
  disabled?: boolean;
  onPick: (picked: PickedEmoji) => void;
  onClear: () => void;
}

const POPOVER_MAX_HEIGHT = 360;
const POPOVER_MOTION = {
  initial: { opacity: 0, scale: 0.96, y: -4 },
  animate: { opacity: 1, scale: 1, y: 0 },
  exit: { opacity: 0, scale: 0.96, y: -4 },
  transition: { duration: 0.15, ease: "easeOut" },
} as const;

export function PackTab({
  isActive,
  glyph,
  onSelect,
}: {
  isActive: boolean;
  glyph: ReactNode;
  onSelect: () => void;
}) {
  return (
    <motion.button
      type="button"
      onClick={onSelect}
      initial="rest"
      whileTap="tap"
      className="group relative isolate block shrink-0 cursor-pointer rounded-full"
    >
      <motion.span
        variants={{ rest: { scale: 1 }, tap: { scale: TAP_PILL_SCALE } }}
        className={`absolute inset-0 rounded-full transition-colors ${
          isActive ? "bg-accent" : "group-hover:bg-white/[0.06]"
        }`}
      />
      <span
        className={`relative z-10 flex h-[26px] items-center justify-center px-3.5 ${
          isActive ? "text-primary" : "text-muted-foreground"
        }`}
      >
        {glyph}
      </span>
    </motion.button>
  );
}

export function EmojiPicker({
  current,
  disabled = false,
  onPick,
  onClear,
}: EmojiPickerProps) {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState("standard");
  const ref = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | undefined>(undefined);
  const tabsRef = useHorizontalWheelScroll<HTMLDivElement>();
  const [packsState] = useAsyncResource(listEmojiPacks);
  const packs = packsState.kind === "ready" ? packsState.data : [];

  useClickOutside([ref, popoverRef], isOpen, () => setIsOpen(false));
  useCloseOnScroll(isOpen, popoverRef, () => setIsOpen(false));

  const activePack = packs.find((pack) => pack.set_name === activeTab);

  const open = () => {
    setActiveTab("standard");
    setIsOpen(true);
  };

  // The popover is portalled, so the gap between trigger and popover is not a
  // DOM ancestor of either -- a delay is what lets the pointer cross it.
  const closeSoon = () => {
    closeTimer.current = window.setTimeout(() => setIsOpen(false), 200);
  };
  const cancelClose = () => {
    if (closeTimer.current !== undefined) window.clearTimeout(closeTimer.current);
  };

  const pick = (picked: PickedEmoji) => {
    onPick(picked);
    setIsOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        // hover-to-open is for a mouse only: a tap fires an emulated enter right
        // before the click, which would open and then toggle the picker shut
        onPointerEnter={(event) => {
          if (disabled || event.pointerType !== "mouse") return;
          cancelClose();
          open();
        }}
        onPointerLeave={(event) => event.pointerType === "mouse" && closeSoon()}
        onClick={() => (isOpen ? setIsOpen(false) : open())}
        className="flex size-[26px] cursor-pointer items-center justify-center rounded-full text-[16px] disabled:cursor-not-allowed disabled:opacity-40"
      >
        {current ?? <Smile className="size-[18px] text-muted-foreground" />}
      </button>

      <PortalPopover
        open={isOpen}
        triggerRef={triggerRef}
        popoverRef={popoverRef}
        align="right"
        maxHeight={POPOVER_MAX_HEIGHT}
        onMouseEnter={cancelClose}
        onMouseLeave={closeSoon}
        {...POPOVER_MOTION}
        // a blur over animating emoji re-renders every frame: measured 60% -> 40% GPU without it
        solid
        className="w-72 p-1.5"
>
        {/* TabBar's capsule, scaled down for the popover: the scroller is
            inset by the capsule's own p-1, so its clip box lines up with
            the outer radius instead of cutting into a pill. */}
        <nav className="mb-2 flex max-w-full rounded-full border border-glass-border bg-white/[0.03] p-1 backdrop-blur-md">
          <div
            ref={tabsRef}
            className="no-scrollbar flex min-w-0 gap-1 overflow-x-auto rounded-full"
          >
            <PackTab
              isActive={activeTab === "standard"}
              glyph={<Smile className="size-[18px]" />}
              onSelect={() => setActiveTab("standard")}
            />
            {packs.map((pack) => (
              <PackTab
                key={pack.set_name}
                isActive={activeTab === pack.set_name}
                glyph={<PremiumEmoji item={pack.items[0]} size={20} />}
                onSelect={() => setActiveTab(pack.set_name)}
              />
            ))}
          </div>
          <IconButton size="26px" className="ml-auto"
            onClick={() => {
              setIsOpen(false);
              scrollToEmojiPacks();
            }}
          >
            <Plus className="size-[18px]" />
          </IconButton>
        </nav>

        {/* x-hidden, not x-auto: a glyph the font renders wider than its
            cell would otherwise add a scrollbar to a grid that is already
            as wide as the popover. */}
        {/* py matches the fade: at either end of the scroll the gradient
            sits over padding, never over a row of emoji. */}
        <div className="max-h-56 overflow-y-auto overflow-x-hidden py-2 [mask-composite:add] [mask-image:linear-gradient(to_bottom,transparent,black_8px,black_calc(100%-8px),transparent),linear-gradient(to_right,transparent_calc(100%-14px),black_calc(100%-14px))]">
          {activePack ? (
            <div className="grid grid-cols-8 gap-1">
              {activePack.items.map((item) => (
                <button
                  key={item.custom_emoji_id}
                  type="button"
                  onClick={() =>
                    pick({
                      customEmojiId: item.custom_emoji_id,
                      fallback: item.fallback_emoji,
                    })
                  }
                  className="flex h-7 w-full min-w-0 cursor-pointer items-center justify-center overflow-hidden rounded-lg text-[17px] transition-colors hover:bg-white/[0.07]"
                >
                  <PremiumEmoji item={item} size={22} />
                </button>
              ))}
            </div>
          ) : (
            STANDARD_EMOJI.map((group) => (
              <div key={group.key} className="mb-2">
                <span className="mb-1 block text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t(`dialogs.inspector.emojiGroup.${group.key}`)}
                </span>
                <div className="grid grid-cols-8 gap-1">
                  {group.items.map((emoji) => (
                    <button
                      key={emoji.g}
                      type="button"
                      onClick={() => pick({ glyph: emoji.g })}
                      className="flex h-7 w-full min-w-0 cursor-pointer items-center justify-center overflow-hidden rounded-lg text-[17px] transition-colors hover:bg-white/[0.07]"
                    >
                      {emoji.g}
                    </button>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>

        {current !== null && (
          <button
            type="button"
            onClick={() => {
              onClear();
              setIsOpen(false);
            }}
            className="mt-1 flex h-[34px] w-full cursor-pointer items-center justify-center gap-1.5 rounded-full border border-border text-[11.5px] text-foreground/70 transition-colors hover:bg-white/[0.06]"
          >
            <X className="size-3" />
            {t("dialogs.inspector.emojiClear")}
          </button>
        )}
      </PortalPopover>
    </div>
  );
}
