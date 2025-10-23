from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    MAIN = State()


class Notification(StatesGroup):
    CLOSE = State()


class Connect(StatesGroup):
    MAIN = State()


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
    STATISTICS = State()


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
    CREATE = State()
    DELETE = State()
    EDIT = State()


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
    UNBLOCK_ALL = State()


class DashboardUser(StatesGroup):
    MAIN = State()
    STATISTICS = State()
    ROLE = State()
    SUBSCRIPTION = State()
    TRANSACTIONS = State()


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
    STATISTICS = State()

    PLAN = State()
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
