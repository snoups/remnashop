import { Bot, Globe } from "lucide-react";

import { ToggleCapsule } from "@shared/ui/glass/ToggleCapsule";

export interface AdLinkChannels {
  allow_bot: boolean;
  allow_webcabinet: boolean;
}

/** Bot and web cabinet as two switches, icons only (half a form row is too narrow for the words);
 *  the last one on can't be switched off. */
export function ChannelsPicker({ value, onChange }: { value: AdLinkChannels; onChange: (value: AdLinkChannels) => void }) {
  return (
    <div className="flex gap-2">
      <ToggleCapsule
        icon={Bot}
        checked={value.allow_bot}
        disabled={value.allow_bot && !value.allow_webcabinet}
        onChange={(allow_bot) => onChange({ ...value, allow_bot })}
      />
      <ToggleCapsule
        icon={Globe}
        checked={value.allow_webcabinet}
        disabled={value.allow_webcabinet && !value.allow_bot}
        onChange={(allow_webcabinet) => onChange({ ...value, allow_webcabinet })}
      />
    </div>
  );
}
