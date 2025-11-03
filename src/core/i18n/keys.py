from enum import StrEnum


class UtilKey(StrEnum):
    SPACE = "space"
    EMPTY = "empty"
    BUTTON = "btn-test"
    MESSAGE = "msg-test"
    DEVELOPMENT = "development"
    TEST_PAYMENT = "test-payment"
    UNLIMITED = "unlimited"
    UNKNOWN = "unknown"
    UNIT_UNLIMITED = "unit-unlimited"


class ByteUnitKey(StrEnum):
    BYTE = "unit-byte"
    KILOBYTE = "unit-kilobyte"
    MEGABYTE = "unit-megabyte"
    GIGABYTE = "unit-gigabyte"
    TERABYTE = "unit-terabyte"


class TimeUnitKey(StrEnum):
    SECOND = "unit-second"
    MINUTE = "unit-minute"
    HOUR = "unit-hour"
    DAY = "unit-day"
    MONTH = "unit-month"
    YEAR = "unit-year"
