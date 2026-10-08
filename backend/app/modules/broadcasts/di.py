from typing import cast

from dishka import Provider, Scope, provide, provide_all

from app.modules.broadcasts.dispatch import (
    DeliverBroadcastDispatch,
    RecallBroadcastDispatch,
    StartBroadcastDispatch,
)
from app.modules.broadcasts.repository import BroadcastRepository
from app.modules.broadcasts.tasks import (
    deliver_broadcast_task,
    recall_broadcast_task,
    start_broadcast_task,
)
from app.modules.broadcasts.telegram_api import TelegramClientFactory
from app.modules.broadcasts.usecases import (
    CancelBroadcastUseCase,
    CreateBroadcastUseCase,
    DeleteBroadcastMediaUseCase,
    DeleteBroadcastUseCase,
    DeliverBroadcastBatchUseCase,
    GetBroadcastPromocodeUseCase,
    GetBroadcastSummaryUseCase,
    GetBroadcastUseCase,
    ListBroadcastRecipientsUseCase,
    ListBroadcastsUseCase,
    PreviewBroadcastAudienceUseCase,
    PruneBroadcastRecipientsUseCase,
    RecallBroadcastBatchUseCase,
    RecallBroadcastUseCase,
    RetryBroadcastUseCase,
    SendBroadcastUseCase,
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
        PreviewBroadcastAudienceUseCase,
        SendBroadcastUseCase,
        CancelBroadcastUseCase,
        RetryBroadcastUseCase,
        RecallBroadcastUseCase,
        SendTestBroadcastUseCase,
        StartBroadcastUseCase,
        DeliverBroadcastBatchUseCase,
        RecallBroadcastBatchUseCase,
        TickBroadcastsUseCase,
        PruneBroadcastRecipientsUseCase,
    )

    @provide
    def start_broadcast_dispatch(self) -> StartBroadcastDispatch:
        return cast(StartBroadcastDispatch, start_broadcast_task)

    @provide
    def deliver_broadcast_dispatch(self) -> DeliverBroadcastDispatch:
        return cast(DeliverBroadcastDispatch, deliver_broadcast_task)

    @provide
    def recall_broadcast_dispatch(self) -> RecallBroadcastDispatch:
        return cast(RecallBroadcastDispatch, recall_broadcast_task)


def get_broadcasts_providers() -> list[Provider]:
    return [BroadcastsProvider()]
