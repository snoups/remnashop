from dataclasses import dataclass

from app.modules.connect_guide.catalog import ConnectCatalog


@dataclass(frozen=True, kw_only=True)
class ConnectGuideDto:
    enabled: bool
    catalog: ConnectCatalog
    # nothing saved yet: the built-in catalog, which follows the release
    is_default: bool


@dataclass(frozen=True, kw_only=True)
class UpdateConnectGuideDto:
    enabled: bool
    catalog: ConnectCatalog
    client_ip: str


@dataclass(frozen=True, kw_only=True)
class ResetConnectGuideDto:
    client_ip: str
