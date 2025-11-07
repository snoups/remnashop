from typing import Optional

from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    MAIN = State()
    DEVICES = State()
    INVITE = State()
    INVITED_USERS = State()


class Notification(StatesGroup):
    CLOSE = State()


class Subscription(StatesGroup):
    MAIN = State()
    PROMOCODE = State()
    PLANS = State()
    DURATION = State()
    PAYMENT_METHOD = State()
    CONFIRM = State()
    SUCCESS = State()
    FAILED = State()
    TRIAL = State()


class Dashboard(StatesGroup):
    MAIN = State()


class DashboardStatistics(StatesGroup):
    MAIN = State()


class DashboardBroadcast(StatesGroup):
    MAIN = State()
    LIST = State()
    VIEW = State()
    PLAN = State()
    SEND = State()
    CONTENT = State()
    BUTTONS = State()


class DashboardPromocodes(StatesGroup):
    MAIN = State()
    LIST = State()
    CONFIGURATOR = State()
    CODE = State()
    TYPE = State()
    AVAILABILITY = State()
    REWARD = State()
    LIFETIME = State()
    ALLOWED = State()


class DashboardAccess(StatesGroup):
    MAIN = State()
    CONDITIONS = State()
    RULES = State()
    CHANNEL = State()


class DashboardUsers(StatesGroup):
    MAIN = State()
    SEARCH = State()
    SEARCH_RESULTS = State()
    RECENT_REGISTERED = State()
    RECENT_ACTIVITY = State()
    BLACKLIST = State()


class DashboardUser(StatesGroup):
    MAIN = State()
    SUBSCRIPTION = State()
    TRAFFIC_LIMIT = State()
    DEVICE_LIMIT = State()
    EXPIRE_TIME = State()
    SQUADS = State()
    DEVICES_LIST = State()
    DISCOUNT = State()
    STATISTICS = State()
    ROLE = State()
    TRANSACTIONS_LIST = State()
    TRANSACTION = State()
    GIVE_ACCESS = State()
    MESSAGE = State()


class DashboardRemnashop(StatesGroup):
    MAIN = State()
    ADMINS = State()
    REFERRAL = State()
    ADVERTISING = State()


class RemnashopGateways(StatesGroup):
    MAIN = State()
    SETTINGS = State()
    FIELD = State()
    CURRENCY = State()


class RemnashopNotifications(StatesGroup):
    MAIN = State()
    USER = State()
    SYSTEM = State()


class RemnashopPlans(StatesGroup):
    MAIN = State()
    CONFIGURATOR = State()
    NAME = State()
    TYPE = State()
    AVAILABILITY = State()
    TRAFFIC = State()
    DEVICES = State()
    DURATIONS = State()
    DURATION_ADD = State()
    PRICES = State()
    PRICE = State()
    ALLOWED = State()
    SQUADS = State()


class DashboardRemnawave(StatesGroup):
    MAIN = State()
    USERS = State()
    HOSTS = State()
    NODES = State()
    INBOUNDS = State()


class DashboardImporter(StatesGroup):
    MAIN = State()
    FROM_XUI = State()
    SYNC = State()
    SQUADS = State()
    IMPORT_COMPLETED = State()
    SYNC_COMPLETED = State()


def state_from_string(state_str: str, sep: Optional[str] = ":") -> Optional[State]:
    try:
        group_name, state_name = state_str.split(":")[:2]
        group_cls = globals().get(group_name)
        if group_cls is None:
            return None
        state_obj = getattr(group_cls, state_name, None)
        if not isinstance(state_obj, State):
            return None
        return state_obj
    except (ValueError, AttributeError):
        return None
