from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.users.dto import UserDto
from app.modules.users.ports import PromocodeLiveness


class GetCurrentUserUseCase(UseCase[None, UserDto, UserDto]):
    # reading one's own profile is every user's right
    required_permission = Permission.PUBLIC

    def __init__(self, promocode_liveness: PromocodeLiveness, uow: UnitOfWork) -> None:
        self._promocode_liveness = promocode_liveness
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> UserDto:
        # Show what checkout would charge: a discount from an ended promocode stays
        # in the row until the next checkout drops it. Read-only, nothing is cleared.
        personal, purchase = actor.personal_discount, actor.purchase_discount
        if actor.personal_discount_promocode_id is not None or (
            actor.purchase_discount_promocode_id is not None
        ):
            async with self._uow:
                if actor.personal_discount_promocode_id is not None and not (
                    await self._promocode_liveness.is_live(actor.personal_discount_promocode_id)
                ):
                    personal = 0
                if actor.purchase_discount_promocode_id is not None and not (
                    await self._promocode_liveness.is_live(actor.purchase_discount_promocode_id)
                ):
                    purchase = 0
        return actor.model_copy(
            update={"personal_discount": personal, "purchase_discount": purchase}
        )
