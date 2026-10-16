from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.modules.broadcasts.dispatch import (
    DeliverBroadcastDispatch,
    DeliverBroadcastEmailDispatch,
    RecallBroadcastDispatch,
    StartBroadcastDispatch,
)
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.tasks import (
    deliver_broadcast_email_task,
    deliver_broadcast_task,
    recall_broadcast_task,
    start_broadcast_task,
)
from app.modules.broadcasts.telegram_api import TelegramClientFactory
from app.modules.broadcasts.usecases import (
    AddBroadcastEmailImageUseCase,
    CancelBroadcastUseCase,
    CreateBroadcastUseCase,
    DeleteBroadcastMediaUseCase,
    DeleteBroadcastUseCase,
    DeliverBroadcastBatchUseCase,
    DeliverBroadcastEmailBatchUseCase,
    GetBroadcastEmailImageUseCase,
    GetBroadcastPromocodeUseCase,
    GetBroadcastSummaryUseCase,
    GetBroadcastUseCase,
    ListBroadcastRecipientsUseCase,
    ListBroadcastsUseCase,
    PreviewBroadcastAudienceUseCase,
    PreviewBroadcastEmailUseCase,
    PruneBroadcastRecipientsUseCase,
    RecallBroadcastBatchUseCase,
    RecallBroadcastUseCase,
    RetryBroadcastUseCase,
    SendBroadcastUseCase,
    SendTestBroadcastEmailUseCase,
    SendTestBroadcastUseCase,
    SetBroadcastMediaUseCase,
    StartBroadcastUseCase,
    TickBroadcastsUseCase,
    UpdateBroadcastUseCase,
)


class BroadcastsProvider(Provider):
    scope = Scope.REQUEST

    broadcast_repository = provide(BroadcastRepository)
    telegram_client_factory = provide(TelegramClientFactory, scope=Scope.APP)
    use_cases = provide_all(
        CreateBroadcastUseCase,
        UpdateBroadcastUseCase,
        DeleteBroadcastUseCase,
        GetBroadcastUseCase,
        GetBroadcastPromocodeUseCase,
        GetBroadcastSummaryUseCase,
        ListBroadcastsUseCase,
        ListBroadcastRecipientsUseCase,
        SetBroadcastMediaUseCase,
        DeleteBroadcastMediaUseCase,
        AddBroadcastEmailImageUseCase,
        GetBroadcastEmailImageUseCase,
        PreviewBroadcastAudienceUseCase,
        SendBroadcastUseCase,
        CancelBroadcastUseCase,
        RetryBroadcastUseCase,
        RecallBroadcastUseCase,
        SendTestBroadcastUseCase,
        SendTestBroadcastEmailUseCase,
        PreviewBroadcastEmailUseCase,
        StartBroadcastUseCase,
        DeliverBroadcastBatchUseCase,
        DeliverBroadcastEmailBatchUseCase,
        RecallBroadcastBatchUseCase,
        TickBroadcastsUseCase,
        PruneBroadcastRecipientsUseCase,
    )

    @provide(scope=Scope.APP)
    def start_broadcast_dispatch(self) -> StartBroadcastDispatch:
        return cast(StartBroadcastDispatch, start_broadcast_task)

    @provide(scope=Scope.APP)
    def deliver_broadcast_dispatch(self) -> DeliverBroadcastDispatch:
        return cast(DeliverBroadcastDispatch, deliver_broadcast_task)

    @provide(scope=Scope.APP)
    def deliver_broadcast_email_dispatch(self) -> DeliverBroadcastEmailDispatch:
        return cast(DeliverBroadcastEmailDispatch, deliver_broadcast_email_task)

    @provide(scope=Scope.APP)
    def recall_broadcast_dispatch(self) -> RecallBroadcastDispatch:
        return cast(RecallBroadcastDispatch, recall_broadcast_task)


def get_broadcasts_providers() -> list[Provider]:
    return [BroadcastsProvider()]
