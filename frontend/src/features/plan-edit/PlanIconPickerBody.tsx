import { X } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listEmojiPacks } from "@entities/emoji-packs/api";
import { PackTab } from "@entities/emoji-packs/EmojiPicker";
import { PremiumEmoji } from "@entities/emoji-packs/PremiumEmoji";
import { NO_PLAN_ICON, type PlanIconValue } from "@entities/plans/api";
import { usePermissions } from "@entities/user/use-current-user";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { useHorizontalWheelScroll } from "@shared/lib/use-horizontal-wheel-scroll";
import { POPOVER_SCROLL_CLASS } from "@shared/ui/classes";
import { EmptyState, ErrorState } from "@shared/ui/glass/EmptyState";
import { Pressable } from "@shared/ui/Pressable";
import { Spinner } from "@shared/ui/Spinner";

const CELL_CLASS =
  "flex h-8 w-full min-w-0 cursor-pointer items-center justify-center overflow-hidden rounded-lg transition-colors hover:bg-white/[0.07]";

/** Lazy: emoji artwork brings lottie, which the dashboard's main bundle shouldn't carry for a closed popover. */
export function PlanIconPickerBody({ value, onChange }: { value: PlanIconValue; onChange: (value: PlanIconValue) => void }) {
  const { t } = useTranslation();
  const canViewPacks = usePermissions().includes("EMOJI_PACKS_VIEW");
  const [packsState] = useAsyncResource((signal) =>
    canViewPacks ? listEmojiPacks(signal) : Promise.resolve([]),
  );
  const packs = packsState.kind === "ready" ? packsState.data : [];
  const [activeTab, setActiveTab] = useState<string | null>(null);
  const activePack = packs.find((pack) => pack.set_name === activeTab) ?? packs[0];
  const tabsRef = useHorizontalWheelScroll<HTMLDivElement>();

  return (
    <>
      {packsState.kind === "loading" && <Spinner size="card" />}
      {packsState.kind === "error" && <ErrorState text={t("common.loadError")} />}
      {packsState.kind === "ready" && !activePack && <EmptyState text={t("plans.edit.iconNoPacks")} />}

      {activePack && (
        <nav className="glass-well mb-2 flex max-w-full rounded-full p-1">
          <div ref={tabsRef} className="no-scrollbar flex min-w-0 gap-1 overflow-x-auto rounded-full">
            {packs.map((pack) => (
              <PackTab
                key={pack.set_name}
                isActive={activePack?.set_name === pack.set_name}
                glyph={<PremiumEmoji item={pack.items[0]} size={20} />}
                onSelect={() => setActiveTab(pack.set_name)}
              />
            ))}
          </div>
        </nav>
      )}

      {activePack && (
        <div className={`max-h-64 ${POPOVER_SCROLL_CLASS}`}>
          <div className="grid grid-cols-8 gap-1">
            {activePack.items.map((item) => (
              <Pressable
                key={item.custom_emoji_id}
                type="button"
                onClick={() =>
                  onChange({ icon_emoji_id: item.custom_emoji_id, icon_emoji_fallback: item.fallback_emoji })
                }
                className={CELL_CLASS}
              >
                <PremiumEmoji item={item} size={22} />
              </Pressable>
            ))}
          </div>
        </div>
      )}

      {value.icon_emoji_id && (
        <Pressable
          type="button"
          onClick={() => onChange(NO_PLAN_ICON)}
          className="mt-1 flex h-[34px] w-full cursor-pointer items-center justify-center gap-1.5 rounded-full border border-glass-border text-xs text-foreground/70 transition-colors hover:bg-white/[0.06]"
        >
          <X className="size-3" />
          {t("plans.edit.iconClear")}
        </Pressable>
      )}
    </>
  );
}
