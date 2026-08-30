from typing import Optional

from app.core.config.base import BaseConfig
from app.core.constants import REPOSITORY


class BuildConfig(BaseConfig, env_prefix="BUILD_"):
    tag: Optional[str] = None
    time: Optional[str] = None
    commit: Optional[str] = None
    branch: Optional[str] = None

    @property
    def is_set(self) -> bool:
        return any((self.tag, self.time, self.commit, self.branch))

    @property
    def commit_url(self) -> Optional[str]:
        return f"{REPOSITORY}/commit/{self.commit}" if self.commit else None
