import { Copy, Download, Forward } from "lucide-react";
import { useTranslation } from "react-i18next";

import { type AdLink, type AdLinkChannel, fetchAdLinkQr, getAdLinkShareUrls } from "@entities/advertising/api";
import { copyToClipboard } from "@shared/lib/clipboard";
import { useAsyncResource } from "@shared/lib/use-async-resource";
import { toast } from "@shared/lib/toast";
import { ActionMenu, type ActionMenuItem } from "@shared/ui/ActionMenu";

const UNAVAILABLE_HINT_KEYS: Record<AdLinkChannel, string> = {
  BOT: "advertising.share.botUnavailable",
  WEBCABINET: "advertising.share.webUnavailable",
};

// Remount (key) when the link's channels change: the URLs are fetched once.
export function AdLinkShareMenu({ adLink }: { adLink: AdLink }) {
  const { t } = useTranslation();
  // prefetched: clipboard writes must stay inside the click, with no request in between
  const [state] = useAsyncResource((signal) => getAdLinkShareUrls(adLink.id, signal));

  const channels: AdLinkChannel[] = [
    ...(adLink.allow_bot ? (["BOT"] as const) : []),
    ...(adLink.allow_webcabinet ? (["WEBCABINET"] as const) : []),
  ];

  const urlFor = (channel: AdLinkChannel) =>
    state.kind === "ready" ? (channel === "BOT" ? state.data.bot_url : state.data.webcabinet_url) : null;
  const hintFor = (channel: AdLinkChannel) => {
    if (state.kind === "loading") return undefined;
    if (state.kind === "error") return t("advertising.share.loadError");
    return urlFor(channel) ? undefined : t(UNAVAILABLE_HINT_KEYS[channel]);
  };

  const copy = (url: string) => {
    void copyToClipboard(url).then((copied) => {
      if (copied) toast.success(t("app.copied"));
    });
  };

  const downloadQr = async (channel: AdLinkChannel) => {
    try {
      const blobUrl = URL.createObjectURL(await fetchAdLinkQr(adLink.id, channel));
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = `${adLink.code}-${channel.toLowerCase()}-qr.png`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(blobUrl);
    } catch {
      toast.error(t("advertising.share.qrError"));
    }
  };

  const itemsFor = (kind: "copy" | "qr"): ActionMenuItem[] =>
    channels.map((channel, index) => {
      const url = urlFor(channel);
      return {
        label: t(`advertising.share.${kind}.${channel}`),
        icon: kind === "copy" ? Copy : Download,
        onClick: () => {
          if (!url) return;
          if (kind === "copy") copy(url);
          else void downloadQr(channel);
        },
        disabled: !url,
        hint: hintFor(channel),
        separatorBefore: kind === "qr" && index === 0,
      };
    });

  return (
    <ActionMenu
      trigger={{ label: t("advertising.share.button"), icon: Forward }}
      items={[...itemsFor("copy"), ...itemsFor("qr")]}
    />
  );
}
