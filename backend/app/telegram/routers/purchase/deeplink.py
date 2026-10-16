from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from app.core.constants import PLAN_START_PREFIX
from app.core.enums import PurchaseType
from app.telegram.routers.purchase.handlers import PLAN_CODE_KEY
from app.telegram.states import Purchase

router = Router(name=__name__)


@router.message(
    CommandStart(deep_link=True, magic=F.args.regexp(rf"^{PLAN_START_PREFIX}[A-Za-z0-9_-]+$"))
)
async def on_plan_link(
    message: Message, command: CommandObject, dialog_manager: DialogManager
) -> None:
    code = (command.args or "").removeprefix(PLAN_START_PREFIX)
    await dialog_manager.start(
        Purchase.PLAN,
        data={"purchase_type": PurchaseType.NEW.value, PLAN_CODE_KEY: code},
        mode=StartMode.RESET_STACK,
    )
