from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    MAIN = State()


class Subscriptions(StatesGroup):
    LIST = State()
    CARD = State()
    RECURRING_TERMS = State()
    DEVICES = State()
    DEVICE_CONFIRM_DELETE = State()
    DEVICE_CONFIRM_DELETE_ALL = State()
    DEVICE_CONFIRM_REISSUE = State()


class Purchase(StatesGroup):
    PLAN = State()
    DURATION = State()
    METHOD = State()
    EMAIL = State()
    CONFIRM = State()
    RECURRING_TERMS = State()
    PAY = State()
    LINK_CHOICE = State()


class PaymentResult(StatesGroup):
    SUCCESS = State()
    FAILED = State()
    CANCELED = State()


class Promocode(StatesGroup):
    INPUT = State()
    TARGET = State()
    CONFIRM = State()


class Referrals(StatesGroup):
    MAIN = State()
    REDEEM_TARGET = State()
    ABOUT = State()
