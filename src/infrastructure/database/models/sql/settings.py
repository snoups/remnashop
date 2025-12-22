from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import BaseSql


class Settings(BaseSql):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
