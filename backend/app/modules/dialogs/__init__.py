from app.modules.dialogs import catalog
from app.modules.dialogs.di import get_dialogs_providers
from app.modules.dialogs.dto import DialogButtonDto, DialogWindowDto
from app.modules.dialogs.flows import register_all_flow_metadata
from app.modules.dialogs.repository import DialogRepository
from app.modules.dialogs.seed import ensure_dialogs_seeded

__all__ = [
    "DialogButtonDto",
    "DialogRepository",
    "DialogWindowDto",
    "catalog",
    "ensure_dialogs_seeded",
    "get_dialogs_providers",
    "register_all_flow_metadata",
]
