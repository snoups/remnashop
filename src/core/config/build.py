from typing import Optional

from src.core.constants import REPOSITORY

from .base import BaseConfig


class BuildConfig(BaseConfig, env_prefix="BUILD_"):
    time: Optional[str] = None
    branch: Optional[str] = None
    commit: Optional[str] = None
    tag: Optional[str] = None

    @property
    def is_set(self) -> bool:
        return any((self.time, self.branch, self.commit, self.tag))

    @property
    def commit_url(self) -> str:
        return f"{REPOSITORY}/commit/{self.commit}"

    @property
    def data(self) -> dict:
        return {
            "has_build": self.is_set,
            "time": self.time,
            "branch": self.branch,
            "commit": self.commit,
            "tag": self.tag,
            "commit_url": self.commit_url,
        }
