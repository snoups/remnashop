from datetime import datetime
from typing import Any

from adaptix import ExtraSkip, Retort, as_is_dumper, dumper, loader, name_mapping
from adaptix._internal.provider.loc_stack_filtering import OriginSubclassLSC
from adaptix.conversion import ConversionRetort, coercer
from dishka import Provider, Scope, provide
from pydantic import SecretStr

from src.application.dto import (
    AccessSettingsDto,
    NotificationsSettingsDto,
    PlanSnapshotDto,
    ReferralSettingsDto,
    RequirementSettingsDto,
)
from src.application.dto.transaction import PriceDetailsDto
from src.core.enums import ReferralLevel, Role
from src.infrastructure.redis.key_builder import StorageKey, serialize_storage_key


class RetortProvider(Provider):
    scope = Scope.APP

    @provide
    def get_retort(self) -> Retort:
        def secret_dumper(value: Any) -> Any:
            if isinstance(value, SecretStr):
                return value.get_secret_value()
            return value

        retort = Retort(
            recipe=[
                as_is_dumper(datetime),
                name_mapping(extra_in=ExtraSkip()),
                #
                loader(
                    dict[ReferralLevel, int],
                    lambda data: {ReferralLevel(int(k)): v for k, v in data.items()},
                ),
                dumper(OriginSubclassLSC(StorageKey), serialize_storage_key),
                #
                loader(SecretStr, SecretStr),
                dumper(SecretStr, lambda v: v.get_secret_value()),
                dumper(Any, secret_dumper),
            ]
        )

        return retort

    @provide
    def get_conversion_retort(self, retort: Retort) -> ConversionRetort:
        conversion_retort = ConversionRetort(
            recipe=[
                coercer(Role, Role, lambda v: Role(v)),
                #
                coercer(dict, PlanSnapshotDto, retort.get_loader(PlanSnapshotDto)),
                coercer(dict, AccessSettingsDto, retort.get_loader(AccessSettingsDto)),
                coercer(dict, RequirementSettingsDto, retort.get_loader(RequirementSettingsDto)),
                coercer(
                    dict, NotificationsSettingsDto, retort.get_loader(NotificationsSettingsDto)
                ),
                coercer(dict, ReferralSettingsDto, retort.get_loader(ReferralSettingsDto)),
                # coercer(SecretStr, str, lambda v: v.get_secret_value()),
                coercer(dict, PriceDetailsDto, retort.get_loader(PriceDetailsDto)),
            ]
        )
        return conversion_retort
