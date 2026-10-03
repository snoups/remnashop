from typing import Optional

from app.__version__ import __version__
from app.core.config.base import BaseConfig


class BuildConfig(BaseConfig, env_prefix="BUILD_"):
    tag: Optional[str] = None
    time: Optional[str] = None
    commit: Optional[str] = None
    branch: Optional[str] = None

    @property
    def version(self) -> str:
        # CI tag wins (release tags carry a "v" prefix); __version__ is the local fallback
        return (self.tag or __version__).removeprefix("v")

    @property
    def is_set(self) -> bool:
        return any((self.tag, self.time, self.commit, self.branch))
