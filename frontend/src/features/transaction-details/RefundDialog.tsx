import type { ParseKeys } from "i18next";
import { Undo2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { RefundPreview, TransactionItem } from "@entities/transactions/api";
import { Modal } from "@shared/ui/Modal";
import { useModalClose } from "@shared/ui/modal-hooks";
import { Button } from "@shared/ui/Button";
import { DialogHeader } from "@shared/ui/DialogHeader";
import { Switch } from "@shared/ui/Switch";

interface RefundDialogProps {
  order: TransactionItem;
  preview: RefundPreview;
  onConfirm: (rollbackSubscription: boolean) => void;
  onCancel: () => void;
}

export function RefundDialog(props: RefundDialogProps) {
  return (
    <Modal onClose={props.onCancel} size="sm">
      <RefundDialogBody {...props} />
    </Modal>
  );
}

function RefundDialogBody({ order, preview, onConfirm }: RefundDialogProps) {
  const { t } = useTranslation();
  const close = useModalClose();
  const [rollbackOn, setRollbackOn] = useState(false);
  const { rollback } = preview;
  const hint = "text-[12.5px] text-muted-foreground";

  return (
    <>
      <DialogHeader icon={Undo2} tone="danger" title={t("transactions.refund.title")} />

      <div className="flex flex-col gap-3 px-5 pt-4 text-[13px] text-foreground/80">
        {!preview.refundable ? (
          <p>{t(`transactions.refund.notRefundable.${preview.reason}` as ParseKeys)}</p>
        ) : (
          <>
            <p>{t("transactions.refund.amount", { amount: Math.ceil(Number(order.final_price)) })}</p>
            {rollback && (
              <>
                <div className="flex items-center justify-between gap-3">
                  <span>{t("transactions.refund.rollbackLabel")}</span>
                  <Switch checked={rollbackOn} onChange={setRollbackOn} disabled={!rollback.available} />
                </div>
                {!rollback.available && rollback.blocked_reason && (
                  <p className={hint}>{t(`transactions.refund.blocked.${rollback.blocked_reason}` as ParseKeys)}</p>
                )}
                {rollback.available && (
                  <>
                    <p className={hint}>
                      {t(`transactions.refund.rollback.${order.purchase_type}`, { days: order.duration_days })}
                    </p>
                    {order.purchase_type === "CHANGE" && (
                      <p className={hint}>{t("transactions.refund.changeLosesCredits")}</p>
                    )}
                    {rollback.old_term_expired && <p className={hint}>{t("transactions.refund.oldTermExpired")}</p>}
                  </>
                )}
              </>
            )}
          </>
        )}
      </div>

      <div className="flex gap-2 px-5 pb-5 pt-4">
        <Button variant="outline" className="flex-1" type="button" onClick={close}>
          {t("common.cancel")}
        </Button>
        {preview.refundable && (
          <Button variant="danger" className="flex-1" onClick={() => onConfirm(rollbackOn)}>
            {t("transactions.refund.confirm")}
          </Button>
        )}
      </div>
    </>
  );
}
