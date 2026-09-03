from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    MAIN = State()
    DEVICES = State()
    DEVICE_CONFIRM_DELETE = State()
    DEVICE_CONFIRM_DELETE_ALL = State()
    DEVICE_CONFIRM_REISSUE = State()


class Subscription(StatesGroup):
    MAIN = State()
    PROMOCODE = State()
    PROMOCODE_TARGET = State()
    PROMOCODE_CONFIRM = State()
