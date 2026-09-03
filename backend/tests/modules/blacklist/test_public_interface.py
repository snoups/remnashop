import app.modules.blacklist as blacklist


def test_public_interface_exports():
    for name in (
        "BlacklistRepository",
        "ListBlacklistUseCase",
        "AddBlacklistEntryUseCase",
        "SyncBlacklistSourcesUseCase",
        "get_blacklist_providers",
        "normalize_identity",
        "BlacklistDto",
    ):
        assert hasattr(blacklist, name)
