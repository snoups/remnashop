import { useState } from "react";
import { useTranslation } from "react-i18next";

import { type AdLink, updateAdLink } from "@entities/advertising/api";
import type { AdLinkChannels } from "@entities/advertising/ChannelsPicker";
import { getErrorMessage } from "@shared/api/http";
import { toast } from "@shared/lib/toast";

// the dialog footer's save button submits this form via form=
export const AD_LINK_EDIT_FORM_ID = "adlink-edit-form";

export type AdLinkEditFormState = ReturnType<typeof useAdLinkEditForm>;

export function useAdLinkEditForm(adLink: AdLink, onSaved: (adLink: AdLink) => void) {
  const { t } = useTranslation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState(adLink.name);
  const [cost, setCost] = useState(adLink.cost);
  const [currency, setCurrency] = useState(adLink.cost_currency);
  const [revenueSharePercent, setRevenueSharePercent] = useState(adLink.revenue_share_percent);
  const [note, setNote] = useState(adLink.note ?? "");
  const [channels, setChannels] = useState<AdLinkChannels>({
    allow_bot: adLink.allow_bot,
    allow_webcabinet: adLink.allow_webcabinet,
  });

  const submit = async () => {
    setIsSubmitting(true);
    try {
      const updated = await updateAdLink(adLink.id, {
        name: name.trim(),
        cost,
        cost_currency: currency,
        revenue_share_percent: revenueSharePercent,
        ...channels,
        // "" clears it; null would leave the old note
        note: note.trim(),
      });
      toast.success(t("advertising.edit.saved"));
      onSaved(updated);
    } catch (err) {
      toast.error(getErrorMessage(err, t("advertising.edit.error")));
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    name,
    setName,
    cost,
    setCost,
    currency,
    setCurrency,
    revenueSharePercent,
    setRevenueSharePercent,
    note,
    setNote,
    channels,
    setChannels,
    isSubmitting,
    canSubmit: !isSubmitting,
    submit,
  };
}
