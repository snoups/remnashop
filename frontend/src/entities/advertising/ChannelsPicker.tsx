import { useTranslation } from "react-i18next";

import { SegmentedPills } from "@shared/ui/SegmentedPills";

export interface AdLinkChannels {
  allow_bot: boolean;
  allow_webcabinet: boolean;
}

type ChannelsKey = "all" | "bot" | "web";

const CHANNELS: Record<ChannelsKey, AdLinkChannels> = {
  all: { allow_bot: true, allow_webcabinet: true },
  bot: { allow_bot: true, allow_webcabinet: false },
  web: { allow_bot: false, allow_webcabinet: true },
};

export function ChannelsPicker({ value, onChange }: { value: AdLinkChannels; onChange: (value: AdLinkChannels) => void }) {
  const { t } = useTranslation();
  const key: ChannelsKey = value.allow_bot ? (value.allow_webcabinet ? "all" : "bot") : "web";

  return (
    <SegmentedPills
      value={key}
      onChange={(next) => onChange(CHANNELS[next])}
      ariaLabel={t("advertising.channels.label")}
      stretch
      options={[
        { value: "all", label: t("advertising.channels.all") },
        { value: "bot", label: t("advertising.channel.BOT") },
        { value: "web", label: t("advertising.channels.web") },
      ]}
    />
  );
}
